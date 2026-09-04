"""转人工 / 反馈 / FAQ / 统计 API 测试。"""
import json


def _answer_id(client) -> str:
    response = client.post("/api/v1/chat", json={"question": "命名规范是什么"})
    for line in response.text.splitlines():
        if line.startswith("data: "):
            payload = json.loads(line.removeprefix("data: "))
            if payload.get("type") == "done":
                return payload["answer_id"]
    raise AssertionError("chat 应返回 done 事件")


def test_feedback_api(auth_client):
    r = auth_client.post(
        "/api/v1/feedback", json={"answer_id": _answer_id(auth_client), "helpful": True}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["blind_spot"] is False


def test_feedback_api_rejects_invalid(auth_client):
    r = auth_client.post("/api/v1/feedback", json={"answer_id": "", "helpful": True})
    assert r.status_code == 422


def test_escalate_api_mock_mode(auth_client):
    """开发默认：未配置 mentor → 模拟发送，sent=True 且 mock=True。"""
    r = auth_client.post(
        "/api/v1/escalate",
        json={"question": "问题", "context": "ctx"},
        headers={"X-Idempotency-Key": "pytest-ticket-1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["sent"] is True
    assert body["mock"] is True
    assert body["ticket_id"]


def test_escalate_mock_messages_api(auth_client, service_auth):
    auth_client.post("/api/v1/escalate", json={"question": "问题"})
    r = auth_client.get("/api/v1/escalate/mock-messages", headers=service_auth)
    assert r.status_code == 200
    assert r.json()["items"]


def test_faq_api_flow(auth_client, service_auth):
    r = auth_client.post(
        "/api/v1/faq",
        json={"question": "怎么连数据库", "answer": "找 DBA", "source_url": "https://x"},
        headers=service_auth,
    )
    assert r.status_code == 200
    faq_id = r.json()["faq_id"]

    # 候选未确认，检索不到
    r = auth_client.get("/api/v1/faq", params={"q": "数据库"})
    assert r.json()["items"] == []

    # 确认后检索到
    r = auth_client.post(f"/api/v1/faq/{faq_id}/confirm", headers=service_auth)
    assert r.status_code == 200
    r = auth_client.get("/api/v1/faq", params={"q": "数据库怎么连"})
    assert r.json()["items"]


def test_faq_confirm_missing_returns_404(api_client, service_auth):
    r = api_client.post("/api/v1/faq/999999/confirm", headers=service_auth)
    assert r.status_code == 404


def test_stats_api(api_client, service_auth):
    r = api_client.get("/api/v1/stats", headers=service_auth)
    assert r.status_code == 200
    body = r.json()
    assert "helpful_rate" in body
    assert "blind_spots" in body
