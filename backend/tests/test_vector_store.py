"""Chroma 向量库封装测试（真实本地 chromadb，tmp 目录）。"""
from app.services.vector_store import VectorStore


def _meta(doc_token: str, title: str = "入职首周", section: str = "说明会") -> dict:
    return {
        "title": title,
        "section": section,
        "doc_token": doc_token,
        "source_url": f"https://x/docx/{doc_token}",
    }


def test_upsert_and_query(tmp_path):
    store = VectorStore(tmp_path)
    store.upsert_document(
        "doc1",
        ids=["doc1:0"],
        texts=["新员工入职首周指南"],
        metadatas=[_meta("doc1")],
        embeddings=[[0.1, 0.2, 0.3]],
    )
    assert store.count() == 1

    hits = store.query([0.1, 0.2, 0.3], top_k=3)
    assert hits
    assert hits[0].title == "入职首周"
    assert hits[0].section == "说明会"
    assert hits[0].doc_token == "doc1"
    assert hits[0].source_url == "https://x/docx/doc1"
    assert 0.0 <= hits[0].score <= 1.0


def test_upsert_replaces_old_doc(tmp_path):
    store = VectorStore(tmp_path)
    store.upsert_document(
        "doc1",
        ids=["doc1:0"],
        texts=["旧内容"],
        metadatas=[_meta("doc1")],
        embeddings=[[0.1, 0.2, 0.3]],
    )
    store.upsert_document(
        "doc1",
        ids=["doc1:0", "doc1:1"],
        texts=["新内容一", "新内容二"],
        metadatas=[_meta("doc1"), _meta("doc1", section="考勤")],
        embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
    )
    assert store.count() == 2  # 旧 1 条被替换，而非累积为 3 条


def test_query_empty_store(tmp_path):
    store = VectorStore(tmp_path)
    assert store.query([0.1, 0.2, 0.3], top_k=3) == []
    assert store.count() == 0
