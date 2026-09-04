"""飞书 OAuth 登录：授权 URL、换 token、查用户、签发/校验会话。"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx

from ..core.config import settings
from ..db import base
from ..db.models import OAuthState, Session, User

LOG = logging.getLogger("inteam.auth")

AUTH_URL = "https://accounts.feishu.cn/open-apis/authen/v1/index"


class AuthError(Exception):
    """登录过程失败。"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC，与 SQLite 存储一致


def _digest(value: str, purpose: str) -> str:
    return hmac.new(
        settings.session_secret.encode(), f"{purpose}:{value}".encode(), hashlib.sha256
    ).hexdigest()


def _issue_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with base.SessionLocal() as s:
        s.add(
            Session(
                token=_digest(token, "session"),
                user_id=user_id,
                expires_ts=_utcnow() + timedelta(days=settings.session_ttl_days),
            )
        )
        s.commit()
    return token


def build_auth_url() -> tuple[str, str]:
    """生成飞书授权跳转链接（带防 CSRF 的 state）。"""
    state = secrets.token_urlsafe(16)
    with base.SessionLocal() as s:
        s.add(
            OAuthState(
                state_hash=_digest(state, "oauth-state"),
                expires_ts=_utcnow() + timedelta(seconds=settings.oauth_state_ttl_seconds),
            )
        )
        s.commit()
    url = (
        f"{AUTH_URL}?app_id={settings.feishu_app_id}"
        f"&redirect_uri={quote(settings.feishu_auth_redirect_uri, safe='')}"
        f"&state={state}"
    )
    return url, state


def _exchange_code(code: str) -> str:
    """用授权 code 换 user_access_token。"""
    resp = httpx.post(
        f"{settings.feishu_base_url}/open-apis/authen/v1/oauth/token",
        json={
            "grant_type": "authorization_code",
            "client_id": settings.feishu_app_id,
            "client_secret": settings.feishu_app_secret,
            "code": code,
            "redirect_uri": settings.feishu_auth_redirect_uri,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise AuthError(f"exchange code failed: {data.get('msg')}")
    return (data.get("data") or {}).get("access_token", "")


def _fetch_user_info(user_access_token: str) -> dict:
    """用 user_access_token 查用户基础信息。"""
    resp = httpx.get(
        f"{settings.feishu_base_url}/open-apis/authen/v1/user_info",
        headers={"Authorization": f"Bearer {user_access_token}"},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise AuthError(f"fetch user_info failed: {data.get('msg')}")
    return data.get("data") or {}


def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "open_id": user.open_id,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "department": user.department,
        "position": user.position,
    }


def _consume_oauth_state(state: str) -> None:
    if not state:
        raise AuthError("invalid oauth state")
    now = _utcnow()
    with base.SessionLocal() as s:
        item = (
            s.query(OAuthState)
            .filter(OAuthState.state_hash == _digest(state, "oauth-state"))
            .first()
        )
        if item is None or item.used_ts is not None or item.expires_ts < now:
            raise AuthError("invalid oauth state")
        item.used_ts = now
        s.commit()


def login(code: str, state: str) -> dict:
    """完整登录：换 token → 查用户 → 建档/更新 → 签发会话。"""
    _consume_oauth_state(state)
    access_token = _exchange_code(code)
    if not access_token:
        raise AuthError("no access_token in feishu response")
    info = _fetch_user_info(access_token)
    open_id = info.get("open_id", "")
    if not open_id:
        raise AuthError("no open_id in user_info")

    name = info.get("name", "")
    avatar = info.get("avatar_url", "")

    with base.SessionLocal() as s:
        user = s.query(User).filter(User.open_id == open_id).first()
        if user is None:
            user = User(open_id=open_id, name=name, avatar_url=avatar)
            s.add(user)
        else:
            user.name = name or user.name
            user.avatar_url = avatar or user.avatar_url
        user.last_login_ts = _utcnow()
        s.flush()

        s.commit()
        user_dict = _user_to_dict(user)

    token = _issue_session(user_dict["id"])
    return {"token": token, "user": user_dict}


def get_user_by_token(token: str) -> dict | None:
    """按 token 取当前用户；无效或过期返回 None。"""
    if not token:
        return None
    with base.SessionLocal() as s:
        digest = _digest(token, "session")
        sess = s.query(Session).filter(Session.token == digest).first()
        if sess is None:
            # 旧版明文会话仅用于无感迁移；命中后立即替换为哈希。
            sess = s.query(Session).filter(Session.token == token).first()
            if sess is not None:
                sess.token = digest
                s.commit()
        if sess is None or sess.expires_ts < _utcnow():
            return None
        user = s.get(User, sess.user_id)
        if user is None:
            return None
        return _user_to_dict(user)


def logout(token: str) -> None:
    """删除会话（注销）。"""
    if not token:
        return
    with base.SessionLocal() as s:
        digest = _digest(token, "session")
        s.query(Session).filter(Session.token.in_([digest, token])).delete(
            synchronize_session=False
        )
        s.commit()
