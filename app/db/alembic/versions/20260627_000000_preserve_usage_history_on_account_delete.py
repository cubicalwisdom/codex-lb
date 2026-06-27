"""preserve usage history on account delete

Revision ID: 20260627_000000_preserve_usage_history_on_account_delete
Revises: 20260611_000000_merge_dashboard_guest_and_weekly_useragent_heads
Create Date: 2026-06-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260627_000000_preserve_usage_history_on_account_delete"
down_revision = "20260611_000000_merge_dashboard_guest_and_weekly_useragent_heads"
branch_labels = None
depends_on = None

_FK_NAMING = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def _account_fk_names(inspector: sa.Inspector, table_name: str) -> list[str]:
    fallback_name = f"fk_{table_name}_account_id_accounts"
    names: list[str] = []
    for foreign_key in inspector.get_foreign_keys(table_name):
        if foreign_key.get("referred_table") != "accounts":
            continue
        if foreign_key.get("constrained_columns") != ["account_id"]:
            continue
        if foreign_key.get("referred_columns") != ["id"]:
            continue
        name = foreign_key.get("name")
        names.append(str(name) if name else fallback_name)
    return names


def _set_account_fk(*, table_name: str, ondelete: str, nullable: bool) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    fk_names = _account_fk_names(inspector, table_name)
    fk_name = f"fk_{table_name}_account_id_accounts"

    with op.batch_alter_table(table_name, naming_convention=_FK_NAMING) as batch_op:
        for existing_fk_name in fk_names:
            batch_op.drop_constraint(existing_fk_name, type_="foreignkey")
        batch_op.alter_column("account_id", existing_type=sa.String(), nullable=nullable)
        batch_op.create_foreign_key(
            fk_name,
            "accounts",
            ["account_id"],
            ["id"],
            ondelete=ondelete,
        )


def upgrade() -> None:
    _set_account_fk(table_name="usage_history", ondelete="SET NULL", nullable=True)
    _restore_usage_history_expression_indexes()
    _set_account_fk(table_name="additional_usage_history", ondelete="SET NULL", nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM usage_history WHERE account_id IS NULL"))
    bind.execute(sa.text("DELETE FROM additional_usage_history WHERE account_id IS NULL"))
    _set_account_fk(table_name="usage_history", ondelete="CASCADE", nullable=False)
    _restore_usage_history_expression_indexes()
    _set_account_fk(table_name="additional_usage_history", ondelete="CASCADE", nullable=False)


def _restore_usage_history_expression_indexes() -> None:
    op.create_index(
        "idx_usage_window_account_time",
        "usage_history",
        [sa.text("coalesce(window, 'primary')"), "account_id", "recorded_at"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "idx_usage_window_account_latest",
        "usage_history",
        [sa.text("coalesce(window, 'primary')"), "account_id", sa.text("recorded_at DESC"), sa.text("id DESC")],
        unique=False,
        if_not_exists=True,
    )
