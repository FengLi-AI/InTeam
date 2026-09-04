"""反馈 API：写入 SQLite + 盲区判定。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..core.config import settings
from ..core.security import CurrentUser
from ..schemas.chat import FeedbackRequest
from ..services.feedback import FeedbackOwnershipError, record_feedback
from ..services.rate_limit import limiter

router = APIRouter()


@router.post("/feedback")
def feedback(req: FeedbackRequest, user: CurrentUser) -> dict:
    limiter.check(
        f"user:{user['id']}:feedback",
        settings.feedback_rate_limit,
        settings.feedback_rate_window_seconds,
    )
    try:
        result = record_feedback(req.answer_id, req.helpful, req.note, int(user["id"]))
    except FeedbackOwnershipError as exc:
        raise HTTPException(status_code=404, detail="答案不存在") from exc
    return {"status": "ok", "id": result["id"], "blind_spot": result["blind_spot"]}
