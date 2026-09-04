"""同步管道：飞书只读拉取 → 切分 → 向量化 → 入库。

同步状态持久化到 records/sync_state.json，支持查看与后续增量同步。
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

from ..core.config import settings
from .embedder import Embedder
from .feishu import FeishuClient, FeishuPermissionError, Section
from .prompt_guard import inspect_and_log
from .vector_store import get_store

LOG = logging.getLogger("inteam.sync")

CHUNK_SIZE = 600  # 每块字符数
CHUNK_OVERLAP = 80  # 相邻块重叠字符数


@dataclass
class _Chunk:
    title: str
    section: str
    text: str
    source_url: str


@dataclass
class SyncItem:
    doc_token: str
    status: str  # synced | skipped | error
    chunk_count: int = 0
    error: str = ""


@dataclass
class SyncResult:
    synced: int = 0
    skipped: int = 0
    failed: int = 0
    quarantined: int = 0
    items: list[SyncItem] = field(default_factory=list)


def split_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """按字符切块，带重叠，避免在边界处切断关键句。"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + size])
        start += size - overlap
    return chunks


def _sections_to_chunks(sections: list[Section]) -> list[_Chunk]:
    chunks: list[_Chunk] = []
    for sec in sections:
        for piece in split_text(sec.text):
            if piece:
                chunks.append(
                    _Chunk(title=sec.title, section=sec.section, text=piece, source_url=sec.source_url)
                )
    return chunks


def load_sync_state() -> dict:
    """读取同步状态文件，损坏时返回空。"""
    path = settings.records_dir / "sync_state.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_sync_state(state: dict) -> None:
    settings.records_dir.mkdir(parents=True, exist_ok=True)
    path = settings.records_dir / "sync_state.json"
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def run_sync() -> SyncResult:
    """执行一次全量同步；未配置飞书时直接返回空结果。"""
    result = SyncResult()
    if not settings.has_feishu:
        return result

    client = FeishuClient(
        settings.feishu_app_id,
        settings.feishu_app_secret,
        base_url=settings.feishu_base_url,
        doc_url_prefix=settings.feishu_doc_url_prefix,
    )
    embedder = Embedder(settings.ark_api_key, settings.ark_base_url, settings.ark_embedding_model)
    store = get_store(str(settings.vectordb_dir))
    state = load_sync_state()

    for doc_token in settings.feishu_doc_tokens:
        item = SyncItem(doc_token=doc_token, status="error")
        try:
            doc = client.fetch_document(doc_token)
            sections = client.extract_sections(doc)
            chunks = _sections_to_chunks(sections)
            risk = inspect_and_log("\n".join(c.text for c in chunks), source=f"sync:{doc_token}")
            if risk.high_risk and settings.prompt_guard_mode == "enforce":
                item.status = "quarantined"
                item.error = "security_review_required"
                result.quarantined += 1
                result.skipped += 1
                state[doc_token] = {
                    "last_sync_ts": time.time(),
                    "chunk_count": 0,
                    "status": "quarantined",
                    "security_signals": list(risk.signals),
                }
                result.items.append(item)
                continue
            texts = [c.text for c in chunks]
            embeddings = embedder.embed(texts)
            ids = [f"{doc_token}:{i}" for i in range(len(chunks))]
            metadatas = [
                {
                    "title": c.title,
                    "section": c.section,
                    "doc_token": doc_token,
                    "source_url": c.source_url,
                }
                for c in chunks
            ]
            store.upsert_document(doc_token, ids, texts, metadatas, embeddings)
            item.status = "synced"
            item.chunk_count = len(chunks)
            result.synced += 1
            state[doc_token] = {
                "last_sync_ts": time.time(),
                "chunk_count": len(chunks),
                "status": "synced",
            }
        except FeishuPermissionError as exc:
            item.status = "skipped"
            item.error = f"denied: {exc.msg}"
            result.skipped += 1
            state[doc_token] = {
                "last_sync_ts": time.time(),
                "chunk_count": 0,
                "status": "skipped",
                "error": exc.msg,
            }
        except Exception as exc:  # noqa: BLE001
            LOG.exception("sync failed for %s", doc_token)
            item.status = "error"
            item.error = str(exc)
            result.failed += 1
            state[doc_token] = {
                "last_sync_ts": time.time(),
                "chunk_count": 0,
                "status": "error",
                "error": str(exc),
            }
        result.items.append(item)

    _save_sync_state(state)
    return result
