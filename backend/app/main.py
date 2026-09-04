"""FastAPI 入口：挂载路由、CORS、根路由。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .api import (
    actions,
    auth,
    chat,
    contacts,
    dashboard,
    docs,
    escalate,
    faq,
    feedback,
    onboarding,
    stats,
    sync,
    todos,
)
from .core.config import settings
from .core.middleware import RequestBodyLimitMiddleware, SecurityMiddleware
from .services.backup import backup_worker
from .services.contacts import seed_contacts

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release="inteam@0.5.0",
        send_default_pii=False,
        traces_sample_rate=0.0,
    )

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """表结构由 Alembic 管理；启动只执行幂等的演示同事种子。"""
    seed_contacts()
    backup_worker.start()
    try:
        yield
    finally:
        backup_worker.stop()


app = FastAPI(
    title="InTeam",
    version="0.5.0",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-Idempotency-Key"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(SecurityMiddleware)
app.add_middleware(RequestBodyLimitMiddleware, max_body_size=settings.max_request_body_bytes)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(contacts.router, prefix="/api/v1")
app.include_router(todos.router, prefix="/api/v1")
app.include_router(actions.router, prefix="/api/v1")
app.include_router(onboarding.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(docs.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(sync.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(escalate.router, prefix="/api/v1")
app.include_router(faq.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")

@app.get("/")
def root() -> dict:
    return {"service": "InTeam", "health": "/api/v1/health"}
