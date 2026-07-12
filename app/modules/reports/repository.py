from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from itertools import batched
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account, RequestLog, RequestLogAggregate

_INTERNAL_LIMIT_WARMUP_SOURCE = "limit_warmup"
_INTERNAL_WARMUP_REQUEST_KINDS = ("warmup", "limit_warmup")
_SQLITE_COMPOUND_SELECT_LIMIT = 500
MAX_DAILY_REPORT_DAYS = 730


class DailyReportRangeTooLargeError(ValueError):
    pass


@dataclass(frozen=True)
class DailyReportAggregateRow:
    date: str
    requests: int
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    cost_usd: float
    active_accounts: int
    error_count: int


@dataclass(frozen=True)
class SummaryAggregateRow:
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    total_cached_tokens: int
    total_requests: int
    total_errors: int
    active_accounts: int


@dataclass(frozen=True)
class ModelAggregateRow:
    model: str
    cost_usd: float


@dataclass(frozen=True)
class AccountAggregateRow:
    account_id: str | None
    alias: str | None
    cost_usd: float
    request_count: int


class ReportsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def aggregate_daily_rows(
        self,
        start_date: date,
        end_date: date,
        timezone_info: ZoneInfo | timezone,
        account_ids: list[str] | None = None,
        model: str | None = None,
    ) -> list[DailyReportAggregateRow]:
        window_days = (end_date - start_date).days + 1
        if window_days > MAX_DAILY_REPORT_DAYS:
            raise DailyReportRangeTooLargeError(f"report date range must be {MAX_DAILY_REPORT_DAYS} days or less")
        day_ranges = list(_daily_bucket_ranges(start_date, end_date, timezone_info))
        if not day_ranges:
            return []

        rows: list[DailyReportAggregateRow] = []
        # SQLite caps compound SELECTs at 500 terms, so long report ranges are
        # executed in chunks instead of building a single oversized UNION ALL.
        for day_ranges_batch in batched(day_ranges, _SQLITE_COMPOUND_SELECT_LIMIT):
            stmt = _daily_rows_stmt(list(day_ranges_batch), account_ids, model)
            result = await self._session.execute(stmt)
            rows.extend(
                DailyReportAggregateRow(
                    date=row.report_date,
                    requests=int(row.requests or 0),
                    input_tokens=int(row.input_tokens or 0),
                    output_tokens=int(row.output_tokens or 0),
                    cached_input_tokens=int(row.cached_input_tokens or 0),
                    cost_usd=float(row.cost_usd or 0.0),
                    active_accounts=int(row.active_accounts or 0),
                    error_count=int(row.error_count or 0),
                )
                for row in result.all()
            )
        archived_stmt = (
            select(
                func.date(RequestLogAggregate.bucket_start).label("report_date"),
                func.sum(RequestLogAggregate.request_count).label("requests"),
                func.sum(RequestLogAggregate.input_tokens).label("input_tokens"),
                func.sum(RequestLogAggregate.output_tokens).label("output_tokens"),
                func.sum(RequestLogAggregate.cached_input_tokens).label("cached_input_tokens"),
                func.sum(RequestLogAggregate.cost_usd).label("cost_usd"),
                func.count(func.distinct(RequestLogAggregate.account_id)).label("active_accounts"),
                func.sum(RequestLogAggregate.error_count).label("error_count"),
            )
            .where(
                RequestLogAggregate.bucket_start >= day_ranges[0][1],
                RequestLogAggregate.bucket_start < day_ranges[-1][2],
                *(_aggregate_filters(account_ids, model)),
            )
            .group_by(func.date(RequestLogAggregate.bucket_start))
        )
        archived = await self._session.execute(archived_stmt)
        merged = {row.date: row for row in rows}
        day_range_by_date = {report_date: (day_start, day_end) for report_date, day_start, day_end in day_ranges}
        for row in archived.all():
            key = str(row.report_date)
            previous = merged.get(key)
            day_start, day_end = day_range_by_date[key]
            active_account_ids = (
                select(RequestLog.account_id.label("account_id"))
                .where(
                    *_report_conditions(day_start, day_end, account_ids, model),
                    RequestLog.account_id.is_not(None),
                )
                .union(
                    select(RequestLogAggregate.account_id.label("account_id")).where(
                        RequestLogAggregate.bucket_start >= day_start,
                        RequestLogAggregate.bucket_start < day_end,
                        RequestLogAggregate.account_id.is_not(None),
                        *(_aggregate_filters(account_ids, model)),
                    )
                )
                .subquery()
            )
            active_accounts = await self._session.scalar(select(func.count()).select_from(active_account_ids))
            addition = DailyReportAggregateRow(
                key,
                int(row.requests or 0),
                int(row.input_tokens or 0),
                int(row.output_tokens or 0),
                int(row.cached_input_tokens or 0),
                float(row.cost_usd or 0.0),
                int(active_accounts or 0),
                int(row.error_count or 0),
            )
            merged[key] = (
                addition
                if previous is None
                else DailyReportAggregateRow(
                    key,
                    previous.requests + addition.requests,
                    previous.input_tokens + addition.input_tokens,
                    previous.output_tokens + addition.output_tokens,
                    previous.cached_input_tokens + addition.cached_input_tokens,
                    previous.cost_usd + addition.cost_usd,
                    addition.active_accounts,
                    previous.error_count + addition.error_count,
                )
            )
        return [merged[key] for key in sorted(merged)]

    async def aggregate_summary(
        self,
        start_date: datetime,
        end_date: datetime,
        account_ids: list[str] | None = None,
        model: str | None = None,
    ) -> SummaryAggregateRow:
        conditions = _report_conditions(start_date, end_date, account_ids, model)

        result = await self._session.execute(
            select(
                func.coalesce(func.sum(RequestLog.cost_usd), 0.0).label("total_cost_usd"),
                func.coalesce(func.sum(RequestLog.input_tokens), 0).label("total_input_tokens"),
                func.coalesce(func.sum(RequestLog.output_tokens), 0).label("total_output_tokens"),
                func.coalesce(func.sum(RequestLog.cached_input_tokens), 0).label("total_cached_tokens"),
                func.count().label("total_requests"),
                func.coalesce(
                    func.sum(case((RequestLog.status != "success", 1), else_=0)),
                    0,
                ).label("total_errors"),
                func.count(func.distinct(RequestLog.account_id)).label("active_accounts"),
            ).where(and_(*conditions))
        )
        row = result.one()
        archived = await self._session.execute(
            select(
                func.coalesce(func.sum(RequestLogAggregate.cost_usd), 0.0).label("cost"),
                func.coalesce(func.sum(RequestLogAggregate.input_tokens), 0).label("input"),
                func.coalesce(func.sum(RequestLogAggregate.output_tokens), 0).label("output"),
                func.coalesce(func.sum(RequestLogAggregate.cached_input_tokens), 0).label("cached"),
                func.coalesce(func.sum(RequestLogAggregate.request_count), 0).label("requests"),
                func.coalesce(func.sum(RequestLogAggregate.error_count), 0).label("errors"),
            ).where(
                RequestLogAggregate.bucket_start >= start_date,
                RequestLogAggregate.bucket_start < end_date,
                *(_aggregate_filters(account_ids, model)),
            )
        )
        archived_row = archived.one()
        active_account_ids = (
            select(RequestLog.account_id.label("account_id"))
            .where(
                and_(*conditions),
                RequestLog.account_id.is_not(None),
            )
            .union(
                select(RequestLogAggregate.account_id.label("account_id")).where(
                    RequestLogAggregate.bucket_start >= start_date,
                    RequestLogAggregate.bucket_start < end_date,
                    RequestLogAggregate.account_id.is_not(None),
                    *(_aggregate_filters(account_ids, model)),
                )
            )
            .subquery()
        )
        active_accounts = await self._session.scalar(select(func.count()).select_from(active_account_ids))
        return SummaryAggregateRow(
            total_cost_usd=float(row.total_cost_usd) + float(archived_row.cost or 0.0),
            total_input_tokens=int(row.total_input_tokens) + int(archived_row.input or 0),
            total_output_tokens=int(row.total_output_tokens) + int(archived_row.output or 0),
            total_cached_tokens=int(row.total_cached_tokens) + int(archived_row.cached or 0),
            total_requests=int(row.total_requests) + int(archived_row.requests or 0),
            total_errors=int(row.total_errors) + int(archived_row.errors or 0),
            active_accounts=int(active_accounts or 0),
        )

    async def aggregate_by_model(
        self,
        start_date: datetime,
        end_date: datetime,
        account_ids: list[str] | None = None,
        model: str | None = None,
    ) -> list[ModelAggregateRow]:
        conditions = [
            *_report_conditions(start_date, end_date, account_ids, model),
            RequestLog.model.is_not(None),
        ]

        stmt = (
            select(
                RequestLog.model,
                func.coalesce(func.sum(RequestLog.cost_usd), 0.0).label("cost_usd"),
            )
            .where(and_(*conditions))
            .group_by(RequestLog.model)
            .order_by(func.coalesce(func.sum(RequestLog.cost_usd), 0.0).desc())
        )
        result = await self._session.execute(stmt)
        merged = {row.model: float(row.cost_usd or 0.0) for row in result.all()}
        archived = await self._session.execute(
            select(
                RequestLogAggregate.model, func.coalesce(func.sum(RequestLogAggregate.cost_usd), 0.0).label("cost_usd")
            )
            .where(
                RequestLogAggregate.bucket_start >= start_date,
                RequestLogAggregate.bucket_start < end_date,
                *(_aggregate_filters(account_ids, model)),
            )
            .group_by(RequestLogAggregate.model)
        )
        for row in archived.all():
            merged[row.model] = merged.get(row.model, 0.0) + float(row.cost_usd or 0.0)
        return [
            ModelAggregateRow(
                model=key,
                cost_usd=value,
            )
            for key, value in sorted(merged.items(), key=lambda item: item[1], reverse=True)
        ]

    async def aggregate_by_account(
        self,
        start_date: datetime,
        end_date: datetime,
        account_ids: list[str] | None = None,
        model: str | None = None,
    ) -> list[AccountAggregateRow]:
        conditions = _report_conditions(start_date, end_date, account_ids, model)

        stmt = (
            select(
                RequestLog.account_id,
                func.coalesce(func.sum(RequestLog.cost_usd), 0.0).label("cost_usd"),
                func.count().label("request_count"),
            )
            .where(and_(*conditions))
            .group_by(RequestLog.account_id)
            .order_by(func.coalesce(func.sum(RequestLog.cost_usd), 0.0).desc())
        )
        result = await self._session.execute(stmt)
        totals = {row.account_id: [float(row.cost_usd or 0.0), int(row.request_count or 0)] for row in result.all()}
        archived = await self._session.execute(
            select(
                RequestLogAggregate.account_id,
                func.coalesce(func.sum(RequestLogAggregate.cost_usd), 0.0).label("cost_usd"),
                func.coalesce(func.sum(RequestLogAggregate.request_count), 0).label("request_count"),
            )
            .where(
                RequestLogAggregate.bucket_start >= start_date,
                RequestLogAggregate.bucket_start < end_date,
                *(_aggregate_filters(account_ids, model)),
            )
            .group_by(RequestLogAggregate.account_id)
        )
        for row in archived.all():
            total = totals.setdefault(row.account_id, [0.0, 0])
            total[0] += float(row.cost_usd or 0.0)
            total[1] += int(row.request_count or 0)
        rows = [(account_id, totals[account_id][0], totals[account_id][1]) for account_id in totals]

        account_ids_found = [row[0] for row in rows if row[0]]
        alias_map: dict[str | None, str | None] = {}
        if account_ids_found:
            alias_result = await self._session.execute(
                select(Account.id, Account.alias).where(Account.id.in_(account_ids_found))
            )
            alias_map = {account_id: alias for account_id, alias in alias_result.all()}

        return [
            AccountAggregateRow(
                account_id=row[0],
                alias=alias_map.get(row[0]),
                cost_usd=float(row[1]),
                request_count=int(row[2]),
            )
            for row in rows
        ]

    async def count_active_accounts(
        self,
        start_date: datetime,
        end_date: datetime,
        account_ids: list[str] | None = None,
        model: str | None = None,
    ) -> int:
        conditions = [
            *_report_conditions(start_date, end_date, account_ids, model),
            RequestLog.account_id.is_not(None),
        ]

        result = await self._session.execute(
            select(func.count(func.distinct(RequestLog.account_id))).where(and_(*conditions))
        )
        return int(result.scalar_one() or 0)

    async def earliest_report_activity_at(
        self,
        account_ids: list[str] | None = None,
        model: str | None = None,
    ) -> datetime | None:
        conditions = [_normal_traffic_clause()]
        if account_ids:
            conditions.append(RequestLog.account_id.in_(account_ids))
        if model:
            conditions.append(RequestLog.model == model)

        result = await self._session.execute(select(func.min(RequestLog.requested_at)).where(and_(*conditions)))
        value = result.scalar_one_or_none()
        return value if isinstance(value, datetime) else None


def _report_conditions(
    start_date: datetime,
    end_date: datetime,
    account_ids: list[str] | None,
    model: str | None,
) -> list:
    conditions = [
        RequestLog.requested_at >= start_date,
        RequestLog.requested_at < end_date,
        _normal_traffic_clause(),
    ]
    if account_ids:
        conditions.append(RequestLog.account_id.in_(account_ids))
    if model:
        conditions.append(RequestLog.model == model)
    return conditions


def _aggregate_filters(account_ids: list[str] | None, model: str | None) -> list:
    conditions: list = []
    if account_ids:
        conditions.append(RequestLogAggregate.account_id.in_(account_ids))
    if model:
        conditions.append(RequestLogAggregate.model == model)
    return conditions


def _normal_traffic_clause():
    return and_(
        or_(RequestLog.source.is_(None), RequestLog.source != _INTERNAL_LIMIT_WARMUP_SOURCE),
        or_(
            RequestLog.request_kind.is_(None),
            RequestLog.request_kind.not_in(_INTERNAL_WARMUP_REQUEST_KINDS),
        ),
    )


def _daily_rows_stmt(
    day_ranges: list[tuple[str, datetime, datetime]],
    account_ids: list[str] | None,
    model: str | None,
):
    day_range_rows = [
        select(
            literal(report_date).label("report_date"),
            literal(day_start).label("day_start"),
            literal(day_end).label("day_end"),
        )
        for report_date, day_start, day_end in day_ranges
    ]
    day_ranges_query = day_range_rows[0] if len(day_range_rows) == 1 else union_all(*day_range_rows)
    day_ranges_cte = day_ranges_query.cte("report_days")
    return (
        select(
            day_ranges_cte.c.report_date,
            func.count(RequestLog.id).label("requests"),
            func.coalesce(func.sum(RequestLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(RequestLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(RequestLog.cached_input_tokens), 0).label("cached_input_tokens"),
            func.coalesce(func.sum(RequestLog.cost_usd), 0.0).label("cost_usd"),
            func.count(func.distinct(RequestLog.account_id)).label("active_accounts"),
            func.coalesce(
                func.sum(case((RequestLog.status != "success", 1), else_=0)),
                0,
            ).label("error_count"),
        )
        .select_from(
            day_ranges_cte.join(
                RequestLog,
                and_(
                    RequestLog.requested_at >= day_ranges_cte.c.day_start,
                    RequestLog.requested_at < day_ranges_cte.c.day_end,
                    _normal_traffic_clause(),
                    *([RequestLog.account_id.in_(account_ids)] if account_ids else []),
                    *([RequestLog.model == model] if model else []),
                ),
            )
        )
        .group_by(day_ranges_cte.c.report_date)
        .order_by(day_ranges_cte.c.report_date)
    )


def _daily_bucket_ranges(
    start_date: date,
    end_date: date,
    timezone_info: ZoneInfo | timezone,
) -> list[tuple[str, datetime, datetime]]:
    ranges: list[tuple[str, datetime, datetime]] = []
    current_date = start_date
    while current_date <= end_date:
        day_start = datetime.combine(current_date, datetime.min.time(), tzinfo=timezone_info)
        next_day_start = datetime.combine(current_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone_info)
        ranges.append(
            (
                current_date.isoformat(),
                day_start.astimezone(timezone.utc).replace(tzinfo=None),
                next_day_start.astimezone(timezone.utc).replace(tzinfo=None),
            )
        )
        current_date += timedelta(days=1)
    return ranges
