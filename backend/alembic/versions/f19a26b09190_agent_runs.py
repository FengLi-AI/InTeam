"""Add isolated Agent run history; existing business tables unchanged."""
from alembic import op
import sqlalchemy as sa
revision = "f19a26b09190"
down_revision = "e73b4f9a20c1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("agent_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scenario", sa.String(24), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("parent_run_id", sa.String(32), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("events_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("created_ts", sa.DateTime(), nullable=False),
        sa.Column("finished_ts", sa.DateTime(), nullable=True))
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])


def downgrade():
    op.drop_index("ix_agent_runs_user_id", table_name="agent_runs")
    op.drop_table("agent_runs")
