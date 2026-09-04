"""答案生成：有 Key 走 DeepSeek 真实模型，无 Key 走演示模式（mock）。

对外统一产出 SSE 事件字符串序列（chunk... → done）。
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

from ..core.config import settings
from .contacts import match_contacts
from .guard import decide
from .parser import ParseError, parse_json
from .prompt_guard import inspect_and_log, safe_model_output, safe_source_url
from .records import append_record
from .retriever import Hit

LOG = logging.getLogger("inteam.generator")

_PROMPT_DIR = Path(__file__).parent / "prompts"

_CHUNK_SIZE = 8  # 流式输出每块的字符数（演示/回放用）


def _load_prompt(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8")


def _sse(data: dict) -> str:
    """把 dict 序列化为一条 SSE data 事件。"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _chunk_text(text: str, size: int = _CHUNK_SIZE) -> Iterator[str]:
    for i in range(0, len(text), size):
        yield text[i : i + size]


def _build_contexts(hits: list[Hit]) -> str:
    parts = []
    for i, h in enumerate(hits, 1):
        parts.append(
            f"[片段{i}] 文档《{h.chunk.title}》章节「{h.chunk.section}」：\n{h.chunk.text[:500]}"
        )
    return "\n\n".join(parts) if parts else "（无检索结果）"


def filter_untrusted_hits(hits: list[Hit]) -> list[Hit]:
    safe_hits: list[Hit] = []
    for hit in hits:
        result = inspect_and_log(hit.chunk.text, source=f"rag:{hit.chunk.doc_token or hit.chunk.path}")
        if result.high_risk and settings.prompt_guard_mode == "enforce":
            continue
        safe_hits.append(hit)
    return safe_hits


def _build_prompt(question: str, hits: list[Hit]) -> str:
    template = _load_prompt("answer.md")
    return template.format(question=question, contexts=_build_contexts(hits))


def _suggest_questions(hits: list[Hit], guard: str) -> list[str]:
    """基于检索命中生成 2~3 个追问建议（模板式，不额外调模型）。"""
    qs: list[str] = []
    seen: list[str] = []
    for h in hits[:2]:
        if h.chunk.title not in seen:
            seen.append(h.chunk.title)
            qs.append(f"《{h.chunk.title}》里还讲了什么？")
    if guard != "not_found":
        qs.append("遇到这个问题该找谁？")
    if not qs:
        qs = ["公司有哪些部门？", "入职第一天要做什么？"]
    return qs[:3]


def _sources_from_hits(hits: list[Hit], top: int = 3) -> list[dict]:
    sources: list[dict] = []
    for h in hits[:top]:
        item = {"title": h.chunk.title, "section": h.chunk.section}
        safe_url = safe_source_url(h.chunk.url)
        if safe_url:  # 来源只允许批准的 HTTPS 域名
            item["url"] = safe_url
        sources.append(item)
    return sources


def _produce_real(question: str, hits: list[Hit], guard: str) -> tuple[str, list[dict], str]:
    """调用 DeepSeek 真实模型，流式累积后解析 JSON。"""
    from openai import OpenAI

    client = OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        timeout=settings.timeout_seconds,
    )
    system = _load_prompt("system.md")
    response = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": _build_prompt(question, hits)},
        ],
        stream=True,
        max_tokens=settings.max_tokens,
    )
    acc = ""
    for chunk in response:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            acc += delta
    try:
        result = parse_json(acc)
        # 出处统一取检索命中（含 url），不信任模型输出的 sources，避免漏掉跳转链接
        safe_answer, _signals = safe_model_output(result.answer, system)
        return safe_answer, _sources_from_hits(hits), result.confidence
    except ParseError:
        LOG.warning("model output parse failed, return safe failure")
        return (
            "这次回答没有通过安全格式校验，请重试或转人工确认。",
            _sources_from_hits(hits),
            "none",
        )


def _produce_mock(question: str, hits: list[Hit], guard: str) -> tuple[str, list[dict], str]:
    """演示模式：无 Key 时基于检索结果生成可交互的回答。"""
    if guard == "not_found":
        return (
            "（演示模式）资料中暂未找到相关说明，建议转人工咨询 mentor。",
            [],
            "none",
        )
    if guard == "suggested":
        top = hits[0]
        return (
            f"（演示模式）这个问题只能给简单建议：可先看《{top.chunk.title}》的"
            f"「{top.chunk.section}」章节，建议转人工确认。",
            [{"title": top.chunk.title, "section": top.chunk.section}],
            "low",
        )
    parts = []
    for h in hits[:3]:
        snippet = " ".join(h.chunk.text[:120].split())
        parts.append(f"- 《{h.chunk.title}》「{h.chunk.section}」：{snippet}")
    answer = (
        "（演示模式，未配置 DeepSeek Key）根据知识库检索到以下相关内容：\n\n"
        + "\n".join(parts)
        + "\n\n配置 DEEPSEEK_API_KEY 后将切换为 AI 真实作答。"
    )
    return answer, _sources_from_hits(hits), "high"


def sse_events(question: str, hits: list[Hit], guard: str, user_id: int | None = None) -> Iterator[str]:
    """产出完整 SSE 事件流：chunk 若干 → done（或由上层兜底 error）。"""
    input_risk = inspect_and_log(question, source="user-question")
    if input_risk.high_risk and settings.prompt_guard_mode == "enforce":
        answer, sources, confidence = (
            "我不能提供系统提示词、密钥或内部配置。你可以继续询问入职资料、流程或协作问题。",
            [],
            "none",
        )
    elif settings.has_key:
        answer, sources, confidence = _produce_real(question, hits, guard)
    else:
        answer, sources, confidence = _produce_mock(question, hits, guard)

    answer_id = append_record(
        "qa",
        {
            "question": question,
            "answer": answer,
            "sources": sources,
            "confidence": confidence,
            "guard": guard,
            "demo": not settings.has_key,
            "user_id": user_id,
            "security_signals": list(input_risk.signals),
        },
    )

    for piece in _chunk_text(answer):
        yield _sse({"type": "chunk", "text": piece})

    yield _sse(
        {
            "type": "done",
            "answer_id": answer_id,
            "answer": answer,
            "sources": sources,
            "guard": guard,
            "confidence": confidence,
            "suggested_questions": _suggest_questions(hits, guard),
            "related_contacts": match_contacts(question),
        }
    )
