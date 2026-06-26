from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.modules.codexneo.scheduler import CodexGoRefreshScheduler
from app.modules.codexneo.service import CodexGoAction

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


@pytest.mark.asyncio
async def test_refresh_once_skips_when_auto_refresh_disabled_or_token_missing() -> None:
    disabled_service = _Service(_Settings(codexgo_auto_refresh_enabled=False, buyer_token_saved=True))
    missing_token_service = _Service(_Settings(codexgo_auto_refresh_enabled=True, buyer_token_saved=False))

    assert await CodexGoRefreshScheduler(disabled_service).refresh_once() is False
    assert await CodexGoRefreshScheduler(missing_token_service).refresh_once() is False
    assert disabled_service.actions == []
    assert missing_token_service.actions == []


@pytest.mark.asyncio
async def test_refresh_once_runs_refresh_when_enabled_and_token_saved() -> None:
    service = _Service(_Settings(codexgo_auto_refresh_enabled=True, buyer_token_saved=True))

    assert await CodexGoRefreshScheduler(service).refresh_once() is True

    assert service.actions == [CodexGoAction.REFRESH]
