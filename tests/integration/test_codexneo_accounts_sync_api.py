from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import generate_unique_account_id
from app.modules.accounts import api as accounts_api

pytestmark = pytest.mark.integration


class FakeCodexHomeSync:
    def __init__(self) -> None:
        self.registered: list[bytes] = []
        self.removed: list[tuple[str, str]] = []

    async def register_auth_json_to_codex_home(self, raw: bytes):
        self.registered.append(raw)
        return SimpleNamespace(success=True, message="registered in Codex Home")

    async def remove_account_from_codex_home(self, account):
        self.removed.append((account.id, account.email))
        return SimpleNamespace(success=True, message="removed from Codex Home")


def _encode_jwt(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    return f"header.{body}.sig"


def _auth_json(*, email: str = "sync@example.com", account_id: str = "acc_sync") -> dict:
    return {
        "tokens": {
            "idToken": _encode_jwt(
                {
                    "email": email,
                    "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
                }
            ),
            "accessToken": "secret-access",
            "refreshToken": "secret-refresh",
            "accountId": account_id,
        },
        "lastRefreshAt": "2026-06-23T00:00:00Z",
    }


@pytest.mark.asyncio
async def test_accounts_import_registers_auth_snapshot_with_codex_home(app_instance) -> None:
    sync = FakeCodexHomeSync()
    app_instance.dependency_overrides[accounts_api.get_codexneo_account_sync_service] = lambda: sync
    email = "sync-import@example.com"
    raw_account_id = "acc_sync_import"
    raw = json.dumps(_auth_json(email=email, account_id=raw_account_id)).encode("utf-8")

    async with app_instance.router.lifespan_context(app_instance):
        transport = ASGITransport(app=app_instance)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/accounts/import",
                files={"auth_json": ("auth.json", raw, "application/json")},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["accountId"] == generate_unique_account_id(raw_account_id, email)
    assert data["codexHomeSyncStatus"] == "synced"
    assert sync.registered == [raw]


@pytest.mark.asyncio
async def test_accounts_delete_removes_matching_account_from_codex_home(app_instance) -> None:
    sync = FakeCodexHomeSync()
    app_instance.dependency_overrides[accounts_api.get_codexneo_account_sync_service] = lambda: sync
    email = "sync-delete@example.com"
    raw_account_id = "acc_sync_delete"
    raw = json.dumps(_auth_json(email=email, account_id=raw_account_id)).encode("utf-8")
    account_id = generate_unique_account_id(raw_account_id, email)

    async with app_instance.router.lifespan_context(app_instance):
        transport = ASGITransport(app=app_instance)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            import_response = await client.post(
                "/api/accounts/import",
                files={"auth_json": ("auth.json", raw, "application/json")},
            )
            delete_response = await client.delete(f"/api/accounts/{account_id}")

    assert import_response.status_code == 200
    assert delete_response.status_code == 200
    assert delete_response.json()["codexHomeSyncStatus"] == "synced"
    assert sync.removed == [(account_id, email)]
