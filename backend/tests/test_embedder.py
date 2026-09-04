"""Embedder 测试（mock 火山方舟多模态向量化接口）。"""
import pytest

from app.services.embedder import EmbedError, Embedder


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self._status = status

    def raise_for_status(self):
        if self._status >= 400:
            raise RuntimeError(f"HTTP {self._status}")

    def json(self):
        return self._payload


def test_embed_returns_vectors(monkeypatch):
    seen: list[dict] = []

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.append((url, json))
        return _Resp({"data": {"embedding": [0.1, 0.2]}})

    monkeypatch.setattr("app.services.embedder.httpx.post", fake_post)
    emb = Embedder("k", "https://x", "m")
    out = emb.embed(["a", "b"])

    assert out == [[0.1, 0.2], [0.1, 0.2]]
    assert len(seen) == 2
    assert all(url.endswith("/embeddings/multimodal") for url, _ in seen)
    assert [body["input"][0]["text"] for _, body in seen] == ["a", "b"]
    assert seen[0][1]["model"] == "m"


def test_embed_empty_input():
    emb = Embedder("k", "https://x", "m")
    assert emb.embed([]) == []


def test_embed_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("boom")
        return _Resp({"data": {"embedding": [0.9]}})

    monkeypatch.setattr("app.services.embedder.httpx.post", fake_post)
    emb = Embedder("k", "https://x", "m", max_retries=2, retry_backoff=0)
    assert emb.embed(["a"]) == [[0.9]]
    assert calls["n"] == 3


def test_embed_all_fail_raises(monkeypatch):
    def fake_post(url, **kwargs):
        raise RuntimeError("down")

    monkeypatch.setattr("app.services.embedder.httpx.post", fake_post)
    emb = Embedder("k", "https://x", "m", max_retries=1, retry_backoff=0)
    with pytest.raises(EmbedError):
        emb.embed(["a"])


def test_embed_unexpected_response_raises(monkeypatch):
    def fake_post(url, **kwargs):
        return _Resp({"error": "missing data"})

    monkeypatch.setattr("app.services.embedder.httpx.post", fake_post)
    emb = Embedder("k", "https://x", "m")
    with pytest.raises(EmbedError):
        emb.embed(["a"])
