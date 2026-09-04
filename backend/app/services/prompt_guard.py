"""Prompt/RAG 风险信号、输出泄漏检测与来源 URL 允许列表。"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse

from ..core.config import settings

LOG = logging.getLogger("inteam.prompt_guard")

_ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
_INPUT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "instruction_override",
        re.compile(
            r"(?:忽略|无视|覆盖|绕过).{0,24}(?:之前|以上|系统|开发者|安全).{0,20}(?:指令|规则|限制|提示词)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "prompt_extraction",
        re.compile(
            r"(?:输出|泄露|打印|重复|逐字|展示).{0,24}(?:系统提示词|system prompt|developer prompt|内部指令)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "secret_exfiltration",
        re.compile(
            r"(?:输出|查找|泄露|发送).{0,24}(?:api[ _-]?key|密钥|token|环境变量|私钥)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
]
_BASE64_BLOB = re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{120,}={0,2}(?![A-Za-z0-9+/])")
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("generic_api_key", re.compile(r"(?i)(?:api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,}")),
    ("cloud_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
]
_INTERNAL_PATH = re.compile(r"(?:/Volumes/|/Users/|backend/app/services/prompts/|\.env(?:\.|\b))")


@dataclass(frozen=True)
class GuardResult:
    signals: tuple[str, ...]
    high_risk: bool


def _normalize(text: str) -> str:
    return _ZERO_WIDTH.sub("", unicodedata.normalize("NFKC", text))


def inspect_untrusted_text(text: str) -> GuardResult:
    normalized = _normalize(text)
    signals = [name for name, pattern in _INPUT_PATTERNS if pattern.search(normalized)]
    if _BASE64_BLOB.search(normalized):
        signals.append("encoded_blob")
    # NFKC 会正常化中文全角标点，这不是攻击信号；
    # 只在原文真的含零宽/双向控制字符时标记。
    if _ZERO_WIDTH.search(text):
        signals.append("hidden_unicode")
    secret_signals = [name for name, pattern in _SECRET_PATTERNS if pattern.search(normalized)]
    signals.extend(secret_signals)
    high_risk = bool(secret_signals or len(set(signals)) >= 2 or "prompt_extraction" in signals)
    return GuardResult(tuple(sorted(set(signals))), high_risk)


def inspect_and_log(text: str, *, source: str) -> GuardResult:
    result = inspect_untrusted_text(text)
    if result.signals:
        LOG.warning("untrusted content risk source=%s signals=%s", source, ",".join(result.signals))
    return result


def output_is_sensitive(text: str, system_prompt: str = "") -> GuardResult:
    normalized = _normalize(text)
    signals = [name for name, pattern in _SECRET_PATTERNS if pattern.search(normalized)]
    if _INTERNAL_PATH.search(normalized):
        signals.append("internal_path")
    prompt_lines = [line.strip() for line in system_prompt.splitlines() if len(line.strip()) >= 32]
    if any(line in normalized for line in prompt_lines):
        signals.append("system_prompt_overlap")
    return GuardResult(tuple(sorted(set(signals))), bool(signals))


def safe_model_output(text: str, system_prompt: str = "") -> tuple[str, GuardResult]:
    result = output_is_sensitive(text, system_prompt)
    if result.signals:
        LOG.error("model output blocked signals=%s", ",".join(result.signals))
    if result.high_risk and settings.output_guard_mode == "enforce":
        return "本次回答触发了敏感信息保护，未展示结果。你可以换一种问法或转人工确认。", result
    return text, result


def safe_source_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return ""
    host = parsed.hostname.lower()
    if host not in settings.allowed_source_hosts and not any(
        host.endswith("." + allowed) for allowed in settings.allowed_source_hosts
    ):
        return ""
    return url
