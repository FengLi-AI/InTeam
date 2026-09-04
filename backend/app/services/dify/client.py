"""Dify Chatflow Service API 客户端。"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

import httpx

from .errors import (
    DifyConfigurationError,
    DifyConnectionError,
    DifyHTTPError,
)
from .events import DifyEvent, parse_sse_lines


class DifyClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        connect_timeout_seconds: float = 10,
        read_timeout_seconds: float = 120,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=30,
            pool=connect_timeout_seconds,
        )
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise DifyConfigurationError("DIFY_APP_API_KEY is not configured")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def stream_chat(
        self,
        *,
        query: str,
        user: str,
        inputs: Mapping[str, Any],
        conversation_id: str | None = None,
    ) -> Iterator[DifyEvent]:
        payload: dict[str, Any] = {
            "query": query,
            "inputs": dict(inputs),
            "response_mode": "streaming",
            "user": user,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}/chat-messages",
                    headers=self._headers(),
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        raise DifyHTTPError(response.status_code)
                    yield from parse_sse_lines(response.iter_lines())
        except DifyHTTPError:
            raise
        except httpx.TransportError as exc:
            raise DifyConnectionError("Dify connection failed") from exc

    def stop(self, *, task_id: str, user: str) -> bool:
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.post(
                    f"{self.base_url}/chat-messages/{task_id}/stop",
                    headers=self._headers(),
                    json={"user": user},
                )
        except httpx.TransportError as exc:
            raise DifyConnectionError("Dify stop request failed") from exc
        if response.status_code != 200:
            raise DifyHTTPError(response.status_code)
        body = response.json()
        return isinstance(body, dict) and body.get("result") == "success"
