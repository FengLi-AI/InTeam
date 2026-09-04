"""SQLite 与必要运行记录的 TOS 备份、恢复和周期任务。"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import shutil
import sqlite3
import tarfile
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from sqlalchemy.engine import make_url

from ..core.config import settings


LOG = logging.getLogger("inteam.backup")


class BackupError(RuntimeError):
    """备份或恢复失败；错误信息不得包含凭据。"""


def sqlite_database_path(database_url: str | None = None) -> Path | None:
    """从 SQLAlchemy URL 解析 SQLite 文件路径；非 SQLite 返回 None。"""
    url = make_url(database_url or settings.database_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return None
    path = Path(url.database)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _alembic_version(path: Path) -> str:
    try:
        with sqlite3.connect(path) as connection:
            row = connection.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
            return str(row[0]) if row else ""
    except sqlite3.Error:
        return ""


def _sqlite_snapshot(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as source_db, sqlite3.connect(target) as target_db:
        source_db.backup(target_db)
        result = target_db.execute("PRAGMA integrity_check").fetchone()
    if not result or result[0] != "ok":
        raise BackupError("SQLite 快照完整性检查失败")


def _copy_jsonl_records(target_dir: Path) -> None:
    source_dir = settings.records_dir
    if not source_dir.exists():
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(source_dir.glob("*.jsonl")):
        data = source.read_bytes()
        if data and not data.endswith(b"\n"):
            newline = data.rfind(b"\n")
            data = data[: newline + 1] if newline >= 0 else b""
        (target_dir / source.name).write_bytes(data)


def _manifest(root: Path, created_at: str) -> dict:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    return {
        "format": 1,
        "service": "InTeam",
        "created_at": created_at,
        "alembic_version": _alembic_version(root / "db" / "app.db"),
        "files": files,
    }


def _safe_extract(archive: Path, target: Path) -> None:
    target_resolved = target.resolve()
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle.getmembers():
            member_path = (target / member.name).resolve()
            if target_resolved not in member_path.parents and member_path != target_resolved:
                raise BackupError("备份包包含非法路径")
            if member.issym() or member.islnk():
                raise BackupError("备份包不能包含链接")
        bundle.extractall(target)


def _verify_manifest(root: Path) -> dict:
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupError("备份清单不可读") from exc
    if manifest.get("format") != 1 or manifest.get("service") != "InTeam":
        raise BackupError("备份格式不受支持")
    files = manifest.get("files")
    if not isinstance(files, list):
        raise BackupError("备份文件清单无效")
    for item in files:
        if not isinstance(item, dict):
            raise BackupError("备份文件清单无效")
        relative = str(item.get("path", ""))
        path = (root / relative).resolve()
        if root.resolve() not in path.parents or not path.is_file():
            raise BackupError("备份文件清单不完整")
        if path.stat().st_size != int(item.get("size", -1)) or _sha256(path) != item.get("sha256"):
            raise BackupError("备份文件校验失败")
    database = root / "db" / "app.db"
    if not database.exists():
        raise BackupError("备份中缺少数据库")
    with sqlite3.connect(database) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchone()
    if not result or result[0] != "ok":
        raise BackupError("恢复数据库完整性检查失败")
    return manifest


def _is_missing_object(exc: ClientError) -> bool:
    code = str((exc.response.get("Error") or {}).get("Code", ""))
    return code in {"404", "NoSuchKey", "NoSuchObject", "NotFound"}


def create_backup(*, client=None) -> str | None:
    """创建一致性快照并上传；成功后才更新 latest 指针。"""
    if not settings.tos_backup_enabled:
        return None
    database = sqlite_database_path()
    if database is None:
        return None
    if not database.exists():
        LOG.info("backup skipped reason=database_missing")
        return None

    s3 = client or _client()
    created_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    object_key = f"{settings.s3_backup_prefix}/versions/{stamp}-{uuid.uuid4().hex[:8]}.tar.gz"
    pointer_key = f"{settings.s3_backup_prefix}/latest.json"

    with tempfile.TemporaryDirectory(prefix="inteam-backup-") as temp_name:
        temp = Path(temp_name)
        payload = temp / "payload"
        snapshot = payload / "db" / "app.db"
        _sqlite_snapshot(database, snapshot)
        _copy_jsonl_records(payload / "records")
        manifest = _manifest(payload, created_at)
        (payload / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        archive = temp / "backup.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            for path in sorted(payload.rglob("*")):
                if path.is_file():
                    bundle.add(path, arcname=path.relative_to(payload).as_posix())
        archive_digest = _sha256(archive)
        s3.upload_file(str(archive), settings.s3_bucket, object_key)
        pointer = {
            "format": 1,
            "service": "InTeam",
            "key": object_key,
            "sha256": archive_digest,
            "created_at": created_at,
            "alembic_version": manifest["alembic_version"],
        }
        s3.put_object(
            Bucket=settings.s3_bucket,
            Key=pointer_key,
            Body=json.dumps(pointer, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )

    _prune_backups(s3)
    LOG.info("backup completed key=%s", object_key)
    return object_key


def _prune_backups(client) -> None:
    try:
        prefix = f"{settings.s3_backup_prefix}/versions/"
        response = client.list_objects_v2(Bucket=settings.s3_bucket, Prefix=prefix)
        items = sorted(response.get("Contents", []), key=lambda item: item.get("Key", ""), reverse=True)
        stale = items[settings.backup_retention_count :]
        if stale:
            client.delete_objects(
                Bucket=settings.s3_bucket,
                Delete={"Objects": [{"Key": item["Key"]} for item in stale], "Quiet": True},
            )
    except Exception:  # noqa: BLE001 清理失败不能让有效备份失败
        LOG.exception("backup retention cleanup failed")


def restore_if_needed(*, client=None) -> bool:
    """仅在本地数据库不存在时，从 latest 指针恢复最近有效备份。"""
    if not settings.tos_backup_enabled:
        return False
    database = sqlite_database_path()
    if database is None or database.exists():
        return False
    s3 = client or _client()
    pointer_key = f"{settings.s3_backup_prefix}/latest.json"
    try:
        response = s3.get_object(Bucket=settings.s3_bucket, Key=pointer_key)
    except ClientError as exc:
        if _is_missing_object(exc):
            LOG.info("restore skipped reason=no_remote_backup")
            return False
        raise BackupError("读取最新备份指针失败") from exc

    try:
        raw_pointer = response["Body"].read()
        pointer = json.loads(raw_pointer)
        object_key = str(pointer["key"])
        expected_digest = str(pointer["sha256"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise BackupError("最新备份指针无效") from exc

    with tempfile.TemporaryDirectory(prefix="inteam-restore-") as temp_name:
        temp = Path(temp_name)
        archive = temp / "backup.tar.gz"
        s3.download_file(settings.s3_bucket, object_key, str(archive))
        if _sha256(archive) != expected_digest:
            raise BackupError("备份包校验失败")
        payload = temp / "payload"
        payload.mkdir()
        _safe_extract(archive, payload)
        manifest = _verify_manifest(payload)

        database.parent.mkdir(parents=True, exist_ok=True)
        restored_database = payload / "db" / "app.db"
        staging_database = database.with_suffix(database.suffix + ".restore")
        shutil.copy2(restored_database, staging_database)
        os.replace(staging_database, database)

        restored_records = payload / "records"
        if restored_records.exists():
            settings.records_dir.mkdir(parents=True, exist_ok=True)
            for source in restored_records.glob("*.jsonl"):
                shutil.copy2(source, settings.records_dir / source.name)

    LOG.info(
        "restore completed key=%s alembic_version=%s",
        object_key,
        manifest.get("alembic_version", ""),
    )
    return True


class BackupWorker:
    """单实例后台备份循环；生产 SQLite 部署必须限制后端 max instance=1。"""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not settings.tos_backup_enabled or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="inteam-backup", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            requested = self._wake.wait(settings.backup_interval_seconds)
            self._wake.clear()
            if self._stop.is_set():
                break
            # 合并同一轮请求内的连续写入（例如登录同时更新邀请码、用户和会话）。
            if requested and self._stop.wait(2):
                break
            while requested and self._wake.is_set():
                self._wake.clear()
                if self._stop.wait(2):
                    return
            try:
                create_backup()
            except Exception:  # noqa: BLE001 周期任务失败只告警，不终止应用
                LOG.exception("scheduled backup failed")

    def request(self) -> None:
        """数据库提交后唤醒备份线程；未启用 TOS 时保持无副作用。"""
        if settings.tos_backup_enabled:
            self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None


backup_worker = BackupWorker()
