from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, or_

from app.core.usage.pricing import ModelPrice, UsageTokens, calculate_cost_from_usage, get_pricing_for_model
from app.core.utils.time import utcnow
from app.db.models import RequestKind, RequestLog
from app.db.session import SessionLocal, sqlite_writer_section

TOTAL_TOKENS_TODAY = 0
TOTAL_TOKENS_LIFETIME = 2_811_043_428
TOTAL_COST_USD = 9_380.18
OUTPUT_RATIO = 0.04
CODEXNEO_WINDOWS_USAGE_MODEL = "gpt-5.5"
MODEL = CODEXNEO_WINDOWS_USAGE_MODEL
REQUEST_ID_PREFIX = "codexneo-windows-import-"
LEGACY_REQUEST_ID_PREFIX = "codexneo-windows-estimate-"
SOURCE_MARKER = "codexneo-windows-estimate"


@dataclass(frozen=True)
class ImportedUsageRow:
    request_id: str
    requested_at_offset_days: int
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    cost_usd: float


@dataclass(frozen=True)
class CodexNeoWindowsUsageTotals:
    input_tokens_today: int
    output_tokens_today: int
    cached_input_tokens_today: int
    input_tokens_lifetime: int
    output_tokens_lifetime: int
    cached_input_tokens_lifetime: int

    @property
    def total_tokens_today(self) -> int:
        return self.input_tokens_today + self.output_tokens_today

    @property
    def total_tokens_lifetime(self) -> int:
        return self.input_tokens_lifetime + self.output_tokens_lifetime

    @property
    def total_cost_usd(self) -> float:
        return _cost_for_tokens(
            input_tokens=self.input_tokens_lifetime,
            output_tokens=self.output_tokens_lifetime,
            cached_input_tokens=self.cached_input_tokens_lifetime,
        )


def build_import_rows(totals: CodexNeoWindowsUsageTotals | None = None) -> list[ImportedUsageRow]:
    totals = totals or _default_usage_totals()
    today_input = totals.input_tokens_today
    today_output = totals.output_tokens_today
    today_cached = totals.cached_input_tokens_today
    lifetime_input = totals.input_tokens_lifetime
    lifetime_output = totals.output_tokens_lifetime
    lifetime_cached = totals.cached_input_tokens_lifetime

    prior_input = lifetime_input - today_input
    prior_output = lifetime_output - today_output
    prior_cached = lifetime_cached - today_cached
    today_cost = round(
        _cost_for_tokens(
            input_tokens=today_input,
            output_tokens=today_output,
            cached_input_tokens=today_cached,
        ),
        6,
    )
    prior_cost = round(totals.total_cost_usd - today_cost, 6)

    return [
        ImportedUsageRow(
            request_id=f"{REQUEST_ID_PREFIX}today",
            requested_at_offset_days=0,
            input_tokens=today_input,
            output_tokens=today_output,
            cached_input_tokens=today_cached,
            cost_usd=today_cost,
        ),
        ImportedUsageRow(
            request_id=f"{REQUEST_ID_PREFIX}prior",
            requested_at_offset_days=2,
            input_tokens=prior_input,
            output_tokens=prior_output,
            cached_input_tokens=prior_cached,
            cost_usd=prior_cost,
        ),
    ]


def _cached_input_for_cost(*, input_tokens: int, output_tokens: int, cost_usd: float) -> int:
    _, price = pricing_model_for_codexneo_windows_usage()
    input_millions = input_tokens / 1_000_000
    output_millions = output_tokens / 1_000_000
    input_rate = price.input_per_1m
    cached_rate = price.cached_input_per_1m if price.cached_input_per_1m is not None else input_rate
    output_rate = price.output_per_1m
    input_cache_savings = input_rate - cached_rate
    if input_cache_savings <= 0:
        return 0
    cached_millions = ((input_millions * input_rate) + (output_millions * output_rate) - cost_usd) / input_cache_savings
    return max(0, min(input_tokens, round(cached_millions * 1_000_000)))


def _cost_for_tokens(*, input_tokens: int, output_tokens: int, cached_input_tokens: int) -> float:
    safe_input = max(input_tokens, 0)
    safe_output = max(output_tokens, 0)
    safe_cached = max(0, min(cached_input_tokens, safe_input))
    _, price = pricing_model_for_codexneo_windows_usage()
    cost = calculate_cost_from_usage(
        UsageTokens(
            input_tokens=float(safe_input),
            output_tokens=float(safe_output),
            cached_input_tokens=float(safe_cached),
        ),
        price,
    )
    return float(cost or 0.0)


def pricing_model_for_codexneo_windows_usage() -> tuple[str, ModelPrice]:
    resolved = get_pricing_for_model(CODEXNEO_WINDOWS_USAGE_MODEL)
    if resolved is None:
        raise RuntimeError(f"Missing CodexNeo Windows usage pricing for {CODEXNEO_WINDOWS_USAGE_MODEL}")
    return resolved


def _default_usage_totals() -> CodexNeoWindowsUsageTotals:
    today_output = round(TOTAL_TOKENS_TODAY * OUTPUT_RATIO)
    lifetime_output = round(TOTAL_TOKENS_LIFETIME * OUTPUT_RATIO)
    lifetime_input = TOTAL_TOKENS_LIFETIME - lifetime_output
    lifetime_cached = _cached_input_for_cost(
        input_tokens=lifetime_input,
        output_tokens=lifetime_output,
        cost_usd=TOTAL_COST_USD,
    )
    today_input = TOTAL_TOKENS_TODAY - today_output
    today_cached = round(lifetime_cached * (TOTAL_TOKENS_TODAY / TOTAL_TOKENS_LIFETIME))
    return CodexNeoWindowsUsageTotals(
        input_tokens_today=today_input,
        output_tokens_today=today_output,
        cached_input_tokens_today=today_cached,
        input_tokens_lifetime=lifetime_input,
        output_tokens_lifetime=lifetime_output,
        cached_input_tokens_lifetime=lifetime_cached,
    )


def load_api_routing_usage_totals(path: Path, *, now: datetime | None = None) -> CodexNeoWindowsUsageTotals:
    current_day_key = (now or utcnow()).strftime("%Y-%m-%d")
    payload = json.loads(path.read_text(encoding="utf-8"))
    accounts = payload.get("Accounts") if isinstance(payload, dict) else None
    entries = accounts.values() if isinstance(accounts, dict) else []

    today_input = 0
    today_output = 0
    today_cached = 0
    lifetime_input = 0
    lifetime_output = 0
    lifetime_cached = 0
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            continue
        if str(raw_entry.get("DayKey") or "") == current_day_key:
            today_input += _int_value(raw_entry.get("InputTokensToday"))
            today_output += _int_value(raw_entry.get("OutputTokensToday"))
            today_cached += _int_value(raw_entry.get("CachedInputTokensToday"))
        lifetime_input += _int_value(raw_entry.get("InputTokensLifetime"))
        lifetime_output += _int_value(raw_entry.get("OutputTokensLifetime"))
        lifetime_cached += _int_value(raw_entry.get("CachedInputTokensLifetime"))

    return CodexNeoWindowsUsageTotals(
        input_tokens_today=today_input,
        output_tokens_today=today_output,
        cached_input_tokens_today=today_cached,
        input_tokens_lifetime=lifetime_input,
        output_tokens_lifetime=lifetime_output,
        cached_input_tokens_lifetime=lifetime_cached,
    )


def _int_value(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


async def import_usage(*, dry_run: bool, api_routing_json: Path | None = None) -> list[ImportedUsageRow]:
    totals = load_api_routing_usage_totals(api_routing_json) if api_routing_json else None
    rows = build_import_rows(totals)
    if dry_run:
        return rows

    now = utcnow().replace(microsecond=0)
    async with SessionLocal() as session:
        async with sqlite_writer_section():
            await session.execute(
                delete(RequestLog).where(
                    or_(
                        RequestLog.request_id.like(f"{REQUEST_ID_PREFIX}%"),
                        RequestLog.request_id.like(f"{LEGACY_REQUEST_ID_PREFIX}%"),
                        RequestLog.source == SOURCE_MARKER,
                    )
                )
            )
            for row in rows:
                session.add(
                    RequestLog(
                        account_id=None,
                        api_key_id=None,
                        request_id=row.request_id,
                        request_kind=RequestKind.NORMAL.value,
                        requested_at=now - timedelta(days=row.requested_at_offset_days),
                        model=MODEL,
                        source=SOURCE_MARKER,
                        useragent_group="codexneo",
                        transport="import",
                        input_tokens=row.input_tokens,
                        output_tokens=row.output_tokens,
                        cached_input_tokens=row.cached_input_tokens,
                        reasoning_tokens=0,
                        cost_usd=row.cost_usd,
                        latency_ms=0,
                        status="success",
                        error_code=None,
                    )
                )
            await session.commit()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Import rough CodexNeo Windows usage totals into dashboard metrics.")
    parser.add_argument("--dry-run", action="store_true", help="Print rows without writing to the database.")
    parser.add_argument(
        "--api-routing-json",
        type=Path,
        help="Read totals from the CodexNeo Windows api-routing.json file instead of the built-in rough values.",
    )
    args = parser.parse_args()
    rows = asyncio.run(import_usage(dry_run=args.dry_run, api_routing_json=args.api_routing_json))
    for row in rows:
        print(
            f"{row.request_id}: tokens={row.input_tokens + row.output_tokens}; "
            f"cached={row.cached_input_tokens}; cost=${row.cost_usd:.6f}"
        )


if __name__ == "__main__":
    main()
