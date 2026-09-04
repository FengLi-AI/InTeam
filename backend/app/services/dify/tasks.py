"""短期保存本地请求与 Dify task_id 的映射，不向浏览器暴露上游 ID。"""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import monotonic


@dataclass
class _TaskState:
    task_id: str = ""
    cancel_requested: bool = False
    expires_at: float = 0


class DifyTaskRegistry:
    def __init__(self, ttl_seconds: int = 600) -> None:
        self._ttl_seconds = ttl_seconds
        self._items: dict[tuple[int, str], _TaskState] = {}
        self._lock = Lock()

    def _cleanup(self, now: float) -> None:
        expired = [key for key, item in self._items.items() if item.expires_at <= now]
        for key in expired:
            self._items.pop(key, None)

    def begin(self, user_id: int, request_id: str) -> None:
        now = monotonic()
        with self._lock:
            self._cleanup(now)
            self._items[(user_id, request_id)] = _TaskState(
                expires_at=now + self._ttl_seconds
            )

    def attach_task(self, user_id: int, request_id: str, task_id: str) -> bool:
        """绑定上游任务；返回是否已经收到停止请求。"""
        now = monotonic()
        with self._lock:
            self._cleanup(now)
            item = self._items.get((user_id, request_id))
            if item is None:
                return True
            item.task_id = task_id
            item.expires_at = now + self._ttl_seconds
            return item.cancel_requested

    def request_stop(self, user_id: int, request_id: str) -> tuple[bool, str]:
        """登记停止；返回 (是否存在当前用户请求, 已知的 task_id)。"""
        now = monotonic()
        with self._lock:
            self._cleanup(now)
            item = self._items.get((user_id, request_id))
            if item is None:
                return False, ""
            item.cancel_requested = True
            item.expires_at = now + self._ttl_seconds
            return True, item.task_id

    def finish(self, user_id: int, request_id: str) -> None:
        with self._lock:
            self._items.pop((user_id, request_id), None)

    def reset(self) -> None:
        with self._lock:
            self._items.clear()


task_registry = DifyTaskRegistry()
