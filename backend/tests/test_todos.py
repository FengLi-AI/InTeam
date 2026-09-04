"""待办事项测试。"""
from app.db import base
from app.db.models import Todo
from app.services.todos import (
    create_todo,
    delete_todo,
    list_todos,
    seed_todos_for_user,
    update_todo,
)


def test_seed_todos_idempotent():
    seed_todos_for_user(1)
    seed_todos_for_user(1)
    with base.SessionLocal() as s:
        assert s.query(Todo).filter(Todo.user_id == 1).count() == 7


def test_list_todos_auto_seed():
    items = list_todos(1)
    assert len(items) == 7
    assert all(it["due_date"] for it in items)


def test_create_update_delete():
    item = create_todo(1, "写周报", due_date="2026-08-30", priority=1)
    assert item["title"] == "写周报"

    updated = update_todo(1, item["id"], status="done")
    assert updated["status"] == "done"
    assert updated["completed_ts"] if "completed_ts" in updated else True

    assert delete_todo(1, item["id"]) is True
    assert delete_todo(1, item["id"]) is False


def test_update_missing_returns_none():
    assert update_todo(1, 999999, status="done") is None
