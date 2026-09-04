"""统计聚合测试。"""
import json

from app.core import config
from app.db import base
from app.db.models import EscalateTicket
from app.services.feedback import record_feedback
from app.services.stats import get_stats


def test_stats_empty():
    s = get_stats()
    assert s["feedback_count"] == 0
    assert s["helpful_rate"] == 0.0
    assert s["escalate_count"] == 0
    assert s["blind_spots"] == []


def test_stats_aggregates(monkeypatch, tmp_path):
    monkeypatch.setattr(config.settings, "records_dir", tmp_path)
    # 一条无出处记录，供无帮助反馈命中盲区
    (tmp_path / "qa.jsonl").write_text(
        json.dumps({"id": "blind1", "question": "盲区问题", "sources": []}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    record_feedback("a1", True)
    record_feedback("a2", False)
    record_feedback("blind1", False)

    with base.SessionLocal() as s:
        s.add(EscalateTicket(question="q", status="sent"))
        s.commit()

    s = get_stats()
    assert s["feedback_count"] == 3
    assert s["helpful_rate"] == round(1 / 3, 4)
    assert s["escalate_count"] == 1
    assert any(b["question"] == "盲区问题" for b in s["blind_spots"])
