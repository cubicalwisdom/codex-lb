"""add request log cache write tokens

Revision ID: 20260710_010000_add_request_log_cache_write_tokens
Revises: 20260710_000000_add_responses_lifecycle_resources
Create Date: 2026-07-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260710_010000_add_request_log_cache_write_tokens"
down_revision = "20260710_000000_add_responses_lifecycle_resources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "request_logs",
        sa.Column("cache_write_tokens", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("request_logs", "cache_write_tokens")
