from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import delete, select

from app.core.config.settings import get_settings
from app.core.utils.time import utcnow
from app.db.models import AdditionalUsageHistory, RequestKind, RequestLog, RequestLogAggregate, UsageHistory
from app.db.session import get_background_session, sqlite_writer_section

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HistoryRetentionScheduler:
    interval_seconds: int
    retention_days: int
    enabled: bool
    _task: asyncio.Task[None] | None = None
    _stop: asyncio.Event = field(default_factory=asyncio.Event)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def start(self) -> None:
        if self.enabled and (self._task is None or self._task.done()):
            self._stop.clear()
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            await self._prune_once()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)

    async def _prune_once(self) -> None:
        cutoff = utcnow() - timedelta(days=self.retention_days)
        async with self._lock:
            try:
                async with get_background_session() as session:
                    logs = list(
                        (
                            await session.execute(
                                select(RequestLog).where(
                                    RequestLog.requested_at < cutoff,
                                    RequestLog.request_kind.not_in((RequestKind.WARMUP.value, "limit_warmup")),
                                )
                            )
                        ).scalars()
                    )
                    rollups: dict[tuple, RequestLogAggregate] = {}
                    for log in logs:
                        bucket_start = log.requested_at.replace(second=0, microsecond=0)
                        key = (
                            bucket_start,
                            log.account_id,
                            log.api_key_id,
                            log.model,
                            log.service_tier,
                            log.error_code,
                        )
                        row = rollups.setdefault(
                            key,
                            RequestLogAggregate(
                                bucket_start=key[0],
                                account_id=key[1],
                                api_key_id=key[2],
                                model=key[3],
                                service_tier=key[4],
                                error_code=key[5],
                                request_count=0,
                                input_tokens=0,
                                output_tokens=0,
                                cached_input_tokens=0,
                                cost_usd=0.0,
                                error_count=0,
                            ),
                        )
                        row.request_count += 1
                        row.input_tokens += log.input_tokens or 0
                        row.output_tokens += log.output_tokens or log.reasoning_tokens or 0
                        row.cached_input_tokens += log.cached_input_tokens or 0
                        row.cost_usd += log.cost_usd or 0.0
                        row.error_count += int(log.status != "success")
                    async with sqlite_writer_section():
                        session.add_all(rollups.values())
                        await session.execute(delete(RequestLog).where(RequestLog.requested_at < cutoff))
                        await session.execute(delete(UsageHistory).where(UsageHistory.recorded_at < cutoff))
                        await session.execute(
                            delete(AdditionalUsageHistory).where(AdditionalUsageHistory.recorded_at < cutoff)
                        )
                        await session.commit()
                    logger.info(
                        "History retention pruned raw detail cutoff=%s request_rollups=%s",
                        cutoff.isoformat(),
                        len(rollups),
                    )
            except Exception:
                logger.exception("History retention loop failed")


def build_history_retention_scheduler() -> HistoryRetentionScheduler:
    settings = get_settings()
    return HistoryRetentionScheduler(
        settings.history_retention_interval_seconds, settings.history_retention_days, settings.history_retention_enabled
    )
