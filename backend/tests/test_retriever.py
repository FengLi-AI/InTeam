"""检索器单元测试。"""
from pathlib import Path

from app.services import retriever
from app.core import config
from app.services.retriever import Chunk, Hit, load_chunks, search

DATA = Path(__file__).resolve().parents[1] / "data" / "knowledge"


def test_load_chunks_parses_title_and_sections():
    chunks = load_chunks(DATA)
    assert chunks, "样例知识库应至少产出一个切块"
    titles = {c.title for c in chunks}
    assert "前端代码规范" in titles


def test_search_hits_relevant_chunk():
    chunks = load_chunks(DATA)
    hits = search("命名规范是什么", chunks)
    assert hits, "应有命中"
    assert hits[0].chunk.title == "前端代码规范"
    assert any(h.chunk.section == "命名规范" for h in hits)


def test_search_no_match_returns_empty():
    chunks = load_chunks(DATA)
    hits = search("火星基地在哪里", chunks)
    assert hits == []


def test_search_empty_query():
    chunks = load_chunks(DATA)
    assert search("", chunks) == []


def test_search_falls_back_to_keyword_without_ark(monkeypatch):
    """未配置方舟 Key 时，search 走关键词检索（第 1 阶段行为不变）。"""
    monkeypatch.setattr(config.settings, "ark_api_key", "")
    monkeypatch.setattr(config.settings, "ark_embedding_model", "")
    chunks = load_chunks(DATA)
    hits = search("命名规范是什么", chunks)
    assert hits
    assert hits[0].chunk.title == "前端代码规范"


def test_search_uses_vector_when_available(monkeypatch):
    """向量检索可用时优先返回向量命中（含飞书出处链接）。"""
    fake_hit = Hit(
        chunk=Chunk(
            title="飞书文档", section="章节", text="内容", path="", url="https://x/docx/T"
        ),
        score=0.9,
    )
    monkeypatch.setattr(retriever, "_vector_search", lambda q, k, allowed: [fake_hit])
    hits = search("问题", [])
    assert hits == [fake_hit]
    assert hits[0].chunk.url == "https://x/docx/T"
