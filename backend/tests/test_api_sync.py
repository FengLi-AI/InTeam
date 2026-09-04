"""同步 API 测试（mock 同步管道）。"""
from app.api import sync as sync_api
from app.core import config


def test_sync_unconfigured_returns_400(api_client, service_auth, monkeypatch):
    monkeypatch.setattr(config.settings, "feishu_app_id", "")
    monkeypatch.setattr(config.settings, "feishu_app_secret", "")
    monkeypatch.setattr(config.settings, "feishu_doc_tokens", [])
    r = api_client.post("/api/v1/sync", headers=service_auth)
    assert r.status_code == 400


def test_sync_ok(api_client, service_auth, monkeypatch):
    monkeypatch.setattr(config.settings, "feishu_app_id", "app")
    monkeypatch.setattr(config.settings, "feishu_app_secret", "sec")
    monkeypatch.setattr(config.settings, "feishu_doc_tokens", ["T1"])

    class _Item:
        doc_token = "T1"
        status = "synced"
        chunk_count = 3
        error = ""

    class _Result:
        synced = 1
        skipped = 0
        failed = 0
        quarantined = 0
        items = [_Item()]

    monkeypatch.setattr(sync_api, "run_sync", lambda: _Result())
    r = api_client.post("/api/v1/sync", headers=service_auth)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["synced"] == 1
    assert body["items"][0]["doc_token"] == "T1"


def test_sync_status(api_client, service_auth, monkeypatch, tmp_path):
    monkeypatch.setattr(config.settings, "records_dir", tmp_path)
    (tmp_path / "sync_state.json").write_text(
        '{"T1": {"last_sync_ts": 1, "status": "synced", "chunk_count": 3}}',
        encoding="utf-8",
    )
    r = api_client.get("/api/v1/sync/status", headers=service_auth)
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[0]["doc_token"] == "T1"
    assert items[0]["chunk_count"] == 3
