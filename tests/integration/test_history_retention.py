from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from alembic import command
from sqlalchemy import create_engine, func, inspect, select

from app.db.migrate import _build_alembic_config, run_upgrade
from app.db.models import (
    Account,
    AccountStatus,
    AdditionalUsageHistory,
    RequestLog,
    RequestLogAggregate,
    UsageHistory,
)
from app.db.session import SessionLocal
from app.modules.api_keys.repository import ApiKeysRepository
from app.modules.history_retention.scheduler import HistoryRetentionScheduler
from app.modules.reports.repository import ReportsRepository
from app.modules.request_logs.repository import RequestLogsRepository

pytestmark = pytest.mark.integration

_RETENTION_PARENT_REVISION = "20260710_010000_add_request_log_cache_write_tokens"


@pytest.mark.asyncio
async def test_retention_prunes_only_expired_detail_and_preserves_all_aggregate_consumers(
    db_setup,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del db_setup
    now = datetime(2026, 7, 13, 12, 0, 0)
    expired_at = now - timedelta(hours=25)
    current_at = now - timedelta(hours=23)
    monkeypatch.setattr("app.modules.history_retention.scheduler.utcnow", lambda: now)

    async with SessionLocal() as session:
        session.add_all(
            [
                Account(
                    id="expired-account",
                    email="expired@example.com",
                    plan_type="pro",
                    access_token_encrypted=b"access",
                    refresh_token_encrypted=b"refresh",
                    id_token_encrypted=b"id",
                    last_refresh=expired_at,
                    status=AccountStatus.ACTIVE,
                ),
                Account(
                    id="current-account",
                    email="current@example.com",
                    plan_type="pro",
                    access_token_encrypted=b"access",
                    refresh_token_encrypted=b"refresh",
                    id_token_encrypted=b"id",
                    last_refresh=current_at,
                    status=AccountStatus.ACTIVE,
                ),
                RequestLog(
                    account_id="expired-account",
                    api_key_id="key-retained",
                    request_id="expired-request",
                    requested_at=expired_at,
                    model="gpt-5.6",
                    status="error",
                    error_code="retained_error",
                    input_tokens=100,
                    output_tokens=None,
                    reasoning_tokens=25,
                    cached_input_tokens=40,
                    cost_usd=0.5,
                ),
                RequestLog(
                    account_id="current-account",
                    api_key_id="key-retained",
                    request_id="current-request",
                    requested_at=current_at,
                    model="gpt-5.6",
                    status="success",
                    input_tokens=10,
                    output_tokens=5,
                    cached_input_tokens=2,
                    cost_usd=0.05,
                ),
                UsageHistory(recorded_at=expired_at, window="primary", used_percent=70.0),
                UsageHistory(recorded_at=current_at, window="primary", used_percent=80.0),
                AdditionalUsageHistory(
                    recorded_at=expired_at,
                    quota_key="old",
                    limit_name="Old",
                    metered_feature="old",
                    window="primary",
                    used_percent=20.0,
                ),
                AdditionalUsageHistory(
                    recorded_at=current_at,
                    quota_key="current",
                    limit_name="Current",
                    metered_feature="current",
                    window="primary",
                    used_percent=30.0,
                ),
            ]
        )
        await session.commit()

    scheduler = HistoryRetentionScheduler(interval_seconds=60, retention_days=1, enabled=True)
    await scheduler._prune_once()

    async with SessionLocal() as session:
        assert await session.scalar(select(func.count()).select_from(RequestLog)) == 1
        assert await session.scalar(select(func.count()).select_from(UsageHistory)) == 1
        assert await session.scalar(select(func.count()).select_from(AdditionalUsageHistory)) == 1

        aggregate = (await session.execute(select(RequestLogAggregate))).scalar_one()
        assert aggregate.request_count == 1
        assert aggregate.input_tokens == 100
        assert aggregate.output_tokens == 25
        assert aggregate.cached_input_tokens == 40
        assert aggregate.cost_usd == pytest.approx(0.5)

        api_key_summary = await ApiKeysRepository(session).get_usage_summary_by_key_id("key-retained")
        assert api_key_summary.request_count == 2
        assert api_key_summary.total_tokens == 140
        assert api_key_summary.cached_input_tokens == 42
        assert api_key_summary.total_cost_usd == pytest.approx(0.55)

        all_api_key_summaries = await ApiKeysRepository(session).list_usage_summary_by_key()
        assert all_api_key_summaries["key-retained"] == api_key_summary

        api_key_trends = await ApiKeysRepository(session).trends_by_key(
            "key-retained",
            expired_at - timedelta(hours=1),
            now,
        )
        assert sum(bucket.total_tokens for bucket in api_key_trends) == 140
        assert sum(bucket.total_cost_usd for bucket in api_key_trends) == pytest.approx(0.55)

        api_key_usage = await ApiKeysRepository(session).usage_7d(
            "key-retained",
            expired_at - timedelta(hours=1),
            now,
        )
        assert api_key_usage.total_requests == 2
        assert api_key_usage.total_tokens == 140
        assert api_key_usage.cached_input_tokens == 42
        assert api_key_usage.total_cost_usd == pytest.approx(0.55)

        account_costs = await ApiKeysRepository(session).usage_7d_by_account(
            "key-retained",
            expired_at - timedelta(hours=1),
            now,
        )
        assert sum(account.cost_usd for account in account_costs) == pytest.approx(0.55)
        assert {account.account_id for account in account_costs} == {
            "expired-account",
            "current-account",
        }

        report = await ReportsRepository(session).aggregate_summary(
            expired_at - timedelta(hours=1),
            now,
        )
        assert report.total_requests == 2
        assert report.total_input_tokens == 110
        assert report.total_output_tokens == 30
        assert report.total_cached_tokens == 42
        assert report.total_cost_usd == pytest.approx(0.55)
        assert report.total_errors == 1
        assert report.active_accounts == 2

        request_logs = RequestLogsRepository(session)
        assert await request_logs.top_error_between(expired_at - timedelta(hours=1), now) == "retained_error"
        assert await request_logs.earliest_activity_at() == aggregate.bucket_start

        daily = await ReportsRepository(session).aggregate_daily_rows(
            expired_at.date(),
            current_at.date(),
            timezone.utc,
        )
        assert sum(row.active_accounts for row in daily) == 2


def test_retention_migration_upgrades_and_downgrades_cleanly(tmp_path) -> None:
    db_path = tmp_path / "retention-migration.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    run_upgrade(url, _RETENTION_PARENT_REVISION, bootstrap_legacy=False)

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        assert "request_log_aggregates" not in inspect(engine).get_table_names()

        run_upgrade(url, "head", bootstrap_legacy=False)
        inspector = inspect(engine)
        assert "request_log_aggregates" in inspector.get_table_names()
        assert {column["name"] for column in inspector.get_columns("request_log_aggregates")} == {
            "id",
            "bucket_start",
            "account_id",
            "api_key_id",
            "model",
            "service_tier",
            "error_code",
            "request_count",
            "input_tokens",
            "output_tokens",
            "cached_input_tokens",
            "cost_usd",
            "error_count",
        }
        assert {index["name"] for index in inspector.get_indexes("request_log_aggregates")} == {
            "idx_request_log_aggregates_bucket"
        }

        command.downgrade(_build_alembic_config(url), _RETENTION_PARENT_REVISION)
        assert "request_log_aggregates" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()
