"""P0 security hardening

Revision ID: 7f2b9c4d1a30
Revises: 344b18649483
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7f2b9c4d1a30"
down_revision: Union[str, None] = "344b18649483"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 旧版在进程导入时会 create_all，可能提前建出新表但不会补旧表字段。
    # 因此迁移按实际 schema 补齐，也能安全继续 SQLite 的非事务 DDL。
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    invite_columns = {column["name"]: column for column in inspector.get_columns("invite_codes")}
    code_length = getattr(invite_columns["code"]["type"], "length", None)
    # SQLite 不强制 VARCHAR(n) 长度，为改这个元数据重建整表反而会
    # 增加非事务 DDL 风险；PostgreSQL/MySQL 等实际限长的数据库才执行。
    if bind.dialect.name != "sqlite" and code_length is not None and code_length < 96:
        with op.batch_alter_table("invite_codes") as batch_op:
            batch_op.alter_column(
                "code",
                existing_type=sa.String(length=code_length),
                type_=sa.String(length=96),
                existing_nullable=False,
            )

    feedback_columns = {column["name"] for column in inspector.get_columns("feedback")}
    feedback_indexes = {index["name"] for index in inspector.get_indexes("feedback")}
    with op.batch_alter_table("feedback") as batch_op:
        if "user_id" not in feedback_columns:
            batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        if "ix_feedback_user_id" not in feedback_indexes:
            batch_op.create_index("ix_feedback_user_id", ["user_id"], unique=False)

    ticket_columns = {
        column["name"] for column in inspector.get_columns("escalate_tickets")
    }
    ticket_indexes = {
        index["name"] for index in inspector.get_indexes("escalate_tickets")
    }
    with op.batch_alter_table("escalate_tickets") as batch_op:
        if "user_id" not in ticket_columns:
            batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        if "idempotency_key" not in ticket_columns:
            batch_op.add_column(
                sa.Column(
                    "idempotency_key", sa.String(length=128), nullable=False, server_default=""
                )
            )
        if "ix_escalate_tickets_user_id" not in ticket_indexes:
            batch_op.create_index("ix_escalate_tickets_user_id", ["user_id"], unique=False)
        if "ix_escalate_tickets_idempotency_key" not in ticket_indexes:
            batch_op.create_index(
                "ix_escalate_tickets_idempotency_key", ["idempotency_key"], unique=False
            )

    if "oauth_states" not in tables:
        op.create_table(
            "oauth_states",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("state_hash", sa.String(length=128), nullable=False),
            sa.Column("created_ts", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_ts", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_ts", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_oauth_states_state_hash", "oauth_states", ["state_hash"], unique=True
        )
    else:
        oauth_indexes = {index["name"] for index in inspector.get_indexes("oauth_states")}
        if "ix_oauth_states_state_hash" not in oauth_indexes:
            op.create_index(
                "ix_oauth_states_state_hash", "oauth_states", ["state_hash"], unique=True
            )


def downgrade() -> None:
    op.drop_index("ix_oauth_states_state_hash", table_name="oauth_states")
    op.drop_table("oauth_states")
    with op.batch_alter_table("escalate_tickets") as batch_op:
        batch_op.drop_index("ix_escalate_tickets_idempotency_key")
        batch_op.drop_index("ix_escalate_tickets_user_id")
        batch_op.drop_column("idempotency_key")
        batch_op.drop_column("user_id")
    with op.batch_alter_table("feedback") as batch_op:
        batch_op.drop_index("ix_feedback_user_id")
        batch_op.drop_column("user_id")
    with op.batch_alter_table("invite_codes") as batch_op:
        batch_op.alter_column(
            "code",
            existing_type=sa.String(length=96),
            type_=sa.String(length=32),
            existing_nullable=False,
        )
