from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol

from app.core.auth import parse_auth_json
from app.modules.codexneo.activity_log import CodexNeoActivityLogService
from app.modules.codexneo.sync import CodexNeoSyncResult


class _CodexNeoSyncService(Protocol):
    async def sync_codex_home_to_accounts(self) -> CodexNeoSyncResult: ...


class CodexNeoRootReconciler:
    """Durably ingest changed root auth independently from the browser page."""

    def __init__(
        self,
        *,
        codex_home: Path,
        sync_service: _CodexNeoSyncService,
        interval_seconds: float = 30.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        activity_pruner: Callable[[], None] | None = None,
    ) -> None:
        self._root_auth = codex_home / "auth.json"
        self._sync_service = sync_service
        self._interval_seconds = max(5.0, interval_seconds)
        self._sleep = sleep
        self._activity_pruner = activity_pruner
        self._fingerprint: str | None = None
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run())

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

    async def reconcile_once(self) -> bool:
        try:
            raw = self._root_auth.read_bytes()
            parse_auth_json(raw)
        except (FileNotFoundError, OSError, ValueError):
            return False
        fingerprint = hashlib.sha256(raw).hexdigest()
        if fingerprint == self._fingerprint:
            return False
        result = await self._sync_service.sync_codex_home_to_accounts()
        if not result.success:
            return False
        self._fingerprint = fingerprint
        return True

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if self._activity_pruner is not None:
                    self._activity_pruner()
                await self.reconcile_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                # Reconciliation is retried on the next bounded pass.
                pass
            try:
                await self._sleep(self._interval_seconds)
            except asyncio.CancelledError:
                raise


def build_codexneo_root_reconciler() -> CodexNeoRootReconciler:
    from app.modules.codexneo.home import resolve_configured_codex_home
    from app.modules.codexneo.sync import CodexNeoAccountsSyncService

    codex_home = resolve_configured_codex_home()
    return CodexNeoRootReconciler(
        codex_home=codex_home,
        sync_service=CodexNeoAccountsSyncService(codex_home=codex_home),
        activity_pruner=CodexNeoActivityLogService(respect_settings=False).prune,
    )
