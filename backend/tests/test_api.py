"""API 单元测试（mock，离线可跑；chat 走演示模式）。"""
import json


def _done_payload(body: str) -> dict:
    events = [json.loads(line.removeprefix("data: ")) for line in body.splitlines() if line.startswith("data: ")]
    return next(event for event in events if event.get("type") == "done")


def test_health(api_client):
    r = api_client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_chat_stream_returns_chunk_and_done(auth_client):
    r = auth_client.post("/api/v1/chat", json={"question": "命名规范是什么", "session_id": "t"})
    assert r.status_code == 200
    body = r.text
    assert "chunk" in body
    assert '"type": "done"' in body


def test_chat_not_found_guard(auth_client):
    r = auth_client.post("/api/v1/chat", json={"question": "火星基地在哪里"})
    body = r.text
    assert '"guard": "not_found"' in body


def test_chat_empty_question_rejected(auth_client):
    r = auth_client.post("/api/v1/chat", json={"question": ""})
    assert r.status_code == 422


def test_feedback_ok(auth_client):
    answer = auth_client.post("/api/v1/chat", json={"question": "命名规范是什么"})
    answer_id = _done_payload(answer.text)["answer_id"]
    r = auth_client.post("/api/v1/feedback", json={"answer_id": answer_id, "helpful": True})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_escalate_ok(auth_client):
    r = auth_client.post("/api/v1/escalate", json={"question": "问题", "context": "上下文"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
