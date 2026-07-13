"""add Responses lifecycle resources

Revision ID: 20260710_000000_add_responses_lifecycle_resources
Revises: 20260627_000000_preserve_usage_history_on_account_delete
Create Date: 2026-07-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260710_000000_add_responses_lifecycle_resources"
down_revision = "20260627_000000_preserve_usage_history_on_account_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("stored_conversations"):
        op.create_table(
            "stored_conversations",
            sa.Column("id", sa.String(length=255), nullable=False),
            sa.Column("api_key_scope", sa.String(length=255), nullable=False),
            sa.Column("metadata_json", sa.Text(), server_default=sa.text("'{}'"), nullable=False),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if "idx_stored_conversations_scope_created" not in _index_names(bind, "stored_conversations"):
        op.create_index(
            "idx_stored_conversations_scope_created",
            "stored_conversations",
            ["api_key_scope", "created_at"],
            unique=False,
        )
    if not inspector.has_table("stored_responses"):
        op.create_table(
            "stored_responses",
            sa.Column("id", sa.String(length=255), nullable=False),
            sa.Column("api_key_scope", sa.String(length=255), nullable=False),
            sa.Column("upstream_response_id", sa.String(length=255), nullable=True),
            sa.Column("conversation_id", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("background", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("request_json", sa.Text(), nullable=False),
            sa.Column("input_items_json", sa.Text(), nullable=False),
            sa.Column("response_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
            sa.Column("completed_at", sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    response_indexes = _index_names(bind, "stored_responses")
    if "idx_stored_responses_scope_created" not in response_indexes:
        op.create_index(
            "idx_stored_responses_scope_created",
            "stored_responses",
            ["api_key_scope", "created_at"],
            unique=False,
        )
    if "idx_stored_responses_scope_upstream" not in response_indexes:
        op.create_index(
            "idx_stored_responses_scope_upstream",
            "stored_responses",
            ["api_key_scope", "upstream_response_id"],
            unique=False,
        )
    if not inspector.has_table("stored_conversation_items"):
        op.create_table(
            "stored_conversation_items",
            sa.Column("id", sa.String(length=255), nullable=False),
            sa.Column("conversation_id", sa.String(length=255), nullable=False),
            sa.Column("sequence", sa.BigInteger(), nullable=False),
            sa.Column("item_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(["conversation_id"], ["stored_conversations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "conversation_id",
                "sequence",
                name="uq_stored_conversation_items_sequence",
            ),
        )
    if "idx_stored_conversation_items_conversation_sequence" not in _index_names(
        bind,
        "stored_conversation_items",
    ):
        op.create_index(
            "idx_stored_conversation_items_conversation_sequence",
            "stored_conversation_items",
            ["conversation_id", "sequence"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("stored_conversation_items"):
        if "idx_stored_conversation_items_conversation_sequence" in _index_names(
            bind,
            "stored_conversation_items",
        ):
            op.drop_index(
                "idx_stored_conversation_items_conversation_sequence",
                table_name="stored_conversation_items",
            )
        op.drop_table("stored_conversation_items")
    if inspector.has_table("stored_responses"):
        response_indexes = _index_names(bind, "stored_responses")
        if "idx_stored_responses_scope_upstream" in response_indexes:
            op.drop_index("idx_stored_responses_scope_upstream", table_name="stored_responses")
        if "idx_stored_responses_scope_created" in response_indexes:
            op.drop_index("idx_stored_responses_scope_created", table_name="stored_responses")
        op.drop_table("stored_responses")
    if inspector.has_table("stored_conversations"):
        if "idx_stored_conversations_scope_created" in _index_names(bind, "stored_conversations"):
            op.drop_index("idx_stored_conversations_scope_created", table_name="stored_conversations")
        op.drop_table("stored_conversations")


def _index_names(bind: sa.engine.Connection, table_name: str) -> set[str]:
    return {
        str(index["name"])
        for index in sa.inspect(bind).get_indexes(table_name)
        if index.get("name") is not None
    }
