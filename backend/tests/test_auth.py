"""飞书 OAuth 登录测试（mock 换 token 与查用户）。"""
from app.db import base
from app.db.models import Session, User
from app.services import auth as auth_mod
from app.services.auth import build_auth_url, get_user_by_token, login, logout


def _mock_fetch(monkeypatch, info: dict):
    monkeypatch.setattr(auth_mod, "_exchange_code", lambda code: "uat_123")
    monkeypatch.setattr(auth_mod, "_fetch_user_info", lambda token: info)


def _login(code: str) -> dict:
    _url, state = build_auth_url()
    return login(code, state)


def test_login_creates_user_and_session(monkeypatch):
    _mock_fetch(monkeypatch, {"open_id": "ou_1", "name": "张三", "avatar_url": "https://x/a.png"})
    result = _login("code123")
    assert result["token"]
    assert result["user"]["name"] == "张三"
    assert result["user"]["open_id"] == "ou_1"

    with base.SessionLocal() as s:
        assert s.query(User).count() == 1
        assert s.query(Session).count() == 1


def test_login_updates_existing_user(monkeypatch):
    _mock_fetch(monkeypatch, {"open_id": "ou_1", "name": "张三", "avatar_url": ""})
    _login("code1")
    _mock_fetch(monkeypatch, {"open_id": "ou_1", "name": "张三丰", "avatar_url": "https://x/b.png"})
    _login("code2")

    with base.SessionLocal() as s:
        users = s.query(User).all()
        assert len(users) == 1  # 同 open_id 不重复建档
        assert users[0].name == "张三丰"
        assert users[0].avatar_url == "https://x/b.png"


def test_get_user_by_token_valid_and_invalid(monkeypatch):
    _mock_fetch(monkeypatch, {"open_id": "ou_1", "name": "张三"})
    token = _login("code")["token"]
    assert get_user_by_token(token)["name"] == "张三"
    assert get_user_by_token("bad_token") is None
    assert get_user_by_token("") is None


def test_logout_invalidates_session(monkeypatch):
    _mock_fetch(monkeypatch, {"open_id": "ou_1", "name": "张三"})
    token = _login("code")["token"]
    logout(token)
    assert get_user_by_token(token) is None
