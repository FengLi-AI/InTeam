"""问答 API 路由（第 3 阶段起反馈/转人工拆分到独立模块）。"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..core.config import settings
from ..core.security import CurrentUser, allowed_doc_tokens
from ..schemas.chat import ChatRequest
from ..services.generator import _sse, filter_untrusted_hits, sse_events
from ..services.guard import decide
from ..services.retriever import load_chunks, search
from ..services.rate_limit import chat_gate, limiter

LOG = logging.getLogger("inteam.api")
router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _index_count() -> int:
    """向量库索引文档块数；未配置方舟 Key 或向量库不可用时返回 0。"""
    if not settings.has_ark:
        return 0
    try:
        from ..services.vector_store import get_store

        return get_store(str(settings.vectordb_dir)).count()
    except Exception:  # noqa: BLE001
        return 0


@router.post("/chat")
def chat(req: ChatRequest, user: CurrentUser) -> StreamingResponse:
    """问答接口：SSE 流式返回（chunk... → done/error）。"""
    user_key = f"user:{user['id']}"
    limiter.check(user_key + ":chat", settings.chat_rate_limit, settings.chat_rate_window_seconds)
    limiter.check(user_key + ":chat-hour", settings.chat_hourly_limit, 3600)
    chat_gate.acquire(
        user_key,
        settings.chat_concurrency_per_user,
        settings.chat_concurrency_global,
    )
    hits = []
    guard = "not_found"
    if settings.chat_provider == "legacy":
        try:
            chunks = load_chunks(settings.knowledge_dir)
            hits = search(req.question, chunks, allowed_doc_tokens=allowed_doc_tokens(user))
            hits = filter_untrusted_hits(hits)
            guard = decide(hits, settings.confidence_threshold)
        except Exception:
            chat_gate.release(user_key)
            raise

    def event_stream():
        try:
            if settings.chat_provider == "dify":
                from ..services.dify.chat import dify_sse_events

                events = dify_sse_events(
                    req.question,
                    local_session_id=req.session_id,
                    local_request_id=req.request_id,
                    user_id=int(user["id"]),
                )
            else:
                events = sse_events(req.question, hits, guard, user_id=int(user["id"]))
            for event in events:
                yield event
        except Exception as exc:  # noqa: BLE001 统一兜底，不泄露堆栈
            LOG.exception("chat stream failed")
            yield _sse(
                {
                    "type": "error",
                    "error": {"code": "internal_error", "message": "服务内部错误，请稍后重试或转人工"},
                }
            )
        finally:
            chat_gate.release(user_key)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/{request_id}/stop")
def stop_chat(request_id: str, user: CurrentUser) -> dict:
    """只接受 InTeam 本地 request_id，服务端内部解析并停止 Dify 任务。"""
    from ..services.dify.client import DifyClient
    from ..services.dify.errors import DifyError
    from ..services.dify.tasks import task_registry

    if re.fullmatch(r"[A-Za-z0-9_-]{8,64}", request_id) is None:
        raise HTTPException(status_code=404, detail="生成请求不存在")
    found, task_id = task_registry.request_stop(int(user["id"]), request_id)
    if not found:
        raise HTTPException(status_code=404, detail="生成请求不存在")
    if not task_id:
        return {"status": "stopping"}
    client = DifyClient(
        base_url=settings.dify_base_url,
        api_key=settings.dify_app_api_key,
        connect_timeout_seconds=settings.dify_connect_timeout_seconds,
        read_timeout_seconds=settings.dify_read_timeout_seconds,
    )
    try:
        stopped = client.stop(task_id=task_id, user=f"inteam-user-{int(user['id'])}")
    except DifyError as exc:
        LOG.warning("Dify stop failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="停止生成失败，请稍后重试") from exc
    task_registry.finish(int(user["id"]), request_id)
    return {"status": "stopped" if stopped else "stopping"}
