"""兜底分流：按检索分数判定 answered / suggested / not_found。"""
from __future__ import annotations

from .retriever import Hit


def decide(hits: list[Hit], threshold: float) -> str:
    """返回 guard 档位：
    - answered  ：命中且最高分 >= 阈值，正常作答
    - suggested ：有命中但分数偏低，给简单建议 + 转人工
    - not_found ：无命中，明确暂未收录 + 转人工
    """
    if not hits:
        return "not_found"
    if hits[0].score >= threshold:
        return "answered"
    return "suggested"
