"""FAQ 沉淀与检索。

检索说明：第 3 阶段 FAQ 量小，先用 SQLite 关键词匹配（轻量、可离线）；
FAQ 语义向量检索复用第 2 阶段向量库，后续阶段按需接入。
"""
from __future__ import annotations

import logging
import re
from ..db import base
from ..db.models import Faq, _utcnow

LOG = logging.getLogger("inteam.faq")


def _tokenize(text: str) -> set[str]:
    text = text.lower()
    tokens = set(re.findall(r"[a-z0-9]+", text))
    cn_chars = re.findall(r"[\u4e00-\u9fff]", text)
    for i in range(len(cn_chars) - 1):
        tokens.add(cn_chars[i] + cn_chars[i + 1])
    return tokens


def add_faq(question: str, answer: str, source_url: str = "") -> str:
    """沉淀一条候选 FAQ（需人工确认后生效）。"""
    with base.SessionLocal() as s:
        faq = Faq(question=question, answer=answer, source_url=source_url, status="candidate")
        s.add(faq)
        s.commit()
        return str(faq.id)


def confirm_faq(faq_id: int) -> bool:
    """确认候选 FAQ 生效。返回是否成功。"""
    with base.SessionLocal() as s:
        faq = s.get(Faq, faq_id)
        if faq is None:
            return False
        faq.status = "confirmed"
        faq.confirmed_ts = _utcnow()
        s.commit()
        return True


def search_faq(query: str, top_k: int = 5) -> list[dict]:
    """检索已确认 FAQ，按关键词重叠度打分。"""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []
    with base.SessionLocal() as s:
        rows = s.query(Faq).filter(Faq.status == "confirmed").all()

    scored: list[tuple[float, Faq]] = []
    for faq in rows:
        overlap = len(q_tokens & _tokenize(faq.question + " " + faq.answer))
        if overlap == 0:
            continue
        score = overlap / len(q_tokens)
        scored.append((score, faq))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "id": str(faq.id),
            "question": faq.question,
            "answer": faq.answer,
            "source_url": faq.source_url,
        }
        for _, faq in scored[:top_k]
    ]
