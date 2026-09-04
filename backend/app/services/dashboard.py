"""今日卡片：入职天数 + 待办进度 + AI 今日建议。"""
from __future__ import annotations

import logging
from datetime import date

from ..core.config import settings
from ..db import base
from ..db.models import User
from .todos import list_todos

LOG = logging.getLogger("inteam.dashboard")


def onboard_day(user_id: int) -> int:
    """入职天数（从首次建档起算，最小 1）。"""
    with base.SessionLocal() as s:
        user = s.get(User, user_id)
    if user is None or user.created_ts is None:
        return 1
    return max(1, (date.today() - user.created_ts.date()).days + 1)


def _suggest(days: int, done: int, total: int, pending: list[str]) -> str:
    """AI 生成今日建议；无 Key 或失败时用模板兜底。"""
    if settings.has_key:
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                timeout=settings.timeout_seconds,
            )
            prompt = (
                f"你是入职助手。新员工入职第 {days} 天，待办完成 {done}/{total}，"
                f"剩余待办：{('、'.join(pending[:3])) if pending else '无'}。\n"
                f"请给一句 40 字以内的今日建议，口语化、鼓励、具体可执行，不要编造待办之外的事。"
            )
            resp = client.chat.completions.create(
                model=settings.deepseek_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=120,
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                return text
        except Exception as exc:  # noqa: BLE001
            LOG.warning("dashboard suggestion failed: %s", exc)

    if total == 0:
        return "欢迎入职！先从左侧资料库了解团队，或直接问我任何问题。"
    if done == total:
        return f"入职第 {days} 天，待办已全部完成！接下来可以多问流程，或点击同事卡片认识伙伴。"
    head = pending[0] if pending else "今天的任务"
    return f"入职第 {days} 天，还有 {total - done} 项待办。建议优先完成「{head}」。"


def get_dashboard(user_id: int) -> dict:
    days = onboard_day(user_id)
    todos = list_todos(user_id)
    done = sum(1 for t in todos if t["status"] == "done")
    total = len(todos)
    pending = [t["title"] for t in todos if t["status"] == "open"]
    return {
        "onboard_day": days,
        "todo_done": done,
        "todo_total": total,
        "suggestion": _suggest(days, done, total, pending),
    }
