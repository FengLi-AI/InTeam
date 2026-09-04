"""记录持久化：问答 / 反馈 / 转人工 / 轨迹，JSONL 原子追加。"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

from ..core.config import settings


def append_record(kind: str, data: dict[str, Any]) -> str:
    """追加一条记录，返回记录 id。目录不存在时自动创建。"""
    settings.records_dir.mkdir(parents=True, exist_ok=True)
    record_id = uuid.uuid4().hex[:12]
    data = {"id": record_id, "ts": time.time(), **data}
    path = settings.records_dir / f"{kind}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=False) + "\n")
    return record_id
