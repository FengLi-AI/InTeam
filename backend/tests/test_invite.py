"""邀请码测试。"""
import re

import pytest

from app.db import base
from app.db.models import InviteCode, User
from app.services.invite import (
    _code_digest,
    InviteError,
    create_invites,
    generate_code,
    redeem,
    revoke_invite,
)


def test_generate_code_format():
    code = generate_code()
    assert re.fullmatch(r"IT-[A-Z0-9]{4}-[A-Z0-9]{4}", code)


def test_create_invites_unique():
    codes = create_invites(20, "内测")
    assert len(codes) == 20
    assert len(set(codes)) == 20
    with base.SessionLocal() as s:
        assert s.query(InviteCode).count() == 20


def test_redeem_creates_user_and_session():
    code = create_invites(1)[0]
    result = redeem(code)
    assert result["token"]
    assert result["user"]["name"] == "试用用户"

    with base.SessionLocal() as s:
        ic = s.query(InviteCode).filter(InviteCode.code == _code_digest(code)).one()
        assert ic.status == "used"
        assert ic.bound_user_id is not None
        assert s.query(User).count() == 1


def test_redeem_again_is_rejected():
    code = create_invites(1)[0]
    redeem(code)
    with pytest.raises(InviteError):
        redeem(code)


def test_redeem_with_nickname():
    code = create_invites(1)[0]
    result = redeem(code, nickname="小明")
    assert result["user"]["name"] == "小明"


def test_redeem_invalid_code():
    with pytest.raises(InviteError):
        redeem("IT-NOTEXIST")


def test_revoke():
    code = create_invites(1)[0]
    assert revoke_invite(code) is True
    with pytest.raises(InviteError):
        redeem(code)
