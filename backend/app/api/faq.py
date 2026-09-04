"""FAQ API：候选沉淀 / 确认 / 检索。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..core.security import AdminUser, CurrentUser
from ..schemas.chat import FaqCreateRequest
from ..services.faq import add_faq, confirm_faq, search_faq

router = APIRouter()


@router.get("/faq")
def faq_search(_user: CurrentUser, q: str = Query(default="", max_length=2000)) -> dict:
    return {"items": search_faq(q)}


@router.post("/faq")
def faq_create(req: FaqCreateRequest, _actor: AdminUser) -> dict:
    faq_id = add_faq(req.question, req.answer, req.source_url)
    return {"status": "ok", "faq_id": faq_id}


@router.post("/faq/{faq_id}/confirm")
def faq_confirm(faq_id: int, _actor: AdminUser) -> dict:
    if not confirm_faq(faq_id):
        raise HTTPException(status_code=404, detail="FAQ 不存在")
    return {"status": "ok"}
