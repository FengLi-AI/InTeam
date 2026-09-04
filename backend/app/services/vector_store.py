"""Chroma 向量库封装：写入 / 查询 / 计数。

chromadb 采用惰性导入（首次实例化才加载），避免无向量需求的路径
（如第 1 阶段纯关键词检索、健康检查）承担启动开销。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

LOG = logging.getLogger("inteam.vector_store")

_COLLECTION = "inteam_knowledge"


@dataclass
class VectorHit:
    """一次向量检索命中。"""

    text: str
    title: str
    section: str
    doc_token: str
    source_url: str
    score: float


class VectorStore:
    """持久化向量库（cosine 相似度）。"""

    def __init__(self, persist_dir: Path) -> None:
        import chromadb
        from chromadb.config import Settings

        persist_dir.mkdir(parents=True, exist_ok=True)
        # 只使用进程内嵌入式客户端，不启动 Chroma HTTP 服务，不暴露其
        # 集合创建/更新 API；同时关闭遥测和 reset 能力。
        self._client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False, allow_reset=False),
        )
        self._collection = self._client.get_or_create_collection(
            _COLLECTION, metadata={"hnsw:space": "cosine"}
        )

    def upsert_document(
        self,
        doc_token: str,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict],
        embeddings: list[list[float]],
    ) -> None:
        """覆盖式写入某文档的全部切块（先删旧块，避免重复同步产生冗余）。"""
        self._collection.delete(where={"doc_token": doc_token})
        if ids:
            self._collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas,
                embeddings=embeddings,
            )

    def query(
        self,
        embedding: list[float],
        top_k: int = 4,
        allowed_doc_tokens: set[str] | None = None,
    ) -> list[VectorHit]:
        """按 cosine 相似度查询 top_k 条，score 归一化到 [0, 1]。"""
        count = self._collection.count()
        if count == 0:
            return []
        if allowed_doc_tokens is not None and not allowed_doc_tokens:
            return []
        kwargs = {}
        if allowed_doc_tokens is not None:
            kwargs["where"] = {"doc_token": {"$in": sorted(allowed_doc_tokens)}}
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
            **kwargs,
        )
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        dists = result.get("distances", [[]])[0]
        hits: list[VectorHit] = []
        for i, _ in enumerate(ids):
            meta = metas[i] or {}
            # cosine space 下 distance = 1 - cos，故 cos = 1 - distance
            score = max(0.0, min(1.0, 1.0 - float(dists[i])))
            hits.append(
                VectorHit(
                    text=docs[i] or "",
                    title=meta.get("title", ""),
                    section=meta.get("section", ""),
                    doc_token=meta.get("doc_token", ""),
                    source_url=meta.get("source_url", ""),
                    score=score,
                )
            )
        return hits

    def count(self) -> int:
        return self._collection.count()

    def list_documents(self, allowed_doc_tokens: set[str] | None = None) -> list[dict]:
        """按 doc_token 去重返回文档列表（title / token / 链接）。"""
        if allowed_doc_tokens is not None and not allowed_doc_tokens:
            return []
        kwargs = {}
        if allowed_doc_tokens is not None:
            kwargs["where"] = {"doc_token": {"$in": sorted(allowed_doc_tokens)}}
        result = self._collection.get(include=["metadatas"], **kwargs)
        docs: dict[str, dict] = {}
        for m in result.get("metadatas", []) or []:
            token = m.get("doc_token", "")
            if token and token not in docs:
                docs[token] = {
                    "doc_token": token,
                    "title": m.get("title", ""),
                    "url": m.get("source_url", ""),
                }
        return list(docs.values())

    def get_doc_chunks(
        self, doc_token: str, allowed_doc_tokens: set[str] | None = None
    ) -> list[str]:
        """返回某文档的全部切块文本（用于导读/摘要）。"""
        if allowed_doc_tokens is not None and doc_token not in allowed_doc_tokens:
            return []
        result = self._collection.get(where={"doc_token": doc_token}, include=["documents"])
        return result.get("documents", []) or []

    def get_all_chunks(self, allowed_doc_tokens: set[str] | None = None) -> list[dict]:
        """返回全部切块（title/section/text/url/doc_token），供关键词降级检索。"""
        if allowed_doc_tokens is not None and not allowed_doc_tokens:
            return []
        kwargs = {}
        if allowed_doc_tokens is not None:
            kwargs["where"] = {"doc_token": {"$in": sorted(allowed_doc_tokens)}}
        result = self._collection.get(include=["documents", "metadatas"], **kwargs)
        docs = result.get("documents", []) or []
        metas = result.get("metadatas", []) or []
        out: list[dict] = []
        for i, doc in enumerate(docs):
            m = (metas[i] if i < len(metas) else {}) or {}
            out.append(
                {
                    "title": m.get("title", ""),
                    "section": m.get("section", ""),
                    "text": doc or "",
                    "url": m.get("source_url", ""),
                    "doc_token": m.get("doc_token", ""),
                }
            )
        return out


@lru_cache(maxsize=8)
def get_store(persist_dir: str) -> VectorStore:
    """按目录缓存 VectorStore 实例（同一进程内复用连接）。"""
    return VectorStore(Path(persist_dir))
