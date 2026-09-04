"""应用配置：从环境变量读取，提供默认值。"""
from __future__ import annotations

import os
import json
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

# 定位目录：backend/app/core/config.py
BACKEND_DIR = Path(__file__).resolve().parents[2]   # backend/
PROJECT_ROOT = BACKEND_DIR.parent                    # inteam/

# 优先读项目根 .env，其次 backend/.env
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env", override=False)


class Settings:
    """集中管理配置；密钥只在此处读取，不进入日志或前端。"""

    def __init__(self) -> None:
        # ---- 运行环境与安全边界 ----
        # veFaaS 等运行环境可能注入通用的 APP_ENV；项目专属变量优先，
        # 同时保留 APP_ENV 作为本地开发的向后兼容入口。
        self.app_env = os.getenv(
            "INTEAM_APP_ENV", os.getenv("APP_ENV", "development")
        ).strip().lower()
        self.allowed_origins = self._csv(
            os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
        )
        self.allowed_hosts = self._csv(
            os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        )
        self.max_request_body_bytes = int(os.getenv("MAX_REQUEST_BODY_BYTES", "65536"))
        self.session_cookie_name = os.getenv("SESSION_COOKIE_NAME", "inteam_session").strip()
        self.session_secret = os.getenv("SESSION_SECRET", "dev-only-change-me").strip()
        self.invite_pepper = os.getenv("INVITE_PEPPER", self.session_secret).strip()
        self.service_token = os.getenv("SERVICE_TOKEN", "").strip()
        self.admin_user_ids = {
            int(value) for value in self._csv(os.getenv("ADMIN_USER_IDS", "")) if value.isdigit()
        }
        self.admin_open_ids = set(self._csv(os.getenv("ADMIN_OPEN_IDS", "")))
        self.enable_feishu_oauth = self._bool(os.getenv("ENABLE_FEISHU_OAUTH", "false"))
        self.oauth_state_ttl_seconds = int(os.getenv("OAUTH_STATE_TTL_SECONDS", "600"))
        self.allow_all_authenticated_docs = self._bool(
            os.getenv("ALLOW_ALL_AUTHENTICATED_DOCS", "true" if self.app_env == "development" else "false")
        )
        self.doc_acl = self._json_mapping(os.getenv("DOC_ACL_JSON", "{}"))
        self.allowed_source_hosts = set(
            self._csv(
                os.getenv(
                    "ALLOWED_SOURCE_HOSTS",
                    "feishu.cn,open.feishu.cn",
                )
            )
        )
        guard_default = "monitor" if self.app_env in {"development", "test"} else "enforce"
        self.prompt_guard_mode = os.getenv("PROMPT_GUARD_MODE", guard_default).strip().lower()
        self.output_guard_mode = os.getenv("OUTPUT_GUARD_MODE", guard_default).strip().lower()
        self.csp_mode = os.getenv("CSP_MODE", "report-only").strip().lower()
        self.sentry_dsn = os.getenv("SENTRY_DSN", "").strip()

        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash-vision-exp")
        self.max_tokens = int(os.getenv("MAX_TOKENS", "1024"))
        self.timeout_seconds = float(os.getenv("TIMEOUT_SECONDS", "60"))
        self.confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.4"))

        # ---- InTeam v1.6：Dify Chatflow（先以 additive gateway 接入） ----
        self.chat_provider = os.getenv("CHAT_PROVIDER", "legacy").strip().lower()
        self.dify_base_url = os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1").rstrip("/")
        self.dify_app_api_key = os.getenv("DIFY_APP_API_KEY", "").strip()
        self.dify_connect_timeout_seconds = float(
            os.getenv("DIFY_CONNECT_TIMEOUT_SECONDS", "10")
        )
        self.dify_read_timeout_seconds = float(
            os.getenv("DIFY_READ_TIMEOUT_SECONDS", "120")
        )
        self.knowledge_dir = Path(
            os.getenv("KNOWLEDGE_DIR", str(BACKEND_DIR / "data" / "knowledge"))
        )
        self.records_dir = Path(
            os.getenv("RECORDS_DIR", str(BACKEND_DIR / "data" / "records"))
        )

        # ---- 第 2 阶段：飞书文档只读同步 ----
        self.feishu_app_id = os.getenv("FEISHU_APP_ID", "").strip()
        self.feishu_app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
        self.feishu_base_url = os.getenv("FEISHU_BASE_URL", "https://open.feishu.cn")
        self.feishu_doc_tokens = [
            t.strip() for t in os.getenv("FEISHU_DOC_TOKENS", "").split(",") if t.strip()
        ]
        # 出处跳转链接前缀；飞书通用跳转，可覆盖为租户域名
        self.feishu_doc_url_prefix = os.getenv(
            "FEISHU_DOC_URL_PREFIX", "https://feishu.cn/docx/"
        )

        # ---- 第 2 阶段：火山方舟 Embedding ----
        self.ark_api_key = os.getenv("ARK_API_KEY", "").strip()
        self.ark_base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        self.ark_embedding_model = os.getenv("ARK_EMBEDDING_MODEL", "").strip()

        # ---- 第 2 阶段：向量库目录 ----
        # 项目位于 exFAT 磁盘时 Chroma 会报 "readonly database"，故默认放系统盘，可用 VECTORDB_DIR 覆盖
        default_vectordb = Path.home() / "Library" / "Application Support" / "InTeam" / "vectordb"
        self.vectordb_dir = Path(os.getenv("VECTORDB_DIR", str(default_vectordb)))

        # ---- 第 3 阶段：转人工通知 + 关系型数据库 ----
        self.feishu_mentor_id = os.getenv("FEISHU_MENTOR_ID", "").strip()
        self.feishu_receive_id_type = os.getenv("FEISHU_RECEIVE_ID_TYPE", "open_id")
        self.database_url = os.getenv(
            "DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'data' / 'app.db'}"
        )

        # ---- 线上 SQLite 持久化：TOS S3 兼容备份 ----
        self.tos_backup_enabled = self._bool(os.getenv("TOS_BACKUP_ENABLED", "false"))
        self.s3_endpoint = os.getenv("S3_ENDPOINT", "").strip().rstrip("/")
        self.s3_access_key = os.getenv("S3_ACCESS_KEY", "").strip()
        self.s3_secret_key = os.getenv("S3_SECRET_KEY", "").strip()
        self.s3_bucket = os.getenv("S3_BUCKET", "").strip()
        self.s3_region = os.getenv("S3_REGION", "cn-beijing").strip()
        self.s3_backup_prefix = os.getenv("S3_BACKUP_PREFIX", "inteam/backups").strip().strip("/")
        self.backup_interval_seconds = int(os.getenv("BACKUP_INTERVAL_SECONDS", "3600"))
        self.backup_retention_count = int(os.getenv("BACKUP_RETENTION_COUNT", "24"))

        # ---- 第 4 阶段：飞书 OAuth 登录 ----
        self.feishu_auth_redirect_uri = os.getenv(
            "FEISHU_AUTH_REDIRECT_URI", "http://localhost:3000/auth/callback"
        )
        self.session_ttl_days = int(os.getenv("SESSION_TTL_DAYS", "30"))

        # ---- 资源保护（首版默认值，可按 Staging 指标调整） ----
        self.invite_attempt_limit = int(os.getenv("INVITE_ATTEMPT_LIMIT", "5"))
        self.invite_attempt_window_seconds = int(os.getenv("INVITE_ATTEMPT_WINDOW_SECONDS", "900"))
        self.chat_rate_limit = int(os.getenv("CHAT_RATE_LIMIT", "10"))
        self.chat_rate_window_seconds = int(os.getenv("CHAT_RATE_WINDOW_SECONDS", "60"))
        self.chat_hourly_limit = int(os.getenv("CHAT_HOURLY_LIMIT", "60"))
        self.chat_concurrency_per_user = int(os.getenv("CHAT_CONCURRENCY_PER_USER", "2"))
        self.chat_concurrency_global = int(os.getenv("CHAT_CONCURRENCY_GLOBAL", "20"))
        self.escalate_rate_limit = int(os.getenv("ESCALATE_RATE_LIMIT", "5"))
        self.escalate_rate_window_seconds = int(os.getenv("ESCALATE_RATE_WINDOW_SECONDS", "3600"))
        self.feedback_rate_limit = int(os.getenv("FEEDBACK_RATE_LIMIT", "30"))
        self.feedback_rate_window_seconds = int(os.getenv("FEEDBACK_RATE_WINDOW_SECONDS", "3600"))

        self.validate_security_settings()

    @staticmethod
    def _csv(raw: str) -> list[str]:
        return [value.strip() for value in raw.split(",") if value.strip()]

    @staticmethod
    def _bool(raw: str) -> bool:
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _json_mapping(raw: str) -> dict[str, list[str]]:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("DOC_ACL_JSON 必须是合法 JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("DOC_ACL_JSON 必须是对象")
        result: dict[str, list[str]] = {}
        for key, items in value.items():
            if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
                raise ValueError("DOC_ACL_JSON 的值必须是字符串数组")
            result[str(key)] = items
        return result

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def docs_enabled(self) -> bool:
        return self.app_env in {"development", "test"}

    @property
    def is_secure_environment(self) -> bool:
        return self.app_env in {"staging", "production"}

    def validate_security_settings(self) -> None:
        if self.app_env not in {"development", "staging", "production", "test"}:
            raise ValueError("APP_ENV 必须是 development/staging/production/test")
        if self.prompt_guard_mode not in {"off", "monitor", "enforce"}:
            raise ValueError("PROMPT_GUARD_MODE 必须是 off/monitor/enforce")
        if self.output_guard_mode not in {"off", "monitor", "enforce"}:
            raise ValueError("OUTPUT_GUARD_MODE 必须是 off/monitor/enforce")
        if self.csp_mode not in {"off", "report-only", "enforce"}:
            raise ValueError("CSP_MODE 必须是 off/report-only/enforce")
        if self.chat_provider not in {"legacy", "dify"}:
            raise ValueError("CHAT_PROVIDER 必须是 legacy/dify")
        if self.chat_provider == "dify" and not self.dify_app_api_key:
            raise ValueError("CHAT_PROVIDER=dify 时必须配置 DIFY_APP_API_KEY")
        dify_url = urlparse(self.dify_base_url)
        if dify_url.scheme not in {"http", "https"} or not dify_url.netloc:
            raise ValueError("DIFY_BASE_URL 必须是合法的 HTTP(S) URL")
        if self.is_secure_environment and dify_url.scheme != "https":
            raise ValueError("Staging/生产环境的 DIFY_BASE_URL 必须使用 HTTPS")
        if self.is_secure_environment:
            if self.session_secret == "dev-only-change-me" or len(self.session_secret) < 32:
                raise ValueError("Staging/生产环境必须配置至少 32 字符的 SESSION_SECRET")
            if not self.invite_pepper or len(self.invite_pepper) < 32:
                raise ValueError("Staging/生产环境必须配置至少 32 字符的 INVITE_PEPPER")
            if not self.allowed_origins or not self.allowed_hosts:
                raise ValueError("Staging/生产环境必须配置 ALLOWED_ORIGINS 和 ALLOWED_HOSTS")
            if not self.allow_all_authenticated_docs and not self.doc_acl:
                raise ValueError(
                    "Staging/生产环境必须配置 DOC_ACL_JSON，或显式设置 ALLOW_ALL_AUTHENTICATED_DOCS=true"
                )
            if self.database_url.startswith("sqlite") and not self.tos_backup_enabled:
                raise ValueError("Staging/生产环境使用 SQLite 时必须启用 TOS_BACKUP_ENABLED")
        if self.tos_backup_enabled:
            missing = [
                key
                for key, value in {
                    "S3_ENDPOINT": self.s3_endpoint,
                    "S3_ACCESS_KEY": self.s3_access_key,
                    "S3_SECRET_KEY": self.s3_secret_key,
                    "S3_BUCKET": self.s3_bucket,
                    "S3_REGION": self.s3_region,
                    "S3_BACKUP_PREFIX": self.s3_backup_prefix,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError(f"启用 TOS 备份时缺少配置：{','.join(missing)}")
            endpoint = urlparse(self.s3_endpoint)
            if endpoint.scheme not in {"http", "https"} or not endpoint.netloc:
                raise ValueError("S3_ENDPOINT 必须是合法的 HTTP(S) URL")
            if self.is_secure_environment and endpoint.scheme != "https":
                raise ValueError("Staging/生产环境的 S3_ENDPOINT 必须使用 HTTPS")
            if self.backup_interval_seconds < 60:
                raise ValueError("BACKUP_INTERVAL_SECONDS 不能小于 60")
            if self.backup_retention_count < 2:
                raise ValueError("BACKUP_RETENTION_COUNT 不能小于 2")

    @property
    def has_key(self) -> bool:
        """是否配置了真实模型 Key（决定走真实模型还是演示模式）。"""
        return bool(self.deepseek_api_key)

    @property
    def has_dify(self) -> bool:
        """是否已配置 Dify Chatflow Service API。"""
        return bool(self.dify_app_api_key)

    @property
    def has_feishu(self) -> bool:
        """是否配置了飞书只读应用与文档清单。"""
        return bool(self.feishu_app_id and self.feishu_app_secret and self.feishu_doc_tokens)

    @property
    def has_ark(self) -> bool:
        """是否配置了方舟 Embedding（决定是否启用向量检索）。"""
        return bool(self.ark_api_key and self.ark_embedding_model)

    @property
    def has_mentor(self) -> bool:
        """是否配置了转人工接收人（决定转人工能否真实发消息）。"""
        return bool(self.feishu_mentor_id)


settings = Settings()
