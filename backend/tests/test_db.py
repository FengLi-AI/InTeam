"""数据库模型测试（临时 SQLite，由 conftest 隔离）。"""
from app.db import base
from app.db.models import EscalateTicket, Faq, Feedback


def test_escalate_ticket_crud():
    with base.SessionLocal() as s:
        s.add(EscalateTicket(question="怎么连数据库", context="ctx", status="sent", message_id="om_1"))
        s.commit()
    with base.SessionLocal() as s:
        t = s.query(EscalateTicket).one()
        assert t.question == "怎么连数据库"
        assert t.status == "sent"
        assert t.message_id == "om_1"


def test_feedback_crud():
    with base.SessionLocal() as s:
        s.add(Feedback(answer_id="a1", helpful=True, blind_spot=False))
        s.commit()
    with base.SessionLocal() as s:
        f = s.query(Feedback).one()
        assert f.helpful is True
        assert f.blind_spot is False


def test_faq_status_flow():
    with base.SessionLocal() as s:
        s.add(Faq(question="q", answer="a", status="candidate"))
        s.commit()
    with base.SessionLocal() as s:
        faq = s.query(Faq).one()
        assert faq.status == "candidate"
        assert faq.confirmed_ts is None
