"""检索服务：向量检索优先，失败或无方舟 Key 时降级关键词检索。

对外接口 `search(query, chunks, top_k)` 保持第 1 阶段签名不变：
- 第 2 阶段起，若配置了方舟 Embedding 且向量库有数据，先走向量检索；
- 向量检索不可用 / 无命中时，降级为关键词检索（复用第 1 阶段实现）。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from ..core.config import settings

LOG = logging.getLogger("inteam.retriever")

# 向量检索「无命中」下限：余弦相似度低于此值视为不相关，丢弃后走 not_found 兑底。
# 实测：相关问题 0.42~0.63，无关问题 0.18~0.26，0.3 是稳定分界线。
MIN_VECTOR_SCORE = 0.3


@dataclass
class Chunk:
    """知识库中的一个切块（文档标题 + 章节 + 正文）。"""

    title: str
    section: str
    text: str
    path: str
    url: str = ""  # 第 2 阶段：飞书原文链接（可选）
    doc_token: str = ""  # 第 2 阶段：飞书文档 token（可选）


@dataclass
class Hit:
    """一次检索命中：切块 + 匹配分数（0~1）。"""

    chunk: Chunk
    score: float


def _tokenize(text: str) -> set[str]:
    """简单分词：英文/数字单词 + 中文 2-gram（不用单字，避免误命中）。"""
    text = text.lower()
    tokens = set(re.findall(r"[a-z0-9]+", text))
    cn_chars = re.findall(r"[\u4e00-\u9fff]", text)
    for i in range(len(cn_chars) - 1):
        tokens.add(cn_chars[i] + cn_chars[i + 1])
    return tokens


def load_chunks(knowledge_dir: Path) -> list[Chunk]:
    """加载目录下所有 markdown，解析 frontmatter，按二级标题切块（第 1 阶段样例库）。"""
    chunks: list[Chunk] = []
    for md in sorted(knowledge_dir.glob("*.md")):
        if md.name.startswith("."):  # 跳过 macOS AppleDouble 等隐藏文件
            continue
        raw = md.read_text(encoding="utf-8")
        title = md.stem
        body = raw
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                fm_match = re.search(r"title:\s*(.+)", parts[1])
                if fm_match:
                    title = fm_match.group(1).strip()
                body = parts[2]
        sections = re.split(r"(?m)^##\s+", body)
        intro = sections[0].strip()
        if intro:
            chunks.append(Chunk(title=title, section="概述", text=intro, path=md.name))
        for sec in sections[1:]:
            lines = sec.split("\n", 1)
            heading = lines[0].strip()
            content = lines[1].strip() if len(lines) > 1 else ""
            if content:
                chunks.append(
                    Chunk(title=title, section=heading, text=f"{heading}\n{content}", path=md.name)
                )
    return chunks


def search(
    query: str,
    chunks: list[Chunk] | None = None,
    top_k: int = 4,
    allowed_doc_tokens: set[str] | None = None,
) -> list[Hit]:
    """统一检索入口：向量优先 → 向量库关键词降级 → 本地样例库（最后兜底）。"""
    hits = _vector_search(query, top_k, allowed_doc_tokens)
    if hits:
        return hits
    hits = _keyword_search_from_store(query, top_k, allowed_doc_tokens)
    if hits:
        return hits
    if chunks:
        visible_chunks = chunks
        if allowed_doc_tokens is not None:
            visible_chunks = [c for c in chunks if c.doc_token in allowed_doc_tokens]
        return _keyword_search(query, visible_chunks, top_k)
    return []


def _keyword_search_from_store(
    query: str, top_k: int = 4, allowed_doc_tokens: set[str] | None = None
) -> list[Hit]:
    """向量检索失败时，用向量库里的文档文本做关键词检索（替代本地样例库）。"""
    try:
        from .vector_store import get_store

        store = get_store(str(settings.vectordb_dir))
        raw = store.get_all_chunks(allowed_doc_tokens)
        chunks = [
            Chunk(
                title=r["title"],
                section=r["section"],
                text=r["text"],
                path="",
                url=r["url"],
                doc_token=r["doc_token"],
            )
            for r in raw
        ]
        return _keyword_search(query, chunks, top_k)
    except Exception as exc:  # noqa: BLE001
        LOG.warning("keyword search from store failed: %s", exc)
        return []


def _keyword_search(query: str, chunks: list[Chunk], top_k: int = 4) -> list[Hit]:
    """按 token 重叠率打分，返回 top_k 个命中（分数 0 的丢弃）。"""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []
    hits: list[Hit] = []
    for c in chunks:
        c_tokens = _tokenize(c.text)
        overlap = len(q_tokens & c_tokens)
        if overlap == 0:
            continue
        score = overlap / len(q_tokens)
        score += 0.02 * (1 / (1 + len(c.text) / 800))
        hits.append(Hit(chunk=c, score=min(score, 1.0)))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]


def _vector_search(
    query: str, top_k: int = 4, allowed_doc_tokens: set[str] | None = None
) -> list[Hit]:
    """向量检索：需方舟 Key；向量库空、异常时返回空列表交由上层降级。"""
    if not settings.has_ark:
        return []
    try:
        from .embedder import Embedder
        from .vector_store import get_store

        store = get_store(str(settings.vectordb_dir))
        if store.count() == 0:
            return []
        embedding = Embedder(
            settings.ark_api_key, settings.ark_base_url, settings.ark_embedding_model
        ).embed([query])[0]
        results = store.query(embedding, top_k, allowed_doc_tokens)
        hits: list[Hit] = []
        for r in results:
            if r.score < MIN_VECTOR_SCORE:  # 低于下限视为不相关，避免误答
                continue
            hits.append(
                Hit(
                    chunk=Chunk(
                        title=r.title,
                        section=r.section,
                        text=r.text,
                        path="",
                        url=r.source_url,
                        doc_token=r.doc_token,
                    ),
                    score=r.score,
                )
            )
        return hits
    except Exception as exc:  # noqa: BLE001
        LOG.warning("vector search failed, fallback to keyword: %s", exc)
        return []
