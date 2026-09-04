"""关键同事测试（seed + 列表 + 标签 + 简介/草稿兜底）。"""
from app.db import base
from app.db.models import Contact
from app.services.contacts import (
    add_label,
    contact_intro,
    draft_message,
    get_contact,
    list_contacts,
    match_contacts,
    seed_contacts,
)


def test_seed_contacts_idempotent():
    seed_contacts()
    seed_contacts()
    with base.SessionLocal() as s:
        assert s.query(Contact).count() == 10


def test_list_contacts():
    seed_contacts()
    items = list_contacts()
    assert len(items) == 10
    assert items[0]["name"] == "陈屿"
    assert "mentor" in items[0]["duty"]
    assert items[0]["labels"] == []


def test_add_label_and_list():
    seed_contacts()
    contact_id = list_contacts()[0]["id"]
    assert add_label(1, contact_id, "技术问题找他")["added"] is True
    # 重复标签不重复添加
    assert add_label(1, contact_id, "技术问题找他")["added"] is False

    items = list_contacts(user_id=1)
    assert "技术问题找他" in items[0]["labels"]
    # 其他用户看不到该标签
    assert list_contacts(user_id=2)[0]["labels"] == []


def test_contact_intro_fallback(monkeypatch):
    seed_contacts()
    c = get_contact(list_contacts()[0]["id"])
    intro = contact_intro(c, "新同事")
    assert c.name in intro
    assert c.duty in intro


def test_draft_message_fallback():
    seed_contacts()
    c = get_contact(list_contacts()[0]["id"])
    msg = draft_message(c, "小明")
    assert c.name in msg
    assert "小明" in msg


def test_match_contacts_by_keyword():
    seed_contacts()
    assert match_contacts("报销找谁")[0]["name"] == "林晓"
    assert match_contacts("生产环境权限怎么申请")[0]["name"] == "王立"
    assert match_contacts("提测流程")[0]["name"] == "孙凯"
    assert match_contacts("今天天气怎么样") == []
