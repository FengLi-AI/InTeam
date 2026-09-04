"""SQLAlchemy engine / session / 建表入口。

engine 与 SessionLocal 为模块级单例；测试可通过 monkeypatch 重绑定到临时 SQLite。
services 应通过 `from ..db import base` 访问 `base.SessionLocal()`，以便测试替换生效。
"""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session as OrmSession, sessionmaker

from ..core.config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def make_engine(url: str):
    """按 URL 创建 engine；SQLite 关闭同线程校验以支持多线程。"""
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


engine = make_engine(settings.database_url)
SessionLocal = make_session_factory(engine)


@event.listens_for(OrmSession, "after_commit")
def _request_tos_backup_after_commit(_session: OrmSession) -> None:
    """将所有 ORM 持久化操作统一接入单实例 TOS 备份唤醒器。"""
    from ..services.backup import backup_worker

    backup_worker.request()


def init_db() -> None:
    """建表（幂等）。正式迁移用 Alembic，此函数作开发期兜底。"""
    from . import models  # noqa: F401  确保模型已注册到 Base.metadata

    Base.metadata.create_all(bind=engine)
