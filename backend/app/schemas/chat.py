"""输入输出结构定义（Pydantic）。"""
from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(default="default", max_length=64)
    request_id: str = Field(
        default_factory=lambda: uuid4().hex,
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class FeedbackRequest(BaseModel):
    answer_id: str = Field(..., min_length=1, max_length=64)
    helpful: bool
    note: str = Field(default="", max_length=1000)


class EscalateRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    context: str = Field(default="", max_length=4000)
    answer_id: str = Field(default="", max_length=64)


class FaqCreateRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    answer: str = Field(..., min_length=1, max_length=8000)
    source_url: str = Field(default="", max_length=512)


class LoginRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=512)
    state: str = Field(default="", max_length=128)


class InviteLoginRequest(BaseModel):
    invite_code: str = Field(..., min_length=1, max_length=64)
    nickname: str = Field(default="", max_length=64)


class InviteGenerateRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=100)
    note: str = Field(default="", max_length=256)


class InviteRevokeRequest(BaseModel):
    invite_code: str = Field(..., min_length=1, max_length=64)
