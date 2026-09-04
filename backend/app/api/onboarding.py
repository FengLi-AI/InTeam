"""六主题上手地图 API。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..core.security import CurrentUser
from ..schemas.onboarding import OnboardingProgressUpdate
from ..services.onboarding import list_onboarding_map, set_topic_progress


router = APIRouter()


@router.get("/onboarding-map")
def onboarding_map(user: CurrentUser) -> dict:
    return {"items": list_onboarding_map(int(user["id"]))}


@router.post("/onboarding-map/{topic_key}")
@router.patch("/onboarding-map/{topic_key}")
def onboarding_progress_update(
    topic_key: str,
    req: OnboardingProgressUpdate,
    user: CurrentUser,
) -> dict:
    try:
        item = set_topic_progress(int(user["id"]), topic_key, req.status)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="上手主题不存在") from exc
    return {"status": "ok", "item": item}
