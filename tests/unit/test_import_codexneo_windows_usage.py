from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from scripts.import_codexneo_windows_usage import (
    CODEXNEO_WINDOWS_USAGE_MODEL,
    TOTAL_COST_USD,
    TOTAL_TOKENS_LIFETIME,
    TOTAL_TOKENS_TODAY,
    build_import_rows,
    load_api_routing_usage_totals,
    pricing_model_for_codexneo_windows_usage,
)


def test_build_import_rows_preserves_codexneo_windows_totals() -> None:
    rows = build_import_rows()

    today, prior = rows
    assert today.request_id == "codexneo-windows-import-today"
    assert prior.request_id == "codexneo-windows-import-prior"
    assert today.input_tokens + today.output_tokens == TOTAL_TOKENS_TODAY
    assert sum(row.input_tokens + row.output_tokens for row in rows) == TOTAL_TOKENS_LIFETIME
    assert sum(row.cost_usd for row in rows) == pytest.approx(TOTAL_COST_USD)
    assert all(0 <= row.cached_input_tokens <= row.input_tokens for row in rows)


def test_load_api_routing_usage_totals_matches_windows_reset_behavior(tmp_path) -> None:
    routing_path = tmp_path / "api-routing.json"
    routing_path.write_text(
        json.dumps(
            {
                "SchemaVersion": 1,
                "Accounts": {
                    "stale": {
                        "DayKey": "2026-06-26",
                        "InputTokensToday": 100,
                        "OutputTokensToday": 50,
                        "CachedInputTokensToday": 20,
                        "InputTokensLifetime": 1_000,
                        "OutputTokensLifetime": 100,
                        "CachedInputTokensLifetime": 300,
                    },
                    "current": {
                        "DayKey": "2026-06-27",
                        "InputTokensToday": 300,
                        "OutputTokensToday": 25,
                        "CachedInputTokensToday": 50,
                        "InputTokensLifetime": 2_000,
                        "OutputTokensLifetime": 200,
                        "CachedInputTokensLifetime": 400,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    totals = load_api_routing_usage_totals(
        routing_path,
        now=datetime(2026, 6, 27, 12, tzinfo=timezone.utc),
    )

    assert totals.input_tokens_today == 300
    assert totals.output_tokens_today == 25
    assert totals.cached_input_tokens_today == 50
    assert totals.total_tokens_today == 325
    assert totals.input_tokens_lifetime == 3_000
    assert totals.output_tokens_lifetime == 300
    assert totals.cached_input_tokens_lifetime == 700
    assert totals.total_tokens_lifetime == 3_300
    assert round(totals.total_cost_usd, 6) == 0.02085


def test_import_cost_uses_shared_current_gpt_5_5_standard_pricing() -> None:
    canonical, price = pricing_model_for_codexneo_windows_usage()

    assert canonical == CODEXNEO_WINDOWS_USAGE_MODEL
    assert price.input_per_1m == 5.0
    assert price.cached_input_per_1m == 0.5
    assert price.output_per_1m == 30.0
