"""火山方舟 Embedding：文本向量化。

技术适配说明（偏离阶段文档预想）：用户账号仅有豆包多模态向量化模型
`doubao-embedding-vision-251215`，它走的是方舟「多模态向量化 API」
`POST /api/v3/embeddings/multimodal`（input 为对象数组、响应为单个 embedding），
而非 OpenAI 兼容的 `/embeddings` 接口，因此本模块用 httpx 直连，不用 openai SDK。
"""
from __future__ import annotations

import logging
import time

import httpx

LOG = logging.getLogger("inteam.embedder")


class EmbedError(Exception):
    """向量化失败。"""


class Embedder:
    """把文本列表逐个转为向量列表，失败有限重试。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 60.0,
        max_retries: int = 2,
        retry_backoff: float = 2.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

    def embed(self, texts: list[str]) -> list[list[float]]:
        """返回与输入一一对应的向量列表（逐条调用多模态接口）。"""
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        url = f"{self.base_url}/embeddings/multimodal"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        body = {"model": self.model, "input": [{"type": "text", "text": text}]}
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = httpx.post(url, headers=headers, json=body, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                embedding = (data.get("data") or {}).get("embedding")
                if embedding:
                    return embedding
                raise EmbedError(f"unexpected response: {str(data)[:200]}")
            except EmbedError:
                raise
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                LOG.warning("embedding attempt %d failed: %s", attempt + 1, exc)
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff**attempt)
        raise EmbedError(f"embedding failed after {self.max_retries + 1} attempts: {last_exc}")
