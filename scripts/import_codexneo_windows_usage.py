from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete

from app.core.utils.time import utcnow
from app.db.models import RequestKind, RequestLog
from app.db.session import SessionLocal, sqlite_writer_section

TOTAL_TOKENS_TODAY = 337_735_265
TOTAL_TOKENS_LIFETIME = 2_500_000_000
TOTAL_COST_USD = 8_342.81
OUTPUT_RATIO = 0.04
MODEL = "gpt-5.5"
REQUEST_ID_PREFIX = "codexneo-windows-import-"


@dataclass(frozen=True)
class ImportedUsageRow:
    request_id: str
    requested_at_offset_days: int
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    cost_usd: float


def build_import_rows() -> list[ImportedUsageRow]:
    today_output = round(TOTAL_TOKENS_TODAY * OUTPUT_RATIO)
    today_input = TOTAL_TOKENS_TODAY - today_output
    lifetime_output = round(TOTAL_TOKENS_LIFETIME * OUTPUT_RATIO)
    lifetime_input = TOTAL_TOKENS_LIFETIME - lifetime_output
    lifetime_cached = _cached_input_for_cost(
        input_tokens=lifetime_input,
        output_tokens=lifetime_output,
        cost_usd=TOTAL_COST_USD,
    )
    today_cached = round(lifetime_cached * (TOTAL_TOKENS_TODAY / TOTAL_TOKENS_LIFETIME))

    prior_input = lifetime_input - today_input
    prior_output = lifetime_output - today_output
    prior_cached = lifetime_cached - today_cached
    today_cost = round(TOTAL_COST_USD * (TOTAL_TOKENS_TODAY / TOTAL_TOKENS_LIFETIME), 6)
    prior_cost = round(TOTAL_COST_USD - today_cost, 6)

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
    input_millions = input_tokens / 1_000_000
    output_millions = output_tokens / 1_000_000
    # CodexNeo Windows reference pricing: gpt-5.5 input $5/M, cached input
    # $0.50/M, output $30/M. Solve for cached input using only the imported
    # lifetime token and cost totals.
    cached_millions = ((input_millions * 5.0) + (output_millions * 30.0) - cost_usd) / 4.5
    return max(0, min(input_tokens, round(cached_millions * 1_000_000)))


async def import_usage(*, dry_run: bool) -> list[ImportedUsageRow]:
    rows = build_import_rows()
    if dry_run:
        return rows

    now = utcnow().replace(microsecond=0)
    async with SessionLocal() as session:
        async with sqlite_writer_section():
            await session.execute(
                delete(RequestLog).where(RequestLog.request_id.like(f"{REQUEST_ID_PREFIX}%"))
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
                        source="codexneo_windows_import",
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
    args = parser.parse_args()
    rows = asyncio.run(import_usage(dry_run=args.dry_run))
    for row in rows:
        print(
            f"{row.request_id}: tokens={row.input_tokens + row.output_tokens}; "
            f"cached={row.cached_input_tokens}; cost=${row.cost_usd:.6f}"
        )


if __name__ == "__main__":
    main()
