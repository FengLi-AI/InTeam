"""反馈统计 + 知识盲区汇总。"""
from __future__ import annotations

from sqlalchemy import func

from ..db import base
from ..db.models import EscalateTicket, Feedback


def get_stats(blind_spot_limit: int = 50) -> dict:
    """返回帮助率、反馈数、转人工数、知识盲区列表。"""
    with base.SessionLocal() as s:
        helpful = s.query(func.count(Feedback.id)).filter(Feedback.helpful.is_(True)).scalar() or 0
        total = s.query(func.count(Feedback.id)).scalar() or 0
        escalate_count = s.query(func.count(EscalateTicket.id)).scalar() or 0
        blind_spots = (
            s.query(Feedback)
            .filter(Feedback.blind_spot.is_(True))
            .order_by(Feedback.ts.desc())
            .limit(blind_spot_limit)
            .all()
        )

    return {
        "helpful_rate": round(helpful / total, 4) if total else 0.0,
        "feedback_count": total,
        "escalate_count": escalate_count,
        "blind_spots": [
            {
                "id": str(b.id),
                "ts": b.ts.isoformat() if b.ts else "",
                "question": b.question,
                "note": b.note,
            }
            for b in blind_spots
        ],
    }
