"""反馈测试（盲区判定）。"""
import json

from app.core import config
from app.db import base
from app.db.models import Feedback
from app.services.feedback import record_feedback


def test_helpful_feedback_not_blind_spot():
    result = record_feedback("ans1", True)
    assert result["blind_spot"] is False
    with base.SessionLocal() as s:
        f = s.query(Feedback).one()
        assert f.helpful is True


def test_unhelpful_without_sources_is_blind_spot(monkeypatch, tmp_path):
    monkeypatch.setattr(config.settings, "records_dir", tmp_path)
    (tmp_path / "qa.jsonl").write_text(
        json.dumps({"id": "ans2", "question": "上海明天会下雨吗", "sources": []}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    result = record_feedback("ans2", False, note="没有答案")
    assert result["blind_spot"] is True
    with base.SessionLocal() as s:
        f = s.query(Feedback).one()
        assert f.question == "上海明天会下雨吗"
        assert f.note == "没有答案"


def test_unhelpful_with_sources_not_blind_spot(monkeypatch, tmp_path):
    monkeypatch.setattr(config.settings, "records_dir", tmp_path)
    (tmp_path / "qa.jsonl").write_text(
        json.dumps(
            {"id": "ans3", "question": "q", "sources": [{"title": "t", "section": "s"}]},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    result = record_feedback("ans3", False)
    assert result["blind_spot"] is False
