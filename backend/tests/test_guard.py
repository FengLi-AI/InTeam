"""兜底分流单元测试。"""
from app.services.guard import decide
from app.services.retriever import Chunk, Hit


def _hit(score: float) -> Hit:
    return Hit(chunk=Chunk(title="t", section="s", text="x", path="p.md"), score=score)


def test_not_found_when_no_hits():
    assert decide([], 0.4) == "not_found"


def test_answered_when_above_threshold():
    assert decide([_hit(0.8)], 0.4) == "answered"


def test_suggested_when_below_threshold():
    assert decide([_hit(0.2)], 0.4) == "suggested"


def test_threshold_boundary():
    assert decide([_hit(0.4)], 0.4) == "answered"
