from __future__ import annotations

from scripts.import_codexneo_windows_usage import (
    TOTAL_COST_USD,
    TOTAL_TOKENS_LIFETIME,
    TOTAL_TOKENS_TODAY,
    build_import_rows,
)


def test_build_import_rows_preserves_codexneo_windows_totals() -> None:
    rows = build_import_rows()

    today, prior = rows
    assert today.request_id == "codexneo-windows-import-today"
    assert prior.request_id == "codexneo-windows-import-prior"
    assert today.input_tokens + today.output_tokens == TOTAL_TOKENS_TODAY
    assert sum(row.input_tokens + row.output_tokens for row in rows) == TOTAL_TOKENS_LIFETIME
    assert sum(row.cost_usd for row in rows) == TOTAL_COST_USD
    assert all(0 <= row.cached_input_tokens <= row.input_tokens for row in rows)
