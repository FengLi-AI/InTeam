"""反馈写入 + 知识盲区判定。"""
from __future__ import annotations

import json
import logging

from ..core.config import settings
from ..db import base
from ..db.models import Feedback

LOG = logging.getLogger("inteam.feedback")


class FeedbackOwnershipError(Exception):
    """答案不存在或不属于当前用户。"""


def _find_qa(answer_id: str, user_id: int | None = None) -> dict | None:
    """从 records/qa.jsonl 反查该 answer_id 的问题与出处（用于盲区判定）。"""
    path = settings.records_dir / "qa.jsonl"
    if not path.exists():
        return None
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("id") == answer_id and (
                user_id is None or rec.get("user_id") == user_id
            ):
                return rec
    except (json.JSONDecodeError, OSError):
        return None
    return None


def record_feedback(answer_id: str, helpful: bool, note: str = "", user_id: int | None = None) -> dict:
    """写一条反馈，返回 {id, blind_spot}。

    盲区判定：无帮助 且 该答案无出处（sources 为空）→ 记为知识盲区，
    供内容维护人补录知识。
    """
    qa = _find_qa(answer_id, user_id)
    if user_id is not None and qa is None:
        raise FeedbackOwnershipError("answer not found")
    question = (qa or {}).get("question", "")
    sources = (qa or {}).get("sources", [])
    blind_spot = (not helpful) and (not sources)

    with base.SessionLocal() as s:
        fb = Feedback(
            user_id=user_id,
            answer_id=answer_id,
            question=question,
            helpful=helpful,
            note=note,
            blind_spot=blind_spot,
        )
        s.add(fb)
        s.commit()
        fb_id = fb.id

    return {"id": str(fb_id), "blind_spot": blind_spot}
