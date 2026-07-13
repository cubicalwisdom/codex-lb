"""add request-log aggregates for history retention

Revision ID: 20260712_000000_add_request_log_daily_aggregates
Revises: 20260710_010000_add_request_log_cache_write_tokens
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260712_000000_add_request_log_daily_aggregates"
down_revision = "20260710_010000_add_request_log_cache_write_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("request_log_aggregates"):
        op.create_table(
            "request_log_aggregates",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("bucket_start", sa.DateTime(), nullable=False),
            sa.Column("account_id", sa.String(), nullable=True),
            sa.Column("api_key_id", sa.String(), nullable=True),
            sa.Column("model", sa.String(), nullable=False),
            sa.Column("service_tier", sa.String(), nullable=True),
            sa.Column("error_code", sa.String(), nullable=True),
            sa.Column("request_count", sa.Integer(), nullable=False),
            sa.Column("input_tokens", sa.Integer(), nullable=False),
            sa.Column("output_tokens", sa.Integer(), nullable=False),
            sa.Column("cached_input_tokens", sa.Integer(), nullable=False),
            sa.Column("cost_usd", sa.Float(), nullable=False),
            sa.Column("error_count", sa.Integer(), nullable=False),
        )
    indexes = {
        str(index["name"])
        for index in sa.inspect(bind).get_indexes("request_log_aggregates")
        if index.get("name") is not None
    }
    if "idx_request_log_aggregates_bucket" not in indexes:
        op.create_index(
            "idx_request_log_aggregates_bucket",
            "request_log_aggregates",
            ["bucket_start"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("request_log_aggregates"):
        return
    indexes = {
        str(index["name"])
        for index in inspector.get_indexes("request_log_aggregates")
        if index.get("name") is not None
    }
    if "idx_request_log_aggregates_bucket" in indexes:
        op.drop_index("idx_request_log_aggregates_bucket", table_name="request_log_aggregates")
    op.drop_table("request_log_aggregates")
