"""单实例滑动窗口限流与并发闸门。

当前 MVP 为单机部署；多实例生产部署时应把计数迁移到 Redis/网关。
"""
from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.RLock()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, math.ceil(events[0] + window_seconds - now))
                raise HTTPException(
                    status_code=429,
                    detail="请求过于频繁，请稍后重试",
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(now)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


class ConcurrencyGate:
    def __init__(self) -> None:
        self._per_key: dict[str, int] = defaultdict(int)
        self._total = 0
        self._lock = threading.RLock()

    def acquire(self, key: str, per_key_limit: int, global_limit: int) -> None:
        with self._lock:
            if self._per_key[key] >= per_key_limit or self._total >= global_limit:
                raise HTTPException(
                    status_code=429,
                    detail="当前请求较多，请稍后重试",
                    headers={"Retry-After": "3"},
                )
            self._per_key[key] += 1
            self._total += 1

    def release(self, key: str) -> None:
        with self._lock:
            if self._per_key[key] > 0:
                self._per_key[key] -= 1
                self._total = max(0, self._total - 1)
            if self._per_key[key] == 0:
                self._per_key.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._per_key.clear()
            self._total = 0


limiter = SlidingWindowLimiter()
chat_gate = ConcurrencyGate()
sync_gate = ConcurrencyGate()


def client_ip(request: Request) -> str:
    """仅信任 ASGI server 解析出的客户端地址，不直接信任用户提供的 XFF。"""
    return request.client.host if request.client else "unknown"
