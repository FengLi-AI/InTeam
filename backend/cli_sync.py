"""手动同步命令行入口。

用法（在 backend 目录下）：
    .venv/bin/python cli_sync.py
"""
from __future__ import annotations

import json

from app.services.sync import run_sync


def main() -> int:
    result = run_sync()
    print(
        json.dumps(
            {
                "synced": result.synced,
                "skipped": result.skipped,
                "failed": result.failed,
                "items": [
                    {
                        "doc_token": i.doc_token,
                        "status": i.status,
                        "chunk_count": i.chunk_count,
                        "error": i.error,
                    }
                    for i in result.items
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
