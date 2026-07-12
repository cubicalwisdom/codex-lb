from __future__ import annotations

import asyncio
import base64
import json

import pytest

from app.modules.codexneo.reconciler import CodexNeoRootReconciler
from app.modules.codexneo.sync import CodexNeoSyncResult

pytestmark = pytest.mark.unit


def _auth_json(account_id: str) -> bytes:
    claims = base64.urlsafe_b64encode(
        json.dumps({"email": f"{account_id}@example.com"}).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    return json.dumps(
        {
            "tokens": {
                "idToken": f"header.{claims}.sig",
                "accessToken": f"access-{account_id}",
                "refreshToken": f"refresh-{account_id}",
                "accountId": account_id,
            }
        }
    ).encode("utf-8")


class RecordingSync:
    def __init__(self) -> None:
        self.calls = 0

    async def sync_codex_home_to_accounts(self) -> CodexNeoSyncResult:
        self.calls += 1
        return CodexNeoSyncResult(success=True, message="synced", count=1)


@pytest.mark.asyncio
async def test_reconciler_ingests_each_new_valid_root_auth_once(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    root_auth = codex_home / "auth.json"
    sync = RecordingSync()
    reconciler = CodexNeoRootReconciler(codex_home=codex_home, sync_service=sync)

    root_auth.write_bytes(_auth_json("first"))
    assert await reconciler.reconcile_once() is True
    assert await reconciler.reconcile_once() is False

    root_auth.write_bytes(_auth_json("second"))
    assert await reconciler.reconcile_once() is True
    assert sync.calls == 2


@pytest.mark.asyncio
async def test_reconciler_prunes_activity_on_every_background_pass(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    prune_calls = 0

    def prune() -> None:
        nonlocal prune_calls
        prune_calls += 1

    async def stop_after_first_sleep(_: float) -> None:
        raise asyncio.CancelledError

    reconciler = CodexNeoRootReconciler(
        codex_home=codex_home,
        sync_service=RecordingSync(),
        sleep=stop_after_first_sleep,
        activity_pruner=prune,
    )

    with pytest.raises(asyncio.CancelledError):
        await reconciler._run()

    assert prune_calls == 1
