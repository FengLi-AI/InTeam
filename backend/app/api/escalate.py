"""转人工 API：发飞书消息（或模拟）+ 落工单 + 模拟收件箱查看。"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query

from ..core.config import settings
from ..core.security import AdminUser, CurrentUser
from ..schemas.chat import EscalateRequest
from ..services.escalate import escalate, list_mock_messages
from ..services.rate_limit import limiter

router = APIRouter()


@router.post("/escalate")
def escalate_endpoint(
    req: EscalateRequest,
    user: CurrentUser,
    idempotency_key: str = Header(default="", alias="X-Idempotency-Key", max_length=128),
) -> dict:
    limiter.check(
        f"user:{user['id']}:escalate",
        settings.escalate_rate_limit,
        settings.escalate_rate_window_seconds,
    )
    result = escalate(
        req.question,
        req.context,
        user_id=int(user["id"]),
        idempotency_key=idempotency_key,
    )
    return {
        "status": "ok",
        "ticket_id": result["ticket_id"],
        "sent": result["sent"],
        "error": result["error"],
        "mock": result["mock"],
        "deduplicated": result["deduplicated"],
    }


@router.get("/escalate/mock-messages")
def mock_messages(
    _actor: AdminUser, limit: int = Query(default=20, ge=1, le=100)
) -> dict:
    """查看模拟收件箱（开发验收用；配置真实 mentor 后不再产生模拟消息）。"""
    if settings.app_env != "development":
        raise HTTPException(status_code=404, detail="接口不存在")
    return {"items": list_mock_messages(limit)}
