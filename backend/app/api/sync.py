"""同步触发与状态查询 API。"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ..core.config import settings
from ..core.security import AdminUser
from ..services.sync import load_sync_state, run_sync
from ..services.rate_limit import sync_gate

LOG = logging.getLogger("inteam.api.sync")
router = APIRouter()


@router.post("/sync")
def sync(_actor: AdminUser) -> dict:
    """触发一次飞书文档同步（阻塞执行，规模大后再改后台任务）。"""
    if not settings.has_feishu:
        raise HTTPException(
            status_code=400,
            detail="飞书应用未配置（FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_DOC_TOKENS）",
        )
    sync_gate.acquire("sync", 1, 1)
    try:
        result = run_sync()
    finally:
        sync_gate.release("sync")
    return {
        "status": "ok",
        "synced": result.synced,
        "skipped": result.skipped,
        "failed": result.failed,
        "quarantined": result.quarantined,
        "items": [
            {
                "doc_token": i.doc_token,
                "status": i.status,
                "chunk_count": i.chunk_count,
                "error": i.error,
            }
            for i in result.items
        ],
    }


@router.get("/sync/status")
def sync_status(_actor: AdminUser) -> dict:
    """查询各文档最近一次同步状态。"""
    state = load_sync_state()
    items = [{"doc_token": token, **meta} for token, meta in state.items()]
    return {"items": items}
