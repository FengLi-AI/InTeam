"""今日卡片 API。"""
from __future__ import annotations

from fastapi import APIRouter

from ..core.security import CurrentUser
from ..services.dashboard import get_dashboard

router = APIRouter()


@router.get("/dashboard")
def dashboard(user: CurrentUser) -> dict:
    return get_dashboard(user["id"])
