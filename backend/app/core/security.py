"""统一身份、角色和知识文档权限依赖。"""
from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from .config import settings
from ..services.auth import get_user_by_token

User = dict[str, object]


def _bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer "):
        return authorization[len("Bearer ") :].strip()
    return ""


def request_token(request: Request) -> tuple[str, str]:
    """返回 (token, source)，Cookie 优先；Bearer 仅用于旧会话平滑迁移。"""
    cookie = request.cookies.get(settings.session_cookie_name, "").strip()
    if cookie:
        return cookie, "cookie"
    bearer = _bearer_token(request)
    return (bearer, "bearer") if bearer else ("", "none")


def optional_user(request: Request) -> User | None:
    token, source = request_token(request)
    user = get_user_by_token(token)
    if user is not None:
        user["auth_source"] = source
    return user


def require_user(request: Request) -> User:
    user = optional_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或会话已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(require_user)]


def _valid_service_token(request: Request) -> bool:
    supplied = request.headers.get("x-inteam-service-token", "")
    return bool(
        settings.service_token
        and supplied
        and hmac.compare_digest(supplied, settings.service_token)
    )


def is_admin(user: User) -> bool:
    user_id = user.get("id")
    open_id = user.get("open_id")
    return bool(
        (isinstance(user_id, int) and user_id in settings.admin_user_ids)
        or (isinstance(open_id, str) and open_id in settings.admin_open_ids)
    )


def require_admin_or_service(request: Request) -> User:
    if _valid_service_token(request):
        return {"id": 0, "name": "service", "role": "service", "auth_source": "service"}
    user = require_user(request)
    if not is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权执行此操作")
    user["role"] = "admin"
    return user


AdminUser = Annotated[User, Depends(require_admin_or_service)]


def allowed_doc_tokens(user: User) -> set[str] | None:
    """None 表示明确允许全部；空集合表示没有任何文档权限。"""
    if settings.allow_all_authenticated_docs:
        return None
    candidates = [str(user.get("id", "")), f"open_id:{user.get('open_id', '')}"]
    tokens: set[str] = set()
    for key in candidates:
        tokens.update(settings.doc_acl.get(key, []))
    return tokens
