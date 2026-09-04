"""统计 API：帮助率 / 转人工数 / 知识盲区。"""
from __future__ import annotations

from fastapi import APIRouter

from ..core.security import AdminUser
from ..services.stats import get_stats

router = APIRouter()


@router.get("/stats")
def stats(_actor: AdminUser) -> dict:
    return get_stats()
