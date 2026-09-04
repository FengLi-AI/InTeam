"""模型输出解析器：宽容解析 JSON，失败抛 ParseError。"""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field


class AnswerSource(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    section: str = Field(default="", max_length=256)


class AnswerResult(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)
    sources: list[AnswerSource] = Field(default_factory=list, max_length=10)
    confidence: Literal["high", "low", "none"] = "none"


class ParseError(Exception):
    """模型输出无法解析为合法 JSON。"""


def parse_json(text: str) -> AnswerResult:
    """从模型输出提取 JSON，兼容前后噪声与 markdown 代码块包裹。"""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    # 1) 直接解析
    try:
        return AnswerResult(**json.loads(cleaned))
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # 2) 提取第一个花括号块
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return AnswerResult(**json.loads(match.group(0)))
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    raise ParseError("模型输出无法解析为合法 JSON")
