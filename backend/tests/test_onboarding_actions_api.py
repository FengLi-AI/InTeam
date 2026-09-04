from __future__ import annotations

from fastapi.testclient import TestClient

from app.db import base
from app.db.models import AgentSuggestion
from app.main import app
from app.services.invite import create_invites


def _other_user_client() -> TestClient:
    client = TestClient(app)
    code = create_invites(1, "actions-other-user")[0]
    response = client.post(
        "/api/v1/auth/invite",
        json={"invite_code": code, "nickname": "另一位用户"},
    )
    assert response.status_code == 200
    return client


def _seed_suggestion(user_id: int, client_key: str = "candidate-1") -> int:
    with base.SessionLocal() as session:
        item = AgentSuggestion(
            user_id=user_id,
            client_key=client_key,
            title="阅读北辰计划项目背景",
            reason="先理解项目目标再参与评审",
            action_type="read",
            due_hint="within_3_days",
            topic_key="current_project",
            related_contact_key="lin-qiao",
        )
        session.add(item)
        session.commit()
        return item.id


def _current_user_id(client: TestClient) -> int:
    response = client.get("/api/v1/me")
    assert response.status_code == 200
    return int(response.json()["user"]["id"])


def test_onboarding_map_lists_six_topics_and_persists_user_progress(
    auth_client,
) -> None:
    response = auth_client.get("/api/v1/onboarding-map")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 6
    assert {item["topic_key"] for item in items} == {
        "today_start",
        "company_business",
        "my_role",
        "current_project",
        "team_collaboration",
        "common_processes",
    }
    assert all(item["status"] == "not_started" for item in items)
    assert all(len(item["suggested_questions"]) == 3 for item in items)

    updated = auth_client.patch(
        "/api/v1/onboarding-map/company_business",
        json={"status": "exploring"},
    )
    assert updated.status_code == 200
    assert updated.json()["item"]["status"] == "exploring"

    with _other_user_client() as other:
        other_items = other.get("/api/v1/onboarding-map").json()["items"]
        company = next(item for item in other_items if item["topic_key"] == "company_business")
        assert company["status"] == "not_started"


def test_onboarding_map_rejects_unknown_topic(auth_client) -> None:
    response = auth_client.patch(
        "/api/v1/onboarding-map/not-real",
        json={"status": "completed"},
    )
    assert response.status_code == 404


def test_manual_action_lifecycle_syncs_topic_progress(auth_client) -> None:
    created = auth_client.post(
        "/api/v1/actions",
        json={
            "title": "阅读公司产品概览",
            "reason": "理解业务背景",
            "due_date": "2026-09-03",
            "topic_key": "company_business",
        },
    )
    assert created.status_code == 200
    item = created.json()["item"]
    assert item["source_type"] == "manual"
    assert item["status"] == "open"

    plan = auth_client.get("/api/v1/actions").json()
    assert plan["progress"] == {"done": 0, "total": 1}
    assert plan["today_focus"][0]["id"] == item["id"]

    topic = auth_client.get("/api/v1/onboarding-map").json()["items"]
    company = next(row for row in topic if row["topic_key"] == "company_business")
    assert company["status"] == "exploring"
    assert company["open_action_count"] == 1

    completed = auth_client.patch(
        f"/api/v1/actions/{item['id']}",
        json={"status": "done"},
    )
    assert completed.status_code == 200
    assert completed.json()["item"]["status"] == "done"
    company = next(
        row
        for row in auth_client.get("/api/v1/onboarding-map").json()["items"]
        if row["topic_key"] == "company_business"
    )
    assert company["status"] == "completed"
    assert company["open_action_count"] == 0

    reopened = auth_client.patch(
        f"/api/v1/actions/{item['id']}",
        json={"status": "open"},
    )
    assert reopened.status_code == 200
    company = next(
        row
        for row in auth_client.get("/api/v1/onboarding-map").json()["items"]
        if row["topic_key"] == "company_business"
    )
    assert company["status"] == "exploring"

    assert auth_client.delete(f"/api/v1/actions/{item['id']}").status_code == 200
    assert auth_client.get("/api/v1/actions").json()["actions"] == []


def test_candidate_accept_is_idempotent_and_user_scoped(auth_client) -> None:
    user_id = _current_user_id(auth_client)
    suggestion_id = _seed_suggestion(user_id)

    plan = auth_client.get("/api/v1/actions").json()
    assert plan["suggestions"][0]["id"] == suggestion_id

    first = auth_client.post(
        "/api/v1/actions",
        json={"suggestion_id": suggestion_id, "due_date": "2026-09-05"},
    )
    second = auth_client.post(
        "/api/v1/actions",
        json={"suggestion_id": suggestion_id, "due_date": "2026-09-06"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["item"]["id"] == second.json()["item"]["id"]
    assert second.json()["item"]["due_date"] == "2026-09-05"
    assert len(auth_client.get("/api/v1/actions").json()["actions"]) == 1

    with _other_user_client() as other:
        assert other.post(
            "/api/v1/actions", json={"suggestion_id": suggestion_id}
        ).status_code == 404
        assert other.patch(
            f"/api/v1/actions/{first.json()['item']['id']}",
            json={"status": "done"},
        ).status_code == 404


def test_candidate_dismiss_is_idempotent_and_cannot_then_be_accepted(
    auth_client,
) -> None:
    suggestion_id = _seed_suggestion(_current_user_id(auth_client), "candidate-dismiss")

    first = auth_client.post(f"/api/v1/suggestions/{suggestion_id}/dismiss")
    second = auth_client.post(f"/api/v1/suggestions/{suggestion_id}/dismiss")
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["item"]["decision"] == "dismissed"
    assert auth_client.post(
        "/api/v1/actions", json={"suggestion_id": suggestion_id}
    ).status_code == 409
    assert auth_client.get("/api/v1/actions").json()["suggestions"] == []


def test_action_contract_rejects_invalid_date_and_unknown_topic(auth_client) -> None:
    assert auth_client.post(
        "/api/v1/actions",
        json={"title": "错误日期", "due_date": "2026-99-99"},
    ).status_code == 422
    assert auth_client.post(
        "/api/v1/actions",
        json={"title": "未知主题", "topic_key": "not-real"},
    ).status_code == 404


def test_new_endpoints_require_auth(api_client) -> None:
    assert api_client.get("/api/v1/onboarding-map").status_code == 401
    assert api_client.get("/api/v1/actions").status_code == 401


def test_post_compatibility_routes_cover_apig_write_operations(auth_client) -> None:
    created = auth_client.post(
        "/api/v1/actions",
        json={"title": "练习需求样本标注", "topic_key": "my_role"},
    )
    assert created.status_code == 200
    action_id = created.json()["item"]["id"]

    completed = auth_client.post(
        f"/api/v1/actions/{action_id}",
        json={"status": "done"},
    )
    assert completed.status_code == 200
    assert completed.json()["item"]["status"] == "done"

    topic = auth_client.post(
        "/api/v1/onboarding-map/my_role",
        json={"status": "completed"},
    )
    assert topic.status_code == 200
    assert topic.json()["item"]["status"] == "completed"

    deleted = auth_client.post(f"/api/v1/actions/{action_id}/delete")
    assert deleted.status_code == 200
    assert auth_client.get("/api/v1/actions").json()["actions"] == []
