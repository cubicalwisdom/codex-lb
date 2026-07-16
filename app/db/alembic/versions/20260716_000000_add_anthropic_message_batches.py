"""add durable Anthropic Message Batches resources

Revision ID: 20260716_000000_add_anthropic_message_batches
Revises: 20260712_000000_add_request_log_daily_aggregates
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260716_000000_add_anthropic_message_batches"
down_revision = "20260712_000000_add_request_log_daily_aggregates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("anthropic_message_batches"):
        op.create_table(
            "anthropic_message_batches",
            sa.Column("id", sa.String(length=255), nullable=False),
            sa.Column("api_key_scope", sa.String(length=255), nullable=False),
            sa.Column("processing_status", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
            sa.Column("ended_at", sa.BigInteger(), nullable=True),
            sa.Column("expires_at", sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    indexes = _index_names(bind, "anthropic_message_batches")
    if "idx_anthropic_message_batches_scope_created" not in indexes:
        op.create_index(
            "idx_anthropic_message_batches_scope_created",
            "anthropic_message_batches",
            ["api_key_scope", "created_at"],
            unique=False,
        )
    if not inspector.has_table("anthropic_message_batch_items"):
        op.create_table(
            "anthropic_message_batch_items",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("batch_id", sa.String(length=255), nullable=False),
            sa.Column("sequence", sa.BigInteger(), nullable=False),
            sa.Column("custom_id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("params_json", sa.Text(), nullable=False),
            sa.Column("result_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(["batch_id"], ["anthropic_message_batches.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("batch_id", "custom_id", name="uq_anthropic_message_batch_items_custom_id"),
        )
    item_indexes = _index_names(bind, "anthropic_message_batch_items")
    if "idx_anthropic_message_batch_items_batch_sequence" not in item_indexes:
        op.create_index(
            "idx_anthropic_message_batch_items_batch_sequence",
            "anthropic_message_batch_items",
            ["batch_id", "sequence"],
            unique=False,
        )
    if "idx_anthropic_message_batch_items_batch_status" not in item_indexes:
        op.create_index(
            "idx_anthropic_message_batch_items_batch_status",
            "anthropic_message_batch_items",
            ["batch_id", "status"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("anthropic_message_batch_items"):
        indexes = _index_names(bind, "anthropic_message_batch_items")
        if "idx_anthropic_message_batch_items_batch_status" in indexes:
            op.drop_index("idx_anthropic_message_batch_items_batch_status", table_name="anthropic_message_batch_items")
        if "idx_anthropic_message_batch_items_batch_sequence" in indexes:
            op.drop_index(
                "idx_anthropic_message_batch_items_batch_sequence",
                table_name="anthropic_message_batch_items",
            )
        op.drop_table("anthropic_message_batch_items")
    if inspector.has_table("anthropic_message_batches"):
        indexes = _index_names(bind, "anthropic_message_batches")
        if "idx_anthropic_message_batches_scope_created" in indexes:
            op.drop_index("idx_anthropic_message_batches_scope_created", table_name="anthropic_message_batches")
        op.drop_table("anthropic_message_batches")


def _index_names(bind: sa.engine.Connection, table_name: str) -> set[str]:
    return {
        str(index["name"])
        for index in sa.inspect(bind).get_indexes(table_name)
        if index.get("name") is not None
    }
