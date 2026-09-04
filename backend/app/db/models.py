"""数据模型：转人工工单 / 反馈 / FAQ。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _utcnow() -> datetime:
    # naive UTC：SQLite 不保留时区，统一存 naive 以便读写比较一致
    return datetime.now(timezone.utc).replace(tzinfo=None)


class EscalateTicket(Base):
    """转人工工单：时间 / 问题 / 接收人 / 状态 / 消息 ID。"""

    __tablename__ = "escalate_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), default="", index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    question: Mapped[str] = mapped_column(Text)
    context: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    receiver: Mapped[str] = mapped_column(String(128), default="")
    receiver_type: Mapped[str] = mapped_column(String(32), default="open_id")
    status: Mapped[str] = mapped_column(String(16), default="sent")  # sent | failed
    message_id: Mapped[str] = mapped_column(String(128), default="")
    error: Mapped[str] = mapped_column(Text, default="")


class Feedback(Base):
    """答案反馈：有帮助/无帮助 + 盲区标记。"""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    answer_id: Mapped[str] = mapped_column(String(64), index=True)
    question: Mapped[str] = mapped_column(Text, default="")
    helpful: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str] = mapped_column(Text, default="")
    blind_spot: Mapped[bool] = mapped_column(Boolean, default=False)


class Faq(Base):
    """沉淀的常见问答：候选 → 人工确认后生效。"""

    __tablename__ = "faq"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(16), default="candidate")  # candidate | confirmed
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    confirmed_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class User(Base):
    """登录用户（飞书身份）。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    open_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    avatar_url: Mapped[str] = mapped_column(String(512), default="")
    department: Mapped[str] = mapped_column(String(256), default="")
    position: Mapped[str] = mapped_column(String(256), default="")
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Session(Base):
    """登录会话：token → 用户。"""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InviteCode(Base):
    """邀请码（每人一码）：兑换即绑定用户，可作废。"""

    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="unused")  # unused | used | revoked
    bound_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(String(256), default="")
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    used_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Contact(Base):
    """关键同事（v1.0 为虚拟数据）。"""

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
    department: Mapped[str] = mapped_column(String(128), default="")
    position: Mapped[str] = mapped_column(String(128), default="")
    duty: Mapped[str] = mapped_column(String(256), default="")  # 一句话职责
    when_to_ask: Mapped[str] = mapped_column(String(256), default="")  # 什么时候找 TA
    avatar_emoji: Mapped[str] = mapped_column(String(16), default="👤")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class UserLabel(Base):
    """用户对同事的备注标签（沉淀到个人记忆）。"""

    __tablename__ = "user_labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    contact_id: Mapped[int] = mapped_column(Integer, index=True)
    label: Mapped[str] = mapped_column(String(128))
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Todo(Base):
    """待办事项（入职任务 + 自定义），支持排期与提醒。"""

    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(256))
    note: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[str] = mapped_column(String(16), default="")  # YYYY-MM-DD
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | done
    priority: Mapped[int] = mapped_column(Integer, default=0)  # 0 普通 / 1 高优
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OAuthState(Base):
    """OAuth CSRF state：只保存哈希，短期有效且一次性消费。"""

    __tablename__ = "oauth_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChatConversation(Base):
    """InTeam 本地会话与 Dify conversation_id 的用户隔离映射。"""

    __tablename__ = "chat_conversations"
    __table_args__ = (
        UniqueConstraint("user_id", "local_session_id", name="uq_chat_conversation_user_session"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    local_session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dify_conversation_id: Mapped[str] = mapped_column(String(128), default="")
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ChatMessage(Base):
    """服务端登记的 Dify 回答，用于反馈归属和后续会话能力。"""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    conversation_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    dify_message_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    answer_status: Mapped[str] = mapped_column(String(32), default="limited")
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class OnboardingProgress(Base):
    """当前用户的六主题上手地图进度。"""

    __tablename__ = "onboarding_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "topic_key", name="uq_onboarding_progress_user_topic"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    topic_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="not_started")
    updated_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AgentSuggestion(Base):
    """Dify 生成但尚未经用户确认的候选行动。"""

    __tablename__ = "agent_suggestions"
    __table_args__ = (
        UniqueConstraint("user_id", "client_key", name="uq_agent_suggestions_user_client"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    chat_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    client_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), default="")
    action_type: Mapped[str] = mapped_column(String(24), default="other")
    due_hint: Mapped[str] = mapped_column(String(24), default="no_date")
    topic_key: Mapped[str] = mapped_column(String(64), default="")
    related_contact_key: Mapped[str] = mapped_column(String(64), default="")
    decision: Mapped[str] = mapped_column(String(24), default="pending")
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    decided_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Action(Base):
    """用户已经确认的个人入职行动。"""

    __tablename__ = "actions"
    __table_args__ = (
        UniqueConstraint("source_suggestion_id", name="uq_actions_source_suggestion"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="open")
    due_date: Mapped[str] = mapped_column(String(16), default="")
    topic_key: Mapped[str] = mapped_column(String(64), default="")
    source_type: Mapped[str] = mapped_column(String(24), default="manual")
    source_suggestion_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
