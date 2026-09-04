"""资料库 API：文档列表 + 文档 AI 导读。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..core.security import CurrentUser, allowed_doc_tokens
from ..services.docs import doc_intro, list_docs

router = APIRouter()


@router.get("/docs")
def docs(user: CurrentUser) -> dict:
    items = list_docs(allowed_doc_tokens(user))
    return {"items": items}


@router.get("/docs/{doc_token}/intro")
def docs_intro(doc_token: str, user: CurrentUser) -> dict:
    allowed = allowed_doc_tokens(user)
    if allowed is not None and doc_token not in allowed:
        raise HTTPException(status_code=404, detail="资料不存在")
    intro = doc_intro(doc_token, allowed)
    return {"intro": intro}
