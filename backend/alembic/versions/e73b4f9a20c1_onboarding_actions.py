"""Onboarding map, agent suggestions and confirmed actions

Revision ID: e73b4f9a20c1
Revises: c2f77a6e5b91
Create Date: 2026-09-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e73b4f9a20c1"
down_revision: Union[str, None] = "c2f77a6e5b91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "onboarding_progress",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("topic_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="not_started"),
        sa.Column("updated_ts", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "topic_key", name="uq_onboarding_progress_user_topic"
        ),
    )
    op.create_index(
        "ix_onboarding_progress_user_id", "onboarding_progress", ["user_id"]
    )

    op.create_table(
        "agent_suggestions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("chat_message_id", sa.Integer(), nullable=True),
        sa.Column("client_key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("action_type", sa.String(length=24), nullable=False, server_default="other"),
        sa.Column("due_hint", sa.String(length=24), nullable=False, server_default="no_date"),
        sa.Column("topic_key", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("related_contact_key", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("decision", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("created_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_ts", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "client_key", name="uq_agent_suggestions_user_client"
        ),
    )
    op.create_index("ix_agent_suggestions_user_id", "agent_suggestions", ["user_id"])
    op.create_index(
        "ix_agent_suggestions_conversation_id", "agent_suggestions", ["conversation_id"]
    )
    op.create_index(
        "ix_agent_suggestions_chat_message_id", "agent_suggestions", ["chat_message_id"]
    )

    op.create_table(
        "actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("due_date", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("topic_key", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("source_type", sa.String(length=24), nullable=False, server_default="manual"),
        sa.Column("source_suggestion_id", sa.Integer(), nullable=True),
        sa.Column("created_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_ts", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_suggestion_id", name="uq_actions_source_suggestion"),
    )
    op.create_index("ix_actions_user_id", "actions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_actions_user_id", table_name="actions")
    op.drop_table("actions")
    op.drop_index("ix_agent_suggestions_chat_message_id", table_name="agent_suggestions")
    op.drop_index("ix_agent_suggestions_conversation_id", table_name="agent_suggestions")
    op.drop_index("ix_agent_suggestions_user_id", table_name="agent_suggestions")
    op.drop_table("agent_suggestions")
    op.drop_index("ix_onboarding_progress_user_id", table_name="onboarding_progress")
    op.drop_table("onboarding_progress")
