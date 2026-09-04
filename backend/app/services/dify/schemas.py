"""InTeam 与 Dify Chatflow 之间的结构化输出契约。"""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .errors import DifyProtocolError


AnswerStatus = Literal["reliable", "limited", "not_found", "blocked"]
ActionType = Literal["read", "ask", "prepare", "practice", "review", "other"]
DueHint = Literal["today", "within_3_days", "this_week", "no_date"]
KNOWN_CONTACT_KEYS = frozenset(
    {
        "chen-mo",
        "lin-qiao",
        "su-wan",
        "zhou-ning",
        "he-chuan",
        "xu-che",
        "gao-yan",
        "luo-qing",
        "tang-wei",
    }
)
KNOWN_TOPIC_KEYS = frozenset(
    {
        "today_start",
        "company_business",
        "my_role",
        "current_project",
        "team_collaboration",
        "common_processes",
    }
)


class ActionSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    client_key: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=240)
    action_type: ActionType
    due_hint: DueHint
    topic_key: str | None = Field(default=None, max_length=64)
    related_contact_key: str | None = Field(default=None, max_length=64)
    source: Literal["agent_candidate"]

    @field_validator("topic_key")
    @classmethod
    def validate_topic_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned not in KNOWN_TOPIC_KEYS:
            raise ValueError("unknown onboarding topic key")
        return cleaned

    @field_validator("related_contact_key")
    @classmethod
    def validate_related_contact_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned not in KNOWN_CONTACT_KEYS:
            raise ValueError("unknown related contact key")
        return cleaned


class WorkflowOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_status: AnswerStatus
    suggested_questions: list[str] = Field(max_length=3)
    action_suggestions: list[ActionSuggestion] = Field(max_length=3)
    related_contact_keys: list[str] = Field(max_length=5)

    @field_validator("suggested_questions")
    @classmethod
    def validate_questions(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            item = value.strip()
            if not item or len(item) > 80:
                raise ValueError("suggested question must contain 1-80 characters")
            cleaned.append(item)
        return cleaned

    @field_validator("related_contact_keys")
    @classmethod
    def validate_contact_keys(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 64 for value in cleaned):
            raise ValueError("contact key must contain 1-64 characters")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("contact keys must be unique")
        if not set(cleaned) <= KNOWN_CONTACT_KEYS:
            raise ValueError("unknown contact key")
        return cleaned


def _decode_json_value(value: Any, expected_type: type) -> Any:
    if not isinstance(value, str):
        return value
    if expected_type is str:
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise DifyProtocolError("Chatflow output contains invalid JSON") from exc


def parse_workflow_outputs(raw: Any) -> WorkflowOutputs:
    if not isinstance(raw, dict):
        raise DifyProtocolError("Chatflow outputs must be an object")

    normalized = dict(raw)
    normalized["suggested_questions"] = _decode_json_value(
        normalized.get("suggested_questions"), list
    )
    normalized["action_suggestions"] = _decode_json_value(
        normalized.get("action_suggestions"), list
    )
    normalized["related_contact_keys"] = _decode_json_value(
        normalized.get("related_contact_keys"), list
    )
    try:
        return WorkflowOutputs.model_validate(normalized)
    except ValidationError as exc:
        raise DifyProtocolError("Chatflow outputs failed validation") from exc
