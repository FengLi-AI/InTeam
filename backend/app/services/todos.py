"""待办事项：默认入职模板 + 列表/创建/更新/删除。"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from ..db import base
from ..db.models import Todo, _utcnow

LOG = logging.getLogger("inteam.todos")

# 默认入职待办模板：(标题, 相对入职天数偏移, 优先级)
DEFAULT_TODOS = [
    ("参加入职说明会", 0, 1),
    ("领取工牌和办公设备", 0, 0),
    ("认识 mentor 和直属 leader", 0, 1),
    ("开通代码仓库权限", 1, 1),
    ("搭建本地开发环境", 1, 0),
    ("了解研发协作与发布流程", 3, 0),
    ("开通报销、考勤系统", 5, 0),
]


def seed_todos_for_user(user_id: int) -> None:
    """首次访问时给用户预置默认入职待办（幂等）。"""
    with base.SessionLocal() as s:
        if s.query(Todo).filter(Todo.user_id == user_id).count() > 0:
            return
        today = date.today()
        for i, (title, offset_days, priority) in enumerate(DEFAULT_TODOS):
            due = (today + timedelta(days=offset_days)).isoformat()
            s.add(
                Todo(
                    user_id=user_id,
                    title=title,
                    due_date=due,
                    priority=priority,
                    sort_order=i,
                )
            )
        s.commit()


def _todo_to_dict(t: Todo) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "note": t.note,
        "due_date": t.due_date,
        "status": t.status,
        "priority": t.priority,
        "sort_order": t.sort_order,
    }


def list_todos(user_id: int) -> list[dict]:
    """列出用户待办（无则先 seed 默认模板），按日期+优先级排序。"""
    seed_todos_for_user(user_id)
    with base.SessionLocal() as s:
        rows = s.query(Todo).filter(Todo.user_id == user_id).all()
    rows.sort(key=lambda t: (t.due_date, -t.priority, t.sort_order))
    return [_todo_to_dict(t) for t in rows]


def create_todo(user_id: int, title: str, note: str = "", due_date: str = "", priority: int = 0) -> dict:
    with base.SessionLocal() as s:
        max_order = (
            s.query(Todo)
            .filter(Todo.user_id == user_id)
            .order_by(Todo.sort_order.desc())
            .first()
        )
        todo = Todo(
            user_id=user_id,
            title=title,
            note=note,
            due_date=due_date,
            priority=priority,
            sort_order=(max_order.sort_order + 1) if max_order else 0,
        )
        s.add(todo)
        s.commit()
        return _todo_to_dict(todo)


def update_todo(user_id: int, todo_id: int, **fields) -> dict | None:
    """更新待办（title/note/due_date/status/priority/sort_order）。"""
    allowed = {"title", "note", "due_date", "status", "priority", "sort_order"}
    with base.SessionLocal() as s:
        todo = s.query(Todo).filter(Todo.id == todo_id, Todo.user_id == user_id).first()
        if todo is None:
            return None
        for k, v in fields.items():
            if k in allowed and v is not None:
                setattr(todo, k, v)
        if todo.status == "done" and todo.completed_ts is None:
            todo.completed_ts = _utcnow()
        if todo.status == "open":
            todo.completed_ts = None
        s.commit()
        return _todo_to_dict(todo)


def delete_todo(user_id: int, todo_id: int) -> bool:
    with base.SessionLocal() as s:
        todo = s.query(Todo).filter(Todo.id == todo_id, Todo.user_id == user_id).first()
        if todo is None:
            return False
        s.delete(todo)
        s.commit()
        return True
