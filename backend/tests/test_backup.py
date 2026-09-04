"""TOS 备份：一致性快照、校验、恢复和无备份首启。"""
from __future__ import annotations

import io
import sqlite3
from pathlib import Path

from botocore.exceptions import ClientError

from app.core import config
from app.core.config import Settings
from app.services.backup import create_backup, restore_if_needed


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        self.objects[(bucket, key)] = Path(filename).read_bytes()

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, **_kwargs) -> None:
        self.objects[(Bucket, Key)] = bytes(Body)

    def get_object(self, *, Bucket: str, Key: str):
        value = self.objects.get((Bucket, Key))
        if value is None:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": io.BytesIO(value)}

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        Path(filename).write_bytes(self.objects[(bucket, key)])

    def list_objects_v2(self, *, Bucket: str, Prefix: str):
        return {
            "Contents": [
                {"Key": key}
                for bucket, key in self.objects
                if bucket == Bucket and key.startswith(Prefix)
            ]
        }

    def delete_objects(self, *, Bucket: str, Delete: dict) -> None:
        for item in Delete["Objects"]:
            self.objects.pop((Bucket, item["Key"]), None)


def _enable_backup(monkeypatch, tmp_path):
    database = tmp_path / "data" / "app.db"
    records = tmp_path / "data" / "records"
    monkeypatch.setattr(config.settings, "database_url", f"sqlite:///{database}")
    monkeypatch.setattr(config.settings, "records_dir", records)
    monkeypatch.setattr(config.settings, "tos_backup_enabled", True)
    monkeypatch.setattr(config.settings, "s3_bucket", "inteam-test")
    monkeypatch.setattr(config.settings, "s3_backup_prefix", "inteam/backups")
    monkeypatch.setattr(config.settings, "backup_retention_count", 20)
    return database, records


def test_backup_and_restore_round_trip(monkeypatch, tmp_path):
    database, records = _enable_backup(monkeypatch, tmp_path)
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES ('test-head')")
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample VALUES ('kept')")
        connection.commit()
    records.mkdir(parents=True)
    (records / "qa.jsonl").write_bytes(b'{"ok":1}\n{"partial":')

    client = FakeS3()
    key = create_backup(client=client)
    assert key and key.endswith(".tar.gz")
    assert ("inteam-test", "inteam/backups/latest.json") in client.objects

    database.unlink()
    for item in records.iterdir():
        item.unlink()
    assert restore_if_needed(client=client) is True

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone() == ("kept",)
    assert (records / "qa.jsonl").read_bytes() == b'{"ok":1}\n'


def test_restore_without_remote_backup_is_clean_first_start(monkeypatch, tmp_path):
    database, _records = _enable_backup(monkeypatch, tmp_path)
    assert not database.exists()
    assert restore_if_needed(client=FakeS3()) is False
    assert not database.exists()


def test_production_sqlite_requires_tos_backup(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SESSION_SECRET", "s" * 32)
    monkeypatch.setenv("INVITE_PEPPER", "p" * 32)
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://inteam.example.com")
    monkeypatch.setenv("ALLOWED_HOSTS", "api.inteam.example.com")
    monkeypatch.setenv("ALLOW_ALL_AUTHENTICATED_DOCS", "true")
    monkeypatch.setenv("CHAT_PROVIDER", "legacy")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'app.db'}")
    monkeypatch.setenv("TOS_BACKUP_ENABLED", "false")

    try:
        Settings()
    except ValueError as exc:
        assert "TOS_BACKUP_ENABLED" in str(exc)
    else:
        raise AssertionError("production SQLite must require TOS backup")
