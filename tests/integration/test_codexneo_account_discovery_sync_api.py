from __future__ import annotations

import base64
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import generate_unique_account_id
from app.modules.codexneo import api as codexneo_api
from app.modules.codexneo.accounts import CodexHomeAccountService
from app.modules.codexneo.schemas import CodexNeoAccountsResponse
from app.modules.codexneo.sync import CodexNeoAccountsSyncService, CodexNeoSyncResult

pytestmark = pytest.mark.integration


def _encode_jwt(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    return f"header.{body}.sig"


def _auth_json(*, email: str, account_id: str) -> bytes:
    return json.dumps(
        {
            "tokens": {
                "idToken": _encode_jwt(
                    {
                        "email": email,
                        "https://api.openai.com/auth": {"chatgpt_plan_type": "pro"},
                    }
                ),
                "accessToken": "secret-access",
                "refreshToken": "secret-refresh",
                "accountId": account_id,
            },
            "lastRefreshAt": "2026-06-24T00:00:00Z",
        }
    ).encode("utf-8")


def _write_live_account(codex_home, account_key: str, *, email: str, raw_account_id: str) -> None:
    accounts_dir = codex_home / "accounts"
    accounts_dir.mkdir(parents=True, exist_ok=True)
    (accounts_dir / "registry.json").write_text(
        json.dumps(
            {
                "schema_version": 4,
                "active_account_key": account_key,
                "accounts": [{"account_key": account_key, "email": email, "plan": "pro"}],
            }
        ),
        encoding="utf-8",
    )
    (accounts_dir / f"{account_key}.auth.json").write_bytes(
        _auth_json(email=email, account_id=raw_account_id),
    )


@pytest.mark.asyncio
async def test_codexneo_accounts_get_is_read_only(app_instance) -> None:
    class FakeAccountService:
        def __init__(self) -> None:
            self.sync_calls = 0

        async def load_accounts_with_codex_ib_usage(self) -> CodexNeoAccountsResponse:
            return CodexNeoAccountsResponse(
                accounts=[],
                active_account_key=None,
                registry_path=None,
                message="read-only load",
            )

        async def sync_and_load_accounts(self) -> CodexNeoAccountsResponse:
            self.sync_calls += 1
            raise AssertionError("GET /api/codexneo/accounts must not sync or write")

    account_service = FakeAccountService()
    app_instance.dependency_overrides[codexneo_api.get_account_service] = lambda: account_service

    async with app_instance.router.lifespan_context(app_instance):
        transport = ASGITransport(app=app_instance)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/codexneo/accounts")

    assert response.status_code == 200
    assert response.json()["message"] == "read-only load"
    assert account_service.sync_calls == 0


@pytest.mark.asyncio
async def test_codexneo_accounts_sync_imports_codex_home_accounts_into_accounts_tab(
    app_instance,
    tmp_path,
) -> None:
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    email = "refresh-sync@example.com"
    raw_account_id = "acc_refresh_sync"
    _write_live_account(codex_home, "refresh-key", email=email, raw_account_id=raw_account_id)
    app_instance.dependency_overrides[codexneo_api.get_account_sync_service] = lambda: CodexNeoAccountsSyncService(
        codex_home=codex_home,
        data_dir=data_dir,
    )
    app_instance.dependency_overrides[codexneo_api.get_account_service] = lambda: CodexHomeAccountService(
        codex_home=codex_home,
        data_dir=data_dir,
    )

    async with app_instance.router.lifespan_context(app_instance):
        transport = ASGITransport(app=app_instance)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            sync_response = await client.post("/api/codexneo/accounts/sync")
            codexneo_response = await client.get("/api/codexneo/accounts")
            accounts_response = await client.get("/api/accounts")

    assert sync_response.status_code == 200
    assert codexneo_response.status_code == 200
    assert accounts_response.status_code == 200
    account_ids = [account["accountId"] for account in accounts_response.json()["accounts"]]
    assert generate_unique_account_id(raw_account_id, email) in account_ids
    assert "secret-access" not in codexneo_response.text


@pytest.mark.asyncio
async def test_codexneo_accounts_sync_endpoint_runs_master_sync(app_instance) -> None:
    class FakeSyncService:
        def __init__(self) -> None:
            self.calls = 0

        async def sync_all_accounts(self):
            self.calls += 1
            return CodexNeoSyncResult(success=True, message="master sync ok", count=2)

    sync_service = FakeSyncService()
    app_instance.dependency_overrides[codexneo_api.get_account_sync_service] = lambda: sync_service

    async with app_instance.router.lifespan_context(app_instance):
        transport = ASGITransport(app=app_instance)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post("/api/codexneo/accounts/sync")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "master sync ok"
    assert sync_service.calls == 1


@pytest.mark.asyncio
async def test_codexneo_location_rejects_invalid_location_value(app_instance) -> None:
    async with app_instance.router.lifespan_context(app_instance):
        transport = ASGITransport(app=app_instance)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/codexneo/accounts/location",
                json={"accountKeys": ["acct-1"], "location": "archive", "present": True},
            )

    assert response.status_code == 422
