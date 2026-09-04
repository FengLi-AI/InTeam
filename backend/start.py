"""veFaaS 生产启动入口：恢复数据、执行迁移、启动 FastAPI。"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import uvicorn


BACKEND_DIR = Path(__file__).resolve().parent


def main() -> int:
    os.chdir(BACKEND_DIR)
    from app.core.config import settings
    from app.services.backup import restore_if_needed, sqlite_database_path

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # veFaaS 的 /tmp 是全新且可写的临时文件系统；首次启动时这些
    # 父目录尚不存在，必须在恢复或 Alembic 连接 SQLite 前创建。
    database = sqlite_database_path()
    if database is not None:
        database.parent.mkdir(parents=True, exist_ok=True)
    settings.records_dir.mkdir(parents=True, exist_ok=True)
    settings.vectordb_dir.mkdir(parents=True, exist_ok=True)
    restore_if_needed()
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=BACKEND_DIR,
        check=True,
    )
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
