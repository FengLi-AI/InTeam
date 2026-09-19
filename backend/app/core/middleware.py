"""请求体、来源校验、请求 ID 与安全响应头。"""
from __future__ import annotations

import logging
import time
import uuid

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import settings


LOG = logging.getLogger("inteam.http")


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_body_size: int) -> None:
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        content_length = headers.get("content-length")
        if content_length and int(content_length) > self.max_body_size:
            response = JSONResponse(
                {"detail": "请求内容过大"}, status_code=413, headers={"Cache-Control": "no-store"}
            )
            await response(scope, receive, send)
            return

        # 缓冲有上限的小请求体，避免 chunked 传输绕过 Content-Length。
        # 如果仅向下游伪造 http.disconnect，框架可能返回 400 而不是明确的 413。
        body_parts: list[bytes] = []
        received = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            part = message.get("body", b"")
            received += len(part)
            if received > self.max_body_size:
                response = JSONResponse(
                    {"detail": "请求内容过大"},
                    status_code=413,
                    headers={"Cache-Control": "no-store"},
                )
                await response(scope, receive, send)
                return
            body_parts.append(part)
            if not message.get("more_body", False):
                break

        replayed = False

        async def limited_receive() -> Message:
            nonlocal replayed
            if replayed:
                # Forward the real disconnect signal so an interrupted Agent stream
                # cancels its model request. Never fabricate a disconnect here.
                return await receive()
            replayed = True
            return {"type": "http.request", "body": b"".join(body_parts), "more_body": False}

        await self.app(scope, limited_receive, send)


class SecurityMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")
        request_id = headers.get("x-request-id") or uuid.uuid4().hex
        started_at = time.perf_counter()
        response_status = 500
        has_cookie_session = settings.session_cookie_name in headers.get("cookie", "")
        if settings.app_env in {"staging", "production"} and has_cookie_session and method not in {
            "GET",
            "HEAD",
            "OPTIONS",
        }:
            origin = headers.get("origin", "")
            if origin not in settings.allowed_origins:
                response = JSONResponse(
                    {"detail": "请求来源校验失败"},
                    status_code=403,
                    headers={"X-Request-ID": request_id, "Cache-Control": "no-store"},
                )
                await response(scope, receive, send)
                return

        async def secure_send(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = int(message.get("status", 500))
                response_headers = list(message.get("headers", []))
                response_headers.extend(
                    [
                        (b"x-request-id", request_id.encode()),
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"strict-origin-when-cross-origin"),
                        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                    ]
                )
                if scope.get("path", "").startswith("/api/"):
                    response_headers.append((b"cache-control", b"no-store"))
                if settings.app_env == "production":
                    response_headers.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, receive, secure_send)
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
            LOG.info(
                "request completed request_id=%s method=%s path=%s status=%s duration_ms=%s",
                request_id,
                method,
                path,
                response_status,
                duration_ms,
            )
