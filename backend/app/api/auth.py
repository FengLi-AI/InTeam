"""登录 / 用户身份 API。

v1.0 登录方式 = 邀请码（`/auth/invite`）；飞书 OAuth（`/auth/url`、`/auth/login`）保留备用。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from ..core.config import settings
from ..core.security import AdminUser, CurrentUser, request_token
from ..schemas.chat import (
    InviteGenerateRequest,
    InviteLoginRequest,
    InviteRevokeRequest,
    LoginRequest,
)
from ..services.auth import AuthError, build_auth_url, login, logout
from ..services.invite import InviteError, create_invites, redeem, revoke_invite
from ..services.rate_limit import client_ip, limiter

router = APIRouter()


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_days * 86400,
        httponly=True,
        secure=settings.app_env in {"staging", "production"},
        samesite="lax",
        path="/",
    )


@router.post("/auth/invite")
def auth_invite(req: InviteLoginRequest, request: Request, response: Response) -> dict:
    """邀请码兑换登录（v1.0 主登录方式）。"""
    limiter.check(
        f"ip:{client_ip(request)}:invite",
        settings.invite_attempt_limit,
        settings.invite_attempt_window_seconds,
    )
    try:
        result = redeem(req.invite_code, req.nickname)
    except InviteError as exc:
        raise HTTPException(status_code=400, detail="邀请码无效或不可用") from exc
    _set_session_cookie(response, result["token"])
    return {"user": result["user"]}


@router.get("/auth/url")
def auth_url() -> dict:
    if not settings.enable_feishu_oauth:
        raise HTTPException(status_code=404, detail="此登录方式未启用")
    url, state = build_auth_url()
    return {"url": url, "state": state}


@router.post("/auth/login")
def auth_login(req: LoginRequest, response: Response) -> dict:
    if not settings.enable_feishu_oauth:
        raise HTTPException(status_code=404, detail="此登录方式未启用")
    try:
        result = login(req.code, req.state)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _set_session_cookie(response, result["token"])
    return {"user": result["user"]}


@router.get("/me")
def me(request: Request, response: Response, user: CurrentUser) -> dict:
    token, source = request_token(request)
    if source == "bearer":
        _set_session_cookie(response, token)
    return {"user": user}


@router.post("/auth/logout")
def auth_logout(request: Request, response: Response, _user: CurrentUser) -> dict:
    token, _source = request_token(request)
    logout(token)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"status": "ok"}


@router.post("/admin/invites")
def admin_create_invites(req: InviteGenerateRequest, _actor: AdminUser) -> dict:
    """生成邀请码；明文只在本次受保护响应中返回。"""
    return {"codes": create_invites(req.count, req.note)}


@router.post("/admin/invites/revoke")
def admin_revoke_invite(req: InviteRevokeRequest, _actor: AdminUser) -> dict:
    """作废邀请码；无论是否存在都不返回内部记录。"""
    if not revoke_invite(req.invite_code):
        raise HTTPException(status_code=404, detail="邀请码不存在或已作废")
    return {"status": "revoked"}
