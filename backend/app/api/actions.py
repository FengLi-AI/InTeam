"""Agent 候选建议和用户确认后的行动 API。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..core.security import CurrentUser
from ..schemas.actions import ActionCreateRequest, ActionUpdateRequest
from ..services.actions import (
    ActionConflictError,
    create_action,
    delete_action,
    dismiss_suggestion,
    list_action_plan,
    update_action,
)


router = APIRouter()


@router.get("/actions")
def action_plan(user: CurrentUser) -> dict:
    return list_action_plan(int(user["id"]))


@router.post("/actions")
def action_create(req: ActionCreateRequest, user: CurrentUser) -> dict:
    try:
        item = create_action(int(user["id"]), **req.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="上手主题不存在") from exc
    except ActionConflictError as exc:
        raise HTTPException(status_code=409, detail="候选建议当前无法接受") from exc
    if item is None:
        raise HTTPException(status_code=404, detail="候选建议不存在")
    return {"status": "ok", "item": item}


@router.post("/actions/{action_id}")
@router.patch("/actions/{action_id}")
def action_update(
    action_id: int,
    req: ActionUpdateRequest,
    user: CurrentUser,
) -> dict:
    fields = {key: value for key, value in req.model_dump().items() if value is not None}
    item = update_action(int(user["id"]), action_id, **fields)
    if item is None:
        raise HTTPException(status_code=404, detail="行动不存在")
    return {"status": "ok", "item": item}


@router.delete("/actions/{action_id}")
def action_delete(action_id: int, user: CurrentUser) -> dict:
    if not delete_action(int(user["id"]), action_id):
        raise HTTPException(status_code=404, detail="行动不存在")
    return {"status": "ok"}


@router.post("/actions/{action_id}/delete")
def action_delete_via_post(action_id: int, user: CurrentUser) -> dict:
    """兼容仅放行 GET/POST 的生产 APIG 路由。"""
    return action_delete(action_id, user)


@router.post("/suggestions/{suggestion_id}/dismiss")
def suggestion_dismiss(suggestion_id: int, user: CurrentUser) -> dict:
    try:
        item = dismiss_suggestion(int(user["id"]), suggestion_id)
    except ActionConflictError as exc:
        raise HTTPException(status_code=409, detail="候选建议已经接受") from exc
    if item is None:
        raise HTTPException(status_code=404, detail="候选建议不存在")
    return {"status": "ok", "item": item}
