"""登录 API 测试。"""
from app.core import config
from app.services import auth as auth_mod
from app.services.invite import create_invites


def _mock_login(monkeypatch, name="李四"):
    monkeypatch.setattr(auth_mod, "_exchange_code", lambda code: "uat")
    monkeypatch.setattr(auth_mod, "_fetch_user_info", lambda token: {"open_id": "ou_1", "name": name})


def test_auth_url(api_client, monkeypatch):
    monkeypatch.setattr(config.settings, "enable_feishu_oauth", True)
    r = api_client.get("/api/v1/auth/url")
    assert r.status_code == 200
    body = r.json()
    assert body["url"]
    assert body["state"]


def test_me_requires_login(api_client):
    r = api_client.get("/api/v1/me")
    assert r.status_code == 401


def test_login_and_me(api_client, monkeypatch):
    monkeypatch.setattr(config.settings, "enable_feishu_oauth", True)
    _mock_login(monkeypatch)
    state = api_client.get("/api/v1/auth/url").json()["state"]
    r = api_client.post("/api/v1/auth/login", json={"code": "c", "state": state})
    assert r.status_code == 200
    assert "token" not in r.json()
    assert config.settings.session_cookie_name in api_client.cookies

    r = api_client.get("/api/v1/me")
    assert r.status_code == 200
    assert r.json()["user"]["name"] == "李四"


def test_login_rejects_bad_code(api_client, monkeypatch):
    monkeypatch.setattr(config.settings, "enable_feishu_oauth", True)
    def _fail(code):
        raise auth_mod.AuthError("bad code")

    monkeypatch.setattr(auth_mod, "_exchange_code", _fail)
    state = api_client.get("/api/v1/auth/url").json()["state"]
    r = api_client.post("/api/v1/auth/login", json={"code": "bad", "state": state})
    assert r.status_code == 400


def test_logout(api_client, monkeypatch):
    monkeypatch.setattr(config.settings, "enable_feishu_oauth", True)
    _mock_login(monkeypatch)
    state = api_client.get("/api/v1/auth/url").json()["state"]
    assert api_client.post("/api/v1/auth/login", json={"code": "c", "state": state}).status_code == 200
    r = api_client.post("/api/v1/auth/logout")
    assert r.status_code == 200
    r = api_client.get("/api/v1/me")
    assert r.status_code == 401


def test_invite_login_flow(api_client):
    """邀请码兑换登录（v1.0 主登录方式）。"""
    code = create_invites(1)[0]
    r = api_client.post("/api/v1/auth/invite", json={"invite_code": code, "nickname": "试用"})
    assert r.status_code == 200
    body = r.json()
    assert "token" not in body
    assert body["user"]["name"] == "试用"

    r = api_client.get("/api/v1/me")
    assert r.status_code == 200
    assert r.json()["user"]["name"] == "试用"


def test_invite_login_invalid_code(api_client):
    r = api_client.post("/api/v1/auth/invite", json={"invite_code": "IT-BADCODE"})
    assert r.status_code == 400
