"""转人工测试（模拟 mentor + mock 飞书 im:message）。"""
import json

from app.core import config
from app.db import base
from app.db.models import EscalateTicket
from app.services import feishu as feishu_mod
from app.services.escalate import build_message, escalate, list_mock_messages


def test_build_message_contains_question_and_mentor_hint():
    msg = build_message("怎么连数据库", "相关线索", "摘要内容")
    assert "怎么连数据库" in msg
    assert "摘要内容" in msg
    assert "mentor" in msg


def test_escalate_mock_mode_writes_inbox(tmp_path):
    """未配置 mentor（开发默认）→ 模拟发送，工单 sent，消息进模拟收件箱。"""
    result = escalate("怎么连数据库", "ctx")
    assert result["sent"] is True
    assert result["mock"] is True
    assert result["ticket_id"]

    with base.SessionLocal() as s:
        t = s.query(EscalateTicket).one()
        assert t.status == "sent"
        assert t.message_id.startswith("mock_")

    messages = list_mock_messages()
    assert messages
    assert "怎么连数据库" in messages[-1]["text"]


def test_escalate_mock_explicit(monkeypatch, tmp_path):
    """显式 FEISHU_MENTOR_ID=mock 也走模拟。"""
    monkeypatch.setattr(config.settings, "feishu_mentor_id", "mock")
    result = escalate("问题")
    assert result["mock"] is True
    assert result["sent"] is True


def test_escalate_sends_message(monkeypatch, tmp_path):
    """配置真实 mentor + 飞书应用 → 真实发送，不进模拟收件箱。"""
    monkeypatch.setattr(config.settings, "feishu_app_id", "app")
    monkeypatch.setattr(config.settings, "feishu_app_secret", "sec")
    monkeypatch.setattr(config.settings, "feishu_mentor_id", "ou_mentor")

    sent: list[tuple] = []

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def send_message(self, receive_id, text, receive_id_type="open_id"):
            sent.append((receive_id, text, receive_id_type))
            return "om_msg_123"

    monkeypatch.setattr(feishu_mod, "FeishuClient", _FakeClient)

    result = escalate("怎么连数据库", "上下文内容")
    assert result["sent"] is True
    assert result["mock"] is False
    assert sent[0][0] == "ou_mentor"
    assert sent[0][2] == "open_id"
    assert "怎么连数据库" in sent[0][1]

    with base.SessionLocal() as s:
        t = s.query(EscalateTicket).one()
        assert t.status == "sent"
        assert t.message_id == "om_msg_123"


def test_escalate_send_failure_records_error(monkeypatch):
    monkeypatch.setattr(config.settings, "feishu_app_id", "app")
    monkeypatch.setattr(config.settings, "feishu_app_secret", "sec")
    monkeypatch.setattr(config.settings, "feishu_mentor_id", "ou_mentor")

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def send_message(self, *args, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(feishu_mod, "FeishuClient", _FakeClient)

    result = escalate("问题")
    assert result["sent"] is False
    assert result["mock"] is False
    assert result["error"]
    with base.SessionLocal() as s:
        t = s.query(EscalateTicket).one()
        assert t.status == "failed"
        assert "network down" in t.error


def test_list_mock_messages_empty(tmp_path):
    assert list_mock_messages() == []


def test_escalate_idempotency_does_not_send_twice():
    first = escalate("问题", user_id=7, idempotency_key="same-request")
    second = escalate("问题", user_id=7, idempotency_key="same-request")

    assert second["ticket_id"] == first["ticket_id"]
    assert second["deduplicated"] is True
    assert len(list_mock_messages()) == 1
