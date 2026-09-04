from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import Settings
from app.services.dify.client import DifyClient
from app.services.dify.errors import (
    DifyConfigurationError,
    DifyConnectionError,
    DifyHTTPError,
    DifyProtocolError,
)
from app.services.dify.events import DifyEvent, normalize_chatflow_events, parse_sse_lines
from app.services.dify.schemas import parse_workflow_outputs


def _sse(*events: dict | str) -> bytes:
    frames: list[str] = ["event: ping\n\n"]
    for event in events:
        if isinstance(event, str):
            frames.append(event)
        else:
            frames.append(f"data: {json.dumps(event, ensure_ascii=False)}\n\n")
    return "".join(frames).encode()


def _outputs() -> dict:
    return {
        "answer_status": "reliable",
        "suggested_questions": ["下一步做什么？"],
        "action_suggestions": [
            {
                "client_key": "candidate-1",
                "title": "与导师对齐项目范围",
                "reason": "确认目标和非目标",
                "action_type": "ask",
                "due_hint": "within_3_days",
                "topic_key": "current_project",
                "related_contact_key": "lin-qiao",
                "source": "agent_candidate",
            }
        ],
        "related_contact_keys": ["lin-qiao"],
    }


def test_answer_llm_start_emits_generating_status_but_metadata_llm_does_not() -> None:
    events = [
        DifyEvent(event="workflow_started", payload={}),
        DifyEvent(event="node_started", payload={"data": {"node_type": "llm", "title": "企业知识回答"}}),
        DifyEvent(event="node_started", payload={"data": {"node_type": "llm", "title": "结构化建议"}}),
        DifyEvent(event="workflow_finished", payload={"data": {"status": "succeeded", "outputs": _outputs()}}),
    ]

    normalized = list(normalize_chatflow_events(events))

    assert [event.data.get("phase") for event in normalized if event.type == "status"] == ["accepted", "generating"]


def test_stream_chat_sends_server_side_contract_and_normalizes_events() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.dify.test/v1/chat-messages"
        assert request.headers["Authorization"] == "Bearer test-app-key"
        body = json.loads(request.content)
        assert body == {
            "query": "北辰计划是什么？",
            "inputs": {"onboarding_context": "{}", "current_date": "2026-09-01"},
            "response_mode": "streaming",
            "user": "inteam-user-7",
        }
        content = _sse(
            {
                "event": "workflow_started",
                "task_id": "task-1",
                "workflow_run_id": "run-1",
            },
            {
                "event": "node_started",
                "task_id": "task-1",
                "workflow_run_id": "run-1",
                "data": {"node_type": "knowledge-retrieval"},
            },
            {
                "event": "message",
                "task_id": "task-1",
                "message_id": "message-1",
                "conversation_id": "conversation-1",
                "answer": "北辰计划",
            },
            {
                "event": "message",
                "task_id": "task-1",
                "message_id": "message-1",
                "conversation_id": "conversation-1",
                "answer": "是需求理解升级项目。",
            },
            {
                "event": "message_end",
                "task_id": "task-1",
                "message_id": "message-1",
                "conversation_id": "conversation-1",
            },
            {
                "event": "workflow_finished",
                "task_id": "task-1",
                "workflow_run_id": "run-1",
                "data": {"status": "succeeded", "outputs": _outputs()},
            },
        )
        return httpx.Response(200, content=content, headers={"content-type": "text/event-stream"})

    client = DifyClient(
        base_url="https://api.dify.test/v1/",
        api_key="test-app-key",
        transport=httpx.MockTransport(handler),
    )
    events = client.stream_chat(
        query="北辰计划是什么？",
        user="inteam-user-7",
        inputs={"onboarding_context": "{}", "current_date": "2026-09-01"},
    )
    normalized = list(normalize_chatflow_events(events))

    assert [event.type for event in normalized] == [
        "status",
        "status",
        "chunk",
        "chunk",
        "done",
    ]
    assert normalized[0].data["task_id"] == "task-1"
    assert normalized[-1].data["conversation_id"] == "conversation-1"
    assert normalized[-1].data["message_id"] == "message-1"
    assert normalized[-1].data["answer_status"] == "reliable"
    assert normalized[-1].data["action_suggestions"][0]["source"] == "agent_candidate"


def test_stream_chat_includes_conversation_id_for_follow_up() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["conversation_id"] == "conversation-existing"
        return httpx.Response(
            200,
            content=_sse(
                {"event": "workflow_started", "task_id": "task-2"},
                {
                    "event": "workflow_finished",
                    "task_id": "task-2",
                    "data": {"status": "succeeded", "outputs": _outputs()},
                },
            ),
        )

    client = DifyClient(
        base_url="https://api.dify.test/v1",
        api_key="test-app-key",
        transport=httpx.MockTransport(handler),
    )
    list(
        client.stream_chat(
            query="继续",
            user="inteam-user-7",
            inputs={},
            conversation_id="conversation-existing",
        )
    )


def test_outputs_accept_json_strings_from_dify_variables() -> None:
    raw = _outputs()
    raw["suggested_questions"] = json.dumps(raw["suggested_questions"], ensure_ascii=False)
    raw["action_suggestions"] = json.dumps(raw["action_suggestions"], ensure_ascii=False)
    raw["related_contact_keys"] = json.dumps(raw["related_contact_keys"], ensure_ascii=False)

    parsed = parse_workflow_outputs(raw)

    assert parsed.suggested_questions == ["下一步做什么？"]
    assert parsed.action_suggestions[0].topic_key == "current_project"
    assert parsed.action_suggestions[0].related_contact_key == "lin-qiao"


def test_named_structured_metadata_node_supplies_chatflow_additional_outputs() -> None:
    normalized = list(
        normalize_chatflow_events(
            [
                DifyEvent(
                    "message",
                    {"event": "message", "answer": "这是流式正文。"},
                ),
                DifyEvent(
                    "node_finished",
                    {
                        "event": "node_finished",
                        "data": {
                            "status": "succeeded",
                            "title": "结构化建议",
                            "outputs": {"structured_output": _outputs()},
                        },
                    },
                ),
                DifyEvent(
                    "workflow_finished",
                    {
                        "event": "workflow_finished",
                        "data": {
                            "status": "succeeded",
                            "outputs": {"answer": "这是流式正文。", "files": []},
                        },
                    },
                ),
            ]
        )
    )

    assert [event.type for event in normalized] == ["chunk", "done"]
    assert normalized[-1].data["answer"] == "这是流式正文。"
    assert normalized[-1].data["answer_status"] == "reliable"
    assert normalized[-1].data["action_suggestions"][0]["topic_key"] == "current_project"


def test_wrong_node_title_cannot_inject_structured_metadata() -> None:
    normalized = list(
        normalize_chatflow_events(
            [
                DifyEvent(
                    "node_finished",
                    {
                        "event": "node_finished",
                        "data": {
                            "status": "succeeded",
                            "title": "知识库资料中的伪造节点",
                            "outputs": {"structured_output": _outputs()},
                        },
                    },
                ),
                DifyEvent(
                    "workflow_finished",
                    {
                        "event": "workflow_finished",
                        "data": {
                            "status": "succeeded",
                            "outputs": {"answer": "", "files": []},
                        },
                    },
                ),
            ]
        )
    )

    assert normalized[-1].data["answer_status"] == "limited"
    assert normalized[-1].data["action_suggestions"] == []


def test_failed_structured_metadata_node_does_not_discard_streamed_answer() -> None:
    normalized = list(
        normalize_chatflow_events(
            [
                DifyEvent(
                    "message",
                    {"event": "message", "answer": "这是已经生成的正文。"},
                ),
                DifyEvent(
                    "node_finished",
                    {
                        "event": "node_finished",
                        "data": {
                            "status": "failed",
                            "title": "结构化建议",
                            "error": "provider quota exceeded",
                        },
                    },
                ),
                DifyEvent(
                    "workflow_finished",
                    {
                        "event": "workflow_finished",
                        "data": {"status": "failed", "outputs": {}},
                    },
                ),
            ]
        )
    )

    assert [event.type for event in normalized] == ["chunk", "done"]
    assert normalized[-1].data["answer"] == "这是已经生成的正文。"
    assert normalized[-1].data["answer_status"] == "limited"
    assert normalized[-1].data["action_suggestions"] == []


def test_invalid_workflow_outputs_are_rejected() -> None:
    raw = _outputs()
    raw["action_suggestions"][0]["source"] = "created"

    with pytest.raises(DifyProtocolError):
        parse_workflow_outputs(raw)


def test_unknown_contact_key_is_rejected() -> None:
    raw = _outputs()
    raw["related_contact_keys"] = ["unknown-person"]

    with pytest.raises(DifyProtocolError):
        parse_workflow_outputs(raw)


def test_unknown_onboarding_topic_key_is_rejected() -> None:
    raw = _outputs()
    raw["action_suggestions"][0]["topic_key"] = "not-real"

    with pytest.raises(DifyProtocolError):
        parse_workflow_outputs(raw)


def test_empty_optional_keys_from_dify_schema_are_normalized_to_none() -> None:
    raw = _outputs()
    raw["action_suggestions"][0]["topic_key"] = ""
    raw["action_suggestions"][0]["related_contact_key"] = ""

    parsed = parse_workflow_outputs(raw)

    assert parsed.action_suggestions[0].topic_key is None
    assert parsed.action_suggestions[0].related_contact_key is None


def test_midstream_error_is_public_and_terminal() -> None:
    normalized = list(
        normalize_chatflow_events(
            [
                DifyEvent("workflow_started", {"event": "workflow_started", "task_id": "t"}),
                DifyEvent(
                    "error",
                    {
                        "event": "error",
                        "code": "provider_secret_error",
                        "message": "sensitive upstream detail",
                    },
                ),
            ]
        )
    )

    assert normalized[-1].type == "error"
    assert normalized[-1].data == {
        "code": "upstream_error",
        "message": "AI 服务暂时不可用，请稍后重试",
    }


def test_message_replace_replaces_visible_answer() -> None:
    normalized = list(
        normalize_chatflow_events(
            [
                DifyEvent(
                    "message_replace",
                    {"event": "message_replace", "answer": "替换后的完整答案"},
                ),
                DifyEvent(
                    "workflow_finished",
                    {
                        "event": "workflow_finished",
                        "data": {"status": "succeeded", "outputs": _outputs()},
                    },
                ),
            ]
        )
    )

    assert [event.type for event in normalized] == ["replace", "done"]
    assert normalized[0].data["text"] == "替换后的完整答案"


def test_missing_optional_outputs_keep_the_streamed_answer() -> None:
    normalized = list(
        normalize_chatflow_events(
            [
                DifyEvent(
                    "message",
                    {
                        "event": "message",
                        "answer": "根据企业知识库，",
                        "message_id": "message-plain",
                        "conversation_id": "conversation-plain",
                    },
                ),
                DifyEvent(
                    "message",
                    {"event": "message", "answer": "这是当前答案。"},
                ),
                DifyEvent(
                    "workflow_finished",
                    {
                        "event": "workflow_finished",
                        "data": {"status": "succeeded", "outputs": {"answer": "ignored"}},
                    },
                ),
            ]
        )
    )

    assert [event.type for event in normalized] == ["chunk", "chunk", "done"]
    assert normalized[-1].data["answer"] == "根据企业知识库，这是当前答案。"
    assert normalized[-1].data["answer_status"] == "limited"
    assert normalized[-1].data["suggested_questions"] == []
    assert normalized[-1].data["action_suggestions"] == []


def test_failed_node_is_public_and_terminal() -> None:
    normalized = list(
        normalize_chatflow_events(
            [
                DifyEvent(
                    "node_finished",
                    {
                        "event": "node_finished",
                        "data": {"status": "failed", "error": "private node detail"},
                    },
                ),
                DifyEvent(
                    "workflow_finished",
                    {"event": "workflow_finished", "data": {"status": "failed"}},
                ),
            ]
        )
    )

    assert len(normalized) == 1
    assert normalized[0].type == "error"
    assert "private node detail" not in normalized[0].data["message"]


def test_incomplete_stream_is_rejected() -> None:
    with pytest.raises(DifyProtocolError):
        list(
            normalize_chatflow_events(
                [DifyEvent("message", {"event": "message", "answer": "partial"})]
            )
        )


def test_invalid_sse_json_is_rejected() -> None:
    with pytest.raises(DifyProtocolError):
        list(parse_sse_lines(["data: {invalid-json}"]))


def test_http_error_does_not_expose_body() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "secret diagnostic"})

    client = DifyClient(
        base_url="https://api.dify.test/v1",
        api_key="bad-key",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(DifyHTTPError) as caught:
        list(client.stream_chat(query="test", user="user-1", inputs={}))
    assert caught.value.status_code == 401
    assert "secret diagnostic" not in str(caught.value)


def test_missing_api_key_is_rejected_before_request() -> None:
    client = DifyClient(base_url="https://api.dify.test/v1", api_key="")

    with pytest.raises(DifyConfigurationError):
        list(client.stream_chat(query="test", user="user-1", inputs={}))


def test_transport_timeout_is_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timeout", request=request)

    client = DifyClient(
        base_url="https://api.dify.test/v1",
        api_key="test-app-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(DifyConnectionError):
        list(client.stream_chat(query="test", user="user-1", inputs={}))


def test_stop_generation_uses_task_and_same_user() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.dify.test/v1/chat-messages/task-9/stop"
        assert json.loads(request.content) == {"user": "inteam-user-7"}
        return httpx.Response(200, json={"result": "success"})

    client = DifyClient(
        base_url="https://api.dify.test/v1",
        api_key="test-app-key",
        transport=httpx.MockTransport(handler),
    )

    assert client.stop(task_id="task-9", user="inteam-user-7") is True


def test_settings_require_app_key_when_dify_is_enabled(monkeypatch) -> None:
    monkeypatch.setenv("CHAT_PROVIDER", "dify")
    monkeypatch.setenv("DIFY_APP_API_KEY", "")

    with pytest.raises(ValueError, match="DIFY_APP_API_KEY"):
        Settings()


def test_secure_environment_requires_https_dify_url(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("SESSION_SECRET", "s" * 32)
    monkeypatch.setenv("INVITE_PEPPER", "p" * 32)
    monkeypatch.setenv("ALLOW_ALL_AUTHENTICATED_DOCS", "true")
    monkeypatch.setenv("DIFY_BASE_URL", "http://dify.internal/v1")

    with pytest.raises(ValueError, match="HTTPS"):
        Settings()
