"""initial schema: ticket_log + resolved_ticket

Revision ID: 0001
Revises:
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticket_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("ticket_text", sa.Text, nullable=False),
        sa.Column("category", sa.String(32)),
        sa.Column("priority", sa.String(16)),
        sa.Column("assigned_team", sa.String(64)),
        sa.Column("impact", sa.String(16)),
        sa.Column("urgency", sa.String(16)),
        sa.Column("reasoning", sa.Text),
        sa.Column("model", sa.String(64)),
        sa.Column("prompt_tokens", sa.Integer),
        sa.Column("completion_tokens", sa.Integer),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("ok", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("error", sa.Text),
        sa.Column("embedding", sa.JSON),
        sa.Column("reused_from_id", sa.Integer),
        sa.Column("similarity", sa.Float),
        sa.Column("confidence", sa.String(8)),
        sa.Column("needs_review", sa.Boolean),
    )
    op.create_table(
        "resolved_ticket",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ticket_text", sa.Text, nullable=False),
        sa.Column("category", sa.String(32)),
        sa.Column("resolution", sa.Text),
        sa.Column("embedding", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("resolved_ticket")
    op.drop_table("ticket_log")
