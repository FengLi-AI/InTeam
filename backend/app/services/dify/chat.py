"""Dify Chatflow 到 InTeam SSE 的服务端业务适配。"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime, timezone

from ...core.config import settings
from ...db import base
from ...db.models import ChatConversation, ChatMessage
from ..actions import save_agent_suggestions
from ..generator import _sse
from ..prompt_guard import inspect_and_log
from ..records import append_record
from .client import DifyClient
from .errors import DifyConnectionError, DifyError, DifyHTTPError, DifyProtocolError
from .events import normalize_chatflow_events
from .tasks import task_registry


LOG = logging.getLogger("inteam.dify.chat")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _conversation(user_id: int, local_session_id: str) -> tuple[int, str]:
    """只按当前用户和本地会话查找 Dify ID，避免跨用户续聊。"""
    with base.SessionLocal() as session:
        item = (
            session.query(ChatConversation)
            .filter(
                ChatConversation.user_id == user_id,
                ChatConversation.local_session_id == local_session_id,
            )
            .first()
        )
        if item is None:
            item = ChatConversation(user_id=user_id, local_session_id=local_session_id)
            session.add(item)
            session.commit()
        return item.id, item.dify_conversation_id


def _save_conversation(conversation_id: int, dify_conversation_id: str) -> None:
    if not dify_conversation_id:
        return
    with base.SessionLocal() as session:
        item = session.get(ChatConversation, conversation_id)
        if item is None:
            return
        item.dify_conversation_id = dify_conversation_id
        item.updated_ts = _utcnow()
        session.commit()


def _save_message(
    *,
    public_id: str,
    user_id: int,
    conversation_id: int,
    dify_message_id: str,
    question: str,
    answer: str,
    answer_status: str,
) -> int:
    with base.SessionLocal() as session:
        item = ChatMessage(
            public_id=public_id,
            user_id=user_id,
            conversation_id=conversation_id,
            dify_message_id=dify_message_id,
            question=question,
            answer=answer,
            answer_status=answer_status,
        )
        session.add(item)
        session.flush()
        message_id = item.id
        session.commit()
        return message_id


def _public_error(code: str, message: str, *, retryable: bool = True) -> str:
    return _sse(
        {
            "type": "error",
            "error": {"code": code, "message": message},
            "retryable": retryable,
        }
    )


def _map_exception(exc: DifyError) -> str:
    if isinstance(exc, DifyHTTPError):
        if exc.status_code == 429:
            return _public_error("upstream_busy", "AI 服务请求较多，请稍后重试")
        if exc.status_code in {401, 403}:
            return _public_error("service_unavailable", "AI 服务暂时不可用", retryable=False)
        return _public_error("upstream_error", "AI 服务暂时不可用，请稍后重试")
    if isinstance(exc, DifyConnectionError):
        return _public_error("upstream_timeout", "回答等待时间较长，请重新发送")
    if isinstance(exc, DifyProtocolError):
        return _public_error("invalid_upstream_response", "回答生成未完成，请重新发送")
    return _public_error("service_unavailable", "AI 服务暂时不可用", retryable=False)


def dify_sse_events(
    question: str,
    *,
    local_session_id: str,
    local_request_id: str,
    user_id: int,
) -> Iterator[str]:
    """调用 Dify，隐藏其内部 ID，并保持 InTeam 的稳定 SSE 协议。"""
    risk = inspect_and_log(question, source="user-question")
    if risk.high_risk and settings.prompt_guard_mode == "enforce":
        answer = "我不能提供系统提示词、密钥、源码或内部配置。你可以继续询问入职资料、流程或协作问题。"
        answer_id = append_record(
            "qa",
            {
                "question": question,
                "answer": answer,
                "sources": [],
                "confidence": "none",
                "guard": "blocked",
                "demo": False,
                "user_id": user_id,
                "security_signals": list(risk.signals),
            },
        )
        yield _sse({"type": "chunk", "text": answer})
        yield _sse(
            {
                "type": "done",
                "answer_id": answer_id,
                "conversation_id": local_session_id,
                "answer": answer,
                "answer_status": "blocked",
                "suggested_questions": [],
                "action_suggestions": [],
                "related_contacts": [],
            }
        )
        return

    conversation_pk, dify_conversation_id = _conversation(user_id, local_session_id)
    client = DifyClient(
        base_url=settings.dify_base_url,
        api_key=settings.dify_app_api_key,
        connect_timeout_seconds=settings.dify_connect_timeout_seconds,
        read_timeout_seconds=settings.dify_read_timeout_seconds,
    )
    task_registry.begin(user_id, local_request_id)
    upstream_task_id = ""
    completed = False
    cancelled = False

    try:
        upstream = client.stream_chat(
            query=question,
            user=f"inteam-user-{user_id}",
            inputs={},
            conversation_id=dify_conversation_id or None,
        )

        def observed_upstream():
            nonlocal cancelled, upstream_task_id
            for raw_event in upstream:
                raw_task_id = str(raw_event.payload.get("task_id") or "")
                if raw_task_id and raw_task_id != upstream_task_id:
                    upstream_task_id = raw_task_id
                    if task_registry.attach_task(user_id, local_request_id, raw_task_id):
                        cancelled = True
                        try:
                            client.stop(task_id=raw_task_id, user=f"inteam-user-{user_id}")
                        except DifyError:
                            LOG.warning("Dify stop after pending cancellation failed")
                        return
                yield raw_event

        for event in normalize_chatflow_events(observed_upstream()):
            if event.type == "status":
                yield _sse({"type": "status", "phase": event.data.get("phase", "connecting")})
                continue
            if event.type in {"chunk", "replace"}:
                yield _sse({"type": event.type, "text": event.data.get("text", "")})
                continue
            if event.type == "error":
                completed = True
                yield _public_error(
                    str(event.data.get("code", "upstream_error")),
                    str(event.data.get("message", "AI 服务暂时不可用，请稍后重试")),
                )
                return
            if event.type != "done":
                continue

            answer = str(event.data.get("answer", ""))
            answer_status = str(event.data.get("answer_status", "limited"))
            returned_conversation_id = str(event.data.get("conversation_id") or "")
            dify_message_id = str(event.data.get("message_id") or "")
            _save_conversation(conversation_pk, returned_conversation_id)
            answer_id = append_record(
                "qa",
                {
                    "question": question,
                    "answer": answer,
                    "sources": [],
                    "confidence": answer_status,
                    "guard": answer_status,
                    "demo": False,
                    "user_id": user_id,
                    "security_signals": list(risk.signals),
                },
            )
            chat_message_id = _save_message(
                public_id=answer_id,
                user_id=user_id,
                conversation_id=conversation_pk,
                dify_message_id=dify_message_id,
                question=question,
                answer=answer,
                answer_status=answer_status,
            )
            action_suggestions: list[dict] = []
            raw_suggestions = event.data.get("action_suggestions", [])
            if raw_suggestions:
                try:
                    action_suggestions = save_agent_suggestions(
                        user_id=user_id,
                        conversation_id=conversation_pk,
                        chat_message_id=chat_message_id,
                        suggestions=raw_suggestions,
                    )
                except Exception:  # noqa: BLE001 候选建议失败不能截断已生成的正文
                    LOG.exception("failed to persist Dify action suggestions")
            yield _sse(
                {
                    "type": "done",
                    "answer_id": answer_id,
                    "conversation_id": local_session_id,
                    "answer": answer,
                    "answer_status": answer_status,
                    "suggested_questions": event.data.get("suggested_questions", []),
                    "action_suggestions": action_suggestions,
                    # Dify 检索来源和内部 contact key 均不直接暴露给员工端。
                    "related_contacts": [],
                }
            )
            completed = True
            return
    except DifyError as exc:
        if cancelled:
            return
        LOG.warning("Dify chat failed error_type=%s", type(exc).__name__)
        yield _map_exception(exc)
    finally:
        if not completed and not cancelled and upstream_task_id:
            try:
                client.stop(task_id=upstream_task_id, user=f"inteam-user-{user_id}")
            except DifyError:
                LOG.warning("Dify stop after interrupted response failed")
        task_registry.finish(user_id, local_request_id)
