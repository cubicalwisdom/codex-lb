from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.script import ScriptDirectory

from app.db.migrate import _build_alembic_config


def test_responses_lifecycle_migration_is_single_head_and_reversible(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'responses-lifecycle.db'}"
    config = _build_alembic_config(database_url)
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["20260712_000000_add_request_log_daily_aggregates"]

    command.upgrade(config, "head")
    engine = sa.create_engine(database_url, future=True)
    try:
        inspector = sa.inspect(engine)
        assert inspector.has_table("stored_responses")
        assert inspector.has_table("stored_conversations")
        assert inspector.has_table("stored_conversation_items")

        command.downgrade(config, "20260627_000000_preserve_usage_history_on_account_delete")
        inspector = sa.inspect(engine)
        assert not inspector.has_table("stored_responses")
        assert not inspector.has_table("stored_conversations")
        assert not inspector.has_table("stored_conversation_items")

        command.upgrade(config, "head")
        inspector = sa.inspect(engine)
        assert inspector.has_table("stored_responses")
        assert inspector.has_table("stored_conversations")
        assert inspector.has_table("stored_conversation_items")
    finally:
        engine.dispose()
