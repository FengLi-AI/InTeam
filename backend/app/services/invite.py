"""邀请码：生成、兑换、管理（每人一码）。

v1.0 用邀请码替代飞书 OAuth 登录：兑换即绑定体验账号，可作废；
将来发布到火山引擎后，把存储从本地 SQLite 换成云端数据库即可（码格式与验证逻辑不变）。
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta

from ..core.config import settings
from ..db import base
from ..db.models import InviteCode, Session, User, _utcnow

# 32 字符集：去掉易混淆的 0/O/1/I/L
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


class InviteError(Exception):
    """邀请码无效/已用/已作废。"""


def _code_digest(code: str) -> str:
    normalized = code.strip().upper()
    return "h1:" + hmac.new(
        settings.invite_pepper.encode(), normalized.encode(), hashlib.sha256
    ).hexdigest()


def generate_code() -> str:
    """生成邀请码，格式 IT-XXXX-XXXX。"""
    body = "".join(secrets.choice(_ALPHABET) for _ in range(8))
    return f"IT-{body[:4]}-{body[4:]}"


def create_invites(count: int, note: str = "") -> list[str]:
    """批量生成唯一邀请码，返回码列表。"""
    codes: list[str] = []
    with base.SessionLocal() as s:
        for _ in range(count):
            while True:
                code = generate_code()
                if s.query(InviteCode).filter(InviteCode.code == _code_digest(code)).first() is None:
                    break
            s.add(InviteCode(code=_code_digest(code), note=note))
            codes.append(code)
        s.commit()
    return codes


def revoke_invite(code: str) -> bool:
    """作废一个邀请码。"""
    with base.SessionLocal() as s:
        normalized = code.strip().upper()
        ic = (
            s.query(InviteCode)
            .filter(InviteCode.code.in_([_code_digest(normalized), normalized]))
            .first()
        )
        if ic is None or ic.status == "revoked":
            return False
        ic.status = "revoked"
        s.commit()
        return True


def redeem(code: str, nickname: str = "") -> dict:
    """一次性兑换邀请码；已使用的码不能再次创建会话。"""
    code = code.strip().upper()
    with base.SessionLocal() as s:
        ic = (
            s.query(InviteCode)
            .filter(InviteCode.code.in_([_code_digest(code), code]))
            .first()
        )
        if ic is None:
            raise InviteError("邀请码无效或不可用")
        if ic.status != "unused":
            raise InviteError("邀请码无效或不可用")

        user = User(
            open_id=f"invite_{secrets.token_hex(12)}",
            name=nickname.strip() or "试用用户",
        )
        s.add(user)
        s.flush()
        ic.code = _code_digest(code)  # 旧版明文邀请码命中后立即迁移
        ic.status = "used"
        ic.bound_user_id = user.id
        ic.used_ts = _utcnow()

        user.last_login_ts = _utcnow()
        token = secrets.token_urlsafe(32)
        from .auth import _digest

        s.add(
            Session(
                token=_digest(token, "session"),
                user_id=user.id,
                expires_ts=_utcnow() + timedelta(days=settings.session_ttl_days),
            )
        )
        s.commit()
        return {
            "token": token,
            "user": {
                "id": user.id,
                "name": user.name,
                "avatar_url": user.avatar_url,
                "department": user.department,
                "position": user.position,
            },
        }
