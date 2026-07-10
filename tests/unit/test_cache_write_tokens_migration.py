from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.script import ScriptDirectory

from app.db.migrate import _build_alembic_config

PRIOR_HEAD = "20260710_000000_add_responses_lifecycle_resources"
EXPECTED_HEAD = "20260710_010000_add_request_log_cache_write_tokens"


def test_cache_write_tokens_migration_is_single_head_and_reversible(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'cache-write-tokens.db'}"
    config = _build_alembic_config(database_url)
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == [EXPECTED_HEAD]

    command.upgrade(config, PRIOR_HEAD)
    engine = sa.create_engine(database_url, future=True)
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO request_logs (request_id, model, status) "
                    "VALUES ('req-before-cache-write', 'gpt-5.6-sol', 'success')"
                )
            )

        command.upgrade(config, "head")
        inspector = sa.inspect(engine)
        columns = {column["name"]: column for column in inspector.get_columns("request_logs")}
        assert "cache_write_tokens" in columns
        assert columns["cache_write_tokens"]["nullable"] is True

        with engine.connect() as connection:
            historical_value = connection.scalar(
                sa.text(
                    "SELECT cache_write_tokens FROM request_logs "
                    "WHERE request_id = 'req-before-cache-write'"
                )
            )
        assert historical_value is None

        command.downgrade(config, PRIOR_HEAD)
        inspector = sa.inspect(engine)
        assert "cache_write_tokens" not in {
            column["name"] for column in inspector.get_columns("request_logs")
        }
    finally:
        engine.dispose()
