"""候选建议和正式行动请求契约。"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ActionCreateRequest(BaseModel):
    suggestion_id: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=256)
    reason: str = Field(default="", max_length=1000)
    due_date: str = Field(default="", max_length=10)
    topic_key: str = Field(default="", max_length=64)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, value: str) -> str:
        value = value.strip()
        if value:
            date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def require_one_source(self):
        if self.suggestion_id is None and not self.title:
            raise ValueError("title is required for a manual action")
        if self.suggestion_id is not None and self.title:
            raise ValueError("title must not override an agent suggestion")
        return self


class ActionUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    due_date: str | None = Field(default=None, max_length=10)
    status: Literal["open", "done"] | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if value:
            date.fromisoformat(value)
        return value
