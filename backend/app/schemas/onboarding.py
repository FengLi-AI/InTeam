"""上手地图请求契约。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


TopicStatus = Literal["not_started", "exploring", "completed"]


class OnboardingProgressUpdate(BaseModel):
    status: TopicStatus
