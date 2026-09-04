"""pytest 全局配置：默认关闭外部依赖 + 数据库隔离，保证 mock 测试离线、确定。

第 1/2 阶段的关键词检索、演示模式等测试依赖「无外部 Key」的前提；
一旦本机 .env 填了真实 DeepSeek/飞书/方舟凭证，这些测试会被真实外部依赖污染。
本 fixture 在每次测试前清空相关配置，并重绑定 SQLite 到临时文件。
需要真实配置的用例再自行 monkeypatch 覆盖。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.db import base, models  # noqa: F401  确保模型注册到 metadata
from app.main import app
from app.services.invite import create_invites
from app.services.rate_limit import chat_gate, limiter, sync_gate
from app.services.dify.tasks import task_registry


@pytest.fixture(autouse=True)
def _offline_external_deps(monkeypatch, tmp_path):
    # 清空外部依赖配置
    monkeypatch.setattr(config.settings, "deepseek_api_key", "")
    monkeypatch.setattr(config.settings, "chat_provider", "legacy")
    monkeypatch.setattr(config.settings, "dify_app_api_key", "")
    monkeypatch.setattr(config.settings, "ark_api_key", "")
    monkeypatch.setattr(config.settings, "ark_embedding_model", "")
    monkeypatch.setattr(config.settings, "feishu_app_id", "")
    monkeypatch.setattr(config.settings, "feishu_app_secret", "")
    monkeypatch.setattr(config.settings, "feishu_doc_tokens", [])
    monkeypatch.setattr(config.settings, "feishu_mentor_id", "")
    monkeypatch.setattr(config.settings, "records_dir", tmp_path)
    monkeypatch.setattr(config.settings, "vectordb_dir", tmp_path / "vectordb")
    monkeypatch.setattr(config.settings, "app_env", "development")
    monkeypatch.setattr(config.settings, "enable_feishu_oauth", False)
    monkeypatch.setattr(config.settings, "service_token", "")
    monkeypatch.setattr(config.settings, "admin_user_ids", set())
    monkeypatch.setattr(config.settings, "admin_open_ids", set())
    monkeypatch.setattr(config.settings, "allow_all_authenticated_docs", True)
    monkeypatch.setattr(config.settings, "doc_acl", {})
    monkeypatch.setattr(config.settings, "prompt_guard_mode", "monitor")
    monkeypatch.setattr(config.settings, "output_guard_mode", "monitor")

    # 数据库隔离：重绑定 engine / SessionLocal 到临时 SQLite 文件
    test_engine = base.make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    test_session = base.make_session_factory(test_engine)
    base.Base.metadata.create_all(bind=test_engine)
    monkeypatch.setattr(base, "engine", test_engine)
    monkeypatch.setattr(base, "SessionLocal", test_session)
    limiter.reset()
    chat_gate.reset()
    sync_gate.reset()
    task_registry.reset()
    yield
    limiter.reset()
    chat_gate.reset()
    sync_gate.reset()
    task_registry.reset()


@pytest.fixture
def api_client() -> TestClient:
    with TestClient(app) as client:
        yield client


@pytest.fixture
def auth_client() -> TestClient:
    with TestClient(app) as client:
        code = create_invites(1, "pytest")[0]
        response = client.post(
            "/api/v1/auth/invite", json={"invite_code": code, "nickname": "测试用户"}
        )
        assert response.status_code == 200
        assert config.settings.session_cookie_name in client.cookies
        yield client


@pytest.fixture
def service_auth(monkeypatch) -> dict[str, str]:
    monkeypatch.setattr(config.settings, "service_token", "pytest-service-token")
    return {"X-InTeam-Service-Token": "pytest-service-token"}
