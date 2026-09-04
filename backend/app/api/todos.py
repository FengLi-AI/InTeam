"""待办事项 API：列表 / 创建 / 更新 / 删除。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.security import CurrentUser
from ..services.todos import create_todo, delete_todo, list_todos, update_todo

router = APIRouter()


class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    note: str = Field(default="", max_length=2000)
    due_date: str = Field(default="", max_length=16)
    priority: int = Field(default=0, ge=0, le=1)


class TodoUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    note: str | None = Field(default=None, max_length=2000)
    due_date: str | None = Field(default=None, max_length=16)
    status: str | None = Field(default=None, pattern="^(open|done)$")
    priority: int | None = Field(default=None, ge=0, le=1)
    sort_order: int | None = None


@router.get("/todos")
def todos(user: CurrentUser) -> dict:
    return {"items": list_todos(user["id"])}


@router.post("/todos")
def todo_create(req: TodoCreate, user: CurrentUser) -> dict:
    item = create_todo(user["id"], req.title, req.note, req.due_date, req.priority)
    return {"status": "ok", "item": item}


@router.patch("/todos/{todo_id}")
def todo_update(todo_id: int, req: TodoUpdate, user: CurrentUser) -> dict:
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    item = update_todo(user["id"], todo_id, **fields)
    if item is None:
        raise HTTPException(status_code=404, detail="待办不存在")
    return {"status": "ok", "item": item}


@router.delete("/todos/{todo_id}")
def todo_delete(todo_id: int, user: CurrentUser) -> dict:
    ok = delete_todo(user["id"], todo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="待办不存在")
    return {"status": "ok"}
