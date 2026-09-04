"""解析 Dify SSE，并转换为 InTeam 稳定事件。"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from .errors import DifyProtocolError
from .schemas import WorkflowOutputs, parse_workflow_outputs


LOG = logging.getLogger("inteam.dify.events")
STRUCTURED_METADATA_NODE_TITLES = frozenset({"结构化建议", "InTeam Structured Metadata"})


@dataclass(frozen=True)
class DifyEvent:
    event: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class InTeamStreamEvent:
    type: str
    data: dict[str, Any]


def parse_sse_lines(lines: Iterable[str]) -> Iterator[DifyEvent]:
    """Dify 每个非 ping 事件都位于一行 `data: {json}` 中。"""
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line == "event: ping" or not line.startswith("data:"):
            continue
        raw_data = line.removeprefix("data:").strip()
        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError as exc:
            raise DifyProtocolError("Dify returned invalid SSE JSON") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("event"), str):
            raise DifyProtocolError("Dify SSE event is missing event type")
        yield DifyEvent(event=payload["event"], payload=payload)


def _status(phase: str, **extra: Any) -> InTeamStreamEvent:
    return InTeamStreamEvent(type="status", data={"phase": phase, **extra})


def _public_error(code: str, message: str) -> InTeamStreamEvent:
    return InTeamStreamEvent(type="error", data={"code": code, "message": message})


def normalize_chatflow_events(events: Iterable[DifyEvent]) -> Iterator[InTeamStreamEvent]:
    """映射 Chatflow 事件；正文可用时，附加 outputs 损坏不会阻断回答。"""
    task_id: str | None = None
    workflow_run_id: str | None = None
    message_id: str | None = None
    conversation_id: str | None = None
    answer_parts: list[str] = []
    structured_metadata: WorkflowOutputs | None = None
    structured_metadata_failed = False
    finished = False

    for item in events:
        payload = item.payload
        task_id = payload.get("task_id") or task_id
        workflow_run_id = payload.get("workflow_run_id") or workflow_run_id
        message_id = payload.get("message_id") or message_id
        conversation_id = payload.get("conversation_id") or conversation_id

        if item.event == "workflow_started":
            yield _status(
                "accepted",
                task_id=task_id,
                workflow_run_id=workflow_run_id,
            )
            continue

        if item.event == "node_started":
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            node_type = str(data.get("node_type", "")).lower()
            node_title = str(data.get("title") or "")
            if "knowledge" in node_type or "retriev" in node_type:
                yield _status("retrieving")
            elif node_type == "llm" and node_title not in STRUCTURED_METADATA_NODE_TITLES:
                yield _status("generating")
            continue

        if item.event == "message":
            answer = payload.get("answer")
            if isinstance(answer, str) and answer:
                answer_parts.append(answer)
                yield InTeamStreamEvent(type="chunk", data={"text": answer})
            continue

        if item.event == "message_replace":
            answer = payload.get("answer")
            if isinstance(answer, str):
                answer_parts = [answer]
                yield InTeamStreamEvent(type="replace", data={"text": answer})
            continue

        if item.event == "message_end":
            continue

        if item.event == "error":
            if structured_metadata_failed and answer_parts:
                LOG.warning(
                    "Dify structured metadata node failed after answer; "
                    "ignoring terminal upstream error"
                )
                continue
            finished = True
            yield _public_error("upstream_error", "AI 服务暂时不可用，请稍后重试")
            return

        if item.event == "node_finished":
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            node_title = str(data.get("title") or "")
            if data.get("status") == "failed":
                if node_title in STRUCTURED_METADATA_NODE_TITLES and answer_parts:
                    structured_metadata_failed = True
                    LOG.warning(
                        "Dify structured metadata node failed after answer; "
                        "using safe empty metadata"
                    )
                    continue
                finished = True
                yield _public_error("workflow_failed", "回答生成失败，请稍后重试")
                return
            if node_title in STRUCTURED_METADATA_NODE_TITLES:
                node_outputs = (
                    data.get("outputs") if isinstance(data.get("outputs"), dict) else {}
                )
                raw_metadata = node_outputs.get("structured_output")
                if raw_metadata is None:
                    raw_metadata = node_outputs.get("text")
                if isinstance(raw_metadata, str):
                    try:
                        raw_metadata = json.loads(raw_metadata)
                    except json.JSONDecodeError:
                        raw_metadata = None
                if raw_metadata is not None:
                    try:
                        structured_metadata = parse_workflow_outputs(raw_metadata)
                    except DifyProtocolError:
                        LOG.warning(
                            "Dify structured metadata node output failed validation"
                        )
            continue

        if item.event == "workflow_finished":
            finished = True
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            if (
                data.get("status") not in {None, "succeeded"}
                and not (structured_metadata_failed and answer_parts)
            ):
                yield _public_error("workflow_failed", "回答生成失败，请稍后重试")
                return
            outputs = structured_metadata
            if outputs is None:
                try:
                    outputs = parse_workflow_outputs(data.get("outputs"))
                except DifyProtocolError:
                    outputs = None
            if outputs is None:
                # Dify 简化版 Chatflow 可能只流式返回正文。附加结构缺失或损坏时
                # 保守降级为空建议，不能让用户已经收到的正文在结束阶段变成错误。
                LOG.warning("Dify workflow outputs unavailable; using safe empty metadata")
                outputs = WorkflowOutputs(
                    answer_status="limited",
                    suggested_questions=[],
                    action_suggestions=[],
                    related_contact_keys=[],
                )
            yield InTeamStreamEvent(
                type="done",
                data={
                    "task_id": task_id,
                    "workflow_run_id": workflow_run_id,
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "answer": "".join(answer_parts),
                    **outputs.model_dump(),
                },
            )
            return

    if not finished:
        raise DifyProtocolError("Dify stream ended before workflow_finished")
