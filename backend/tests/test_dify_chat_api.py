from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.core import config
from app.db import base
from app.db.models import AgentSuggestion
from app.main import app
from app.services.invite import create_invites
from app.services.dify.client import DifyClient
from app.services.dify.chat import dify_sse_events
from app.services.dify.events import DifyEvent
from app.services.dify.tasks import task_registry


def _events(body: str) -> list[dict]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


def test_chat_route_uses_dify_and_keeps_user_scoped_conversation(
    auth_client, monkeypatch
) -> None:
    monkeypatch.setattr(config.settings, "chat_provider", "dify")
    monkeypatch.setattr(config.settings, "dify_app_api_key", "test-app-key")
    calls: list[str | None] = []

    def fake_stream_chat(
        self,
        *,
        query: str,
        user: str,
        inputs: dict,
        conversation_id: str | None = None,
    ):
        del self
        calls.append(conversation_id)
        assert user.startswith("inteam-user-")
        assert inputs == {}
        yield DifyEvent("workflow_started", {"event": "workflow_started", "task_id": "private-task"})
        yield DifyEvent(
            "node_started",
            {"event": "node_started", "data": {"node_type": "knowledge-retrieval"}},
        )
        yield DifyEvent(
            "message",
            {
                "event": "message",
                "answer": f"回答：{query}",
                "message_id": "dify-message-1",
                "conversation_id": "dify-conversation-1",
            },
        )
        yield DifyEvent(
            "workflow_finished",
            {"event": "workflow_finished", "data": {"status": "succeeded", "outputs": {}}},
        )

    monkeypatch.setattr(DifyClient, "stream_chat", fake_stream_chat)

    first = auth_client.post(
        "/api/v1/chat", json={"question": "公司产品是什么？", "session_id": "web"}
    )
    second = auth_client.post(
        "/api/v1/chat", json={"question": "继续介绍", "session_id": "web"}
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == [None, "dify-conversation-1"]
    first_events = _events(first.text)
    assert [item["type"] for item in first_events] == ["status", "status", "chunk", "done"]
    done = first_events[-1]
    assert done["answer"] == "回答：公司产品是什么？"
    assert done["conversation_id"] == "web"
    assert done["suggested_questions"] == []
    assert done["action_suggestions"] == []
    assert "sources" not in done
    assert "task_id" not in done
    assert "dify-message-1" not in first.text

    feedback = auth_client.post(
        "/api/v1/feedback", json={"answer_id": done["answer_id"], "helpful": True}
    )
    assert feedback.status_code == 200


def test_same_local_session_id_is_isolated_between_users(auth_client, monkeypatch) -> None:
    monkeypatch.setattr(config.settings, "chat_provider", "dify")
    monkeypatch.setattr(config.settings, "dify_app_api_key", "test-app-key")
    calls: list[tuple[str, str | None]] = []

    def fake_stream_chat(
        self,
        *,
        query: str,
        user: str,
        inputs: dict,
        conversation_id: str | None = None,
    ):
        del self, query, inputs
        calls.append((user, conversation_id))
        yield DifyEvent(
            "message",
            {
                "event": "message",
                "answer": "已回答",
                "message_id": f"message-{user}",
                "conversation_id": f"conversation-{user}",
            },
        )
        yield DifyEvent(
            "workflow_finished",
            {"event": "workflow_finished", "data": {"status": "succeeded", "outputs": {}}},
        )

    monkeypatch.setattr(DifyClient, "stream_chat", fake_stream_chat)

    assert auth_client.post(
        "/api/v1/chat", json={"question": "用户一", "session_id": "web"}
    ).status_code == 200
    with TestClient(app) as other_client:
        code = create_invites(1, "dify-isolation")[0]
        assert other_client.post(
            "/api/v1/auth/invite", json={"invite_code": code, "nickname": "用户二"}
        ).status_code == 200
        assert other_client.post(
            "/api/v1/chat", json={"question": "用户二", "session_id": "web"}
        ).status_code == 200

    assert len(calls) == 2
    assert calls[0][0] != calls[1][0]
    assert calls[0][1] is None
    assert calls[1][1] is None


def test_valid_dify_action_suggestion_is_persisted_as_pending_candidate(
    auth_client, monkeypatch
) -> None:
    monkeypatch.setattr(config.settings, "chat_provider", "dify")
    monkeypatch.setattr(config.settings, "dify_app_api_key", "test-app-key")

    def fake_stream_chat(
        self,
        *,
        query: str,
        user: str,
        inputs: dict,
        conversation_id: str | None = None,
    ):
        del self, query, user, inputs, conversation_id
        yield DifyEvent(
            "message",
            {
                "event": "message",
                "answer": "建议先阅读项目背景。",
                "message_id": "dify-message-action",
                "conversation_id": "dify-conversation-action",
            },
        )
        yield DifyEvent(
            "workflow_finished",
            {
                "event": "workflow_finished",
                "data": {
                    "status": "succeeded",
                    "outputs": {
                        "answer_status": "reliable",
                        "suggested_questions": ["当前项目有哪些风险？"],
                        "action_suggestions": [
                            {
                                "client_key": "chat-action-1",
                                "title": "阅读北辰计划项目背景",
                                "reason": "先理解项目目标再参与评审",
                                "action_type": "read",
                                "due_hint": "within_3_days",
                                "topic_key": "current_project",
                                "related_contact_key": "lin-qiao",
                                "source": "agent_candidate",
                            }
                        ],
                        "related_contact_keys": ["lin-qiao"],
                    },
                },
            },
        )

    monkeypatch.setattr(DifyClient, "stream_chat", fake_stream_chat)
    response = auth_client.post(
        "/api/v1/chat",
        json={"question": "我接下来做什么？", "session_id": "action-session"},
    )
    assert response.status_code == 200
    done = _events(response.text)[-1]
    candidate = done["action_suggestions"][0]
    assert candidate["id"] > 0
    assert candidate["decision"] == "pending"
    assert candidate["topic_key"] == "current_project"

    plan = auth_client.get("/api/v1/actions")
    assert plan.status_code == 200
    assert plan.json()["suggestions"][0]["id"] == candidate["id"]

    with base.SessionLocal() as session:
        stored = session.get(AgentSuggestion, candidate["id"])
        assert stored is not None
        assert stored.chat_message_id is not None


def test_stop_route_resolves_private_task_server_side(auth_client, monkeypatch) -> None:
    user_id = int(auth_client.get("/api/v1/me").json()["user"]["id"])
    request_id = "request-stop-123"
    task_registry.begin(user_id, request_id)
    assert task_registry.attach_task(user_id, request_id, "private-dify-task") is False
    calls: list[tuple[str, str]] = []

    def fake_stop(self, *, task_id: str, user: str) -> bool:
        del self
        calls.append((task_id, user))
        return True

    monkeypatch.setattr(DifyClient, "stop", fake_stop)
    response = auth_client.post(f"/api/v1/chat/{request_id}/stop")
    assert response.status_code == 200
    assert response.json() == {"status": "stopped"}
    assert calls == [("private-dify-task", f"inteam-user-{user_id}")]
    assert "private-dify-task" not in response.text


def test_stop_route_handles_pending_task_and_enforces_user_scope(auth_client) -> None:
    user_id = int(auth_client.get("/api/v1/me").json()["user"]["id"])
    request_id = "request-pending-123"
    task_registry.begin(user_id, request_id)

    with TestClient(app) as other_client:
        code = create_invites(1, "stop-isolation")[0]
        assert other_client.post(
            "/api/v1/auth/invite", json={"invite_code": code, "nickname": "用户二"}
        ).status_code == 200
        assert other_client.post(f"/api/v1/chat/{request_id}/stop").status_code == 404

    response = auth_client.post(f"/api/v1/chat/{request_id}/stop")
    assert response.status_code == 200
    assert response.json() == {"status": "stopping"}
    assert task_registry.attach_task(user_id, request_id, "late-task") is True


def test_chat_request_rejects_invalid_local_request_id(auth_client) -> None:
    response = auth_client.post(
        "/api/v1/chat",
        json={"question": "测试", "session_id": "web", "request_id": "含空格"},
    )
    assert response.status_code == 422


def test_closing_local_stream_stops_known_dify_task(auth_client, monkeypatch) -> None:
    monkeypatch.setattr(config.settings, "dify_app_api_key", "test-app-key")
    user_id = int(auth_client.get("/api/v1/me").json()["user"]["id"])
    stop_calls: list[tuple[str, str]] = []

    def fake_stream_chat(
        self,
        *,
        query: str,
        user: str,
        inputs: dict,
        conversation_id: str | None = None,
    ):
        del self, query, user, inputs, conversation_id
        yield DifyEvent(
            "workflow_started",
            {"event": "workflow_started", "task_id": "task-close-1"},
        )
        yield DifyEvent(
            "message",
            {"event": "message", "answer": "尚未完成", "task_id": "task-close-1"},
        )

    def fake_stop(self, *, task_id: str, user: str) -> bool:
        del self
        stop_calls.append((task_id, user))
        return True

    monkeypatch.setattr(DifyClient, "stream_chat", fake_stream_chat)
    monkeypatch.setattr(DifyClient, "stop", fake_stop)
    stream = dify_sse_events(
        "测试停止",
        local_session_id="stop-session",
        local_request_id="request-close-123",
        user_id=user_id,
    )
    assert '"phase": "accepted"' in next(stream)
    stream.close()
    assert stop_calls == [("task-close-1", f"inteam-user-{user_id}")]
