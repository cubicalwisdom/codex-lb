from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

from app.modules.codexneo.service import CodexGoAction, CodexNeoService

logger = logging.getLogger(__name__)


class _CodexNeoRefreshService(Protocol):
    async def get_settings(self): ...

    async def apply_codexgo_auth(self, action: CodexGoAction): ...


class CodexGoRefreshScheduler:
    def __init__(
        self,
        service: _CodexNeoRefreshService | None = None,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._service = service or CodexNeoService()
        self._sleep = sleep
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def refresh_once(self) -> bool:
        settings = await self._service.get_settings()
        if not settings.codexgo_auto_refresh_enabled or not settings.buyer_token_saved:
            return False
        await self._service.apply_codexgo_auth(CodexGoAction.REFRESH)
        return True

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            interval_seconds = 300.0
            try:
                settings = await self._service.get_settings()
                interval_seconds = max(300.0, float(settings.codexgo_auto_refresh_interval_minutes) * 60.0)
                await self.refresh_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("CodexGO auto-refresh pass failed")
            try:
                await self._sleep(interval_seconds)
            except asyncio.CancelledError:
                raise


def build_codexgo_refresh_scheduler() -> CodexGoRefreshScheduler:
    return CodexGoRefreshScheduler()
