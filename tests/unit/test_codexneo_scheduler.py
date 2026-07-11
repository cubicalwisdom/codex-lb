from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.modules.codexneo.scheduler import CodexGoRefreshScheduler, build_codexgo_refresh_scheduler
from app.modules.codexneo.service import CodexGoAction, CodexNeoService
from app.modules.codexneo.sync import CodexNeoAccountsSyncService

pytestmark = pytest.mark.unit


@dataclass
class _Settings:
    codexgo_auto_refresh_enabled: bool
    buyer_token_saved: bool
    codexgo_auto_refresh_interval_minutes: int = 30


class _Service:
    def __init__(self, settings: _Settings) -> None:
        self.settings = settings
        self.actions: list[CodexGoAction] = []

    async def get_settings(self) -> _Settings:
        return self.settings

    async def apply_codexgo_auth(self, action: CodexGoAction):
        self.actions.append(action)


class _FailingService(_Service):
    async def apply_codexgo_auth(self, action: CodexGoAction):
        await super().apply_codexgo_auth(action)
        raise RuntimeError("provider unavailable; buyer_token=secret")


class _ActivityLog:
    def __init__(self) -> None:
        self.entries: list[tuple[str, str]] = []

    def append(self, stream: str, message: str) -> None:
        self.entries.append((stream, message))


def test_background_scheduler_wires_account_sync_for_codexgo_reconciliation() -> None:
    scheduler = build_codexgo_refresh_scheduler()

    assert isinstance(scheduler._service, CodexNeoService)
    assert isinstance(scheduler._service._account_sync, CodexNeoAccountsSyncService)


@pytest.mark.asyncio
async def test_refresh_once_skips_when_auto_refresh_disabled_or_token_missing() -> None:
    disabled_service = _Service(_Settings(codexgo_auto_refresh_enabled=False, buyer_token_saved=True))
    missing_token_service = _Service(_Settings(codexgo_auto_refresh_enabled=True, buyer_token_saved=False))
    disabled_log = _ActivityLog()
    missing_token_log = _ActivityLog()

    assert (
        await CodexGoRefreshScheduler(disabled_service, activity_log_service=disabled_log).refresh_once()
        is False
    )
    assert (
        await CodexGoRefreshScheduler(missing_token_service, activity_log_service=missing_token_log).refresh_once()
        is False
    )
    assert disabled_service.actions == []
    assert missing_token_service.actions == []
    assert disabled_log.entries == [
        ("management", "Management task CodexGO auto-refresh -> skipped; reason=disabled.")
    ]
    assert missing_token_log.entries == [
        ("management", "Management task CodexGO auto-refresh -> skipped; reason=buyer_token_missing.")
    ]


@pytest.mark.asyncio
async def test_refresh_once_runs_refresh_when_enabled_and_token_saved() -> None:
    service = _Service(_Settings(codexgo_auto_refresh_enabled=True, buyer_token_saved=True))
    activity_log = _ActivityLog()

    assert await CodexGoRefreshScheduler(service, activity_log_service=activity_log).refresh_once() is True

    assert service.actions == [CodexGoAction.REFRESH]
    assert activity_log.entries[0] == ("management", "Management task CodexGO auto-refresh -> started.")
    assert activity_log.entries[1][0] == "management"
    assert activity_log.entries[1][1].startswith("Management task CodexGO auto-refresh -> applied; ")


@pytest.mark.asyncio
async def test_refresh_once_logs_failure_without_secret_details() -> None:
    service = _FailingService(_Settings(codexgo_auto_refresh_enabled=True, buyer_token_saved=True))
    activity_log = _ActivityLog()

    with pytest.raises(RuntimeError):
        await CodexGoRefreshScheduler(service, activity_log_service=activity_log).refresh_once()

    assert service.actions == [CodexGoAction.REFRESH]
    assert activity_log.entries[0] == ("management", "Management task CodexGO auto-refresh -> started.")
    assert activity_log.entries[1][0] == "management"
    assert activity_log.entries[1][1].startswith(
        "Management task CodexGO auto-refresh -> failed; error=RuntimeError; "
    )
    assert "secret" not in activity_log.entries[1][1]
