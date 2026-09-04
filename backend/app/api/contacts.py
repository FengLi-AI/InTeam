"""关键同事 API：列表 / AI 简介 / 沟通草稿 / 备注标签。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.security import CurrentUser
from ..services.contacts import add_label, contact_intro, draft_message, get_contact, list_contacts

router = APIRouter()


class LabelRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=64)


class DraftRequest(BaseModel):
    topic: str = Field(default="", max_length=500)


@router.get("/contacts")
def contacts(user: CurrentUser) -> dict:
    items = list_contacts(user["id"])
    return {"items": items, "count": len(items)}


@router.get("/contacts/{contact_id}/intro")
def intro(contact_id: int, user: CurrentUser) -> dict:
    c = get_contact(contact_id)
    if c is None:
        raise HTTPException(status_code=404, detail="同事不存在")
    name = user.get("name", "新同事")
    return {"intro": contact_intro(c, name)}


@router.post("/contacts/{contact_id}/draft")
def draft(contact_id: int, req: DraftRequest, user: CurrentUser) -> dict:
    c = get_contact(contact_id)
    if c is None:
        raise HTTPException(status_code=404, detail="同事不存在")
    name = user.get("name", "新同事")
    text = draft_message(c, name)
    if req.topic:
        text = f"【关于：{req.topic}】\n{text}"
    return {"message": text}


@router.post("/contacts/{contact_id}/labels")
def label(contact_id: int, req: LabelRequest, user: CurrentUser) -> dict:
    if get_contact(contact_id) is None:
        raise HTTPException(status_code=404, detail="同事不存在")
    result = add_label(user["id"], contact_id, req.label)
    return {"status": "ok", "added": result["added"]}
