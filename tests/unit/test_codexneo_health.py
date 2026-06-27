from __future__ import annotations

import base64
import json

import pytest

from app.core.auth import generate_unique_account_id
from app.modules.codexneo.health import CodexNeoHealthService

pytestmark = pytest.mark.unit


async def _count_accounts() -> int:
    return 2


async def _count_one_account() -> int:
    return 1


def _snapshot_filename(account_key: str) -> str:
    encoded = base64.urlsafe_b64encode(account_key.encode("utf-8")).rstrip(b"=").decode("ascii")
    return f"{encoded}.auth.json"


def _encode_jwt(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    return f"header.{body}.sig"


def _auth_json(*, email: str, account_id: str, plan: str = "pro") -> str:
    return json.dumps(
        {
            "tokens": {
                "idToken": _encode_jwt(
                    {
                        "email": email,
                        "https://api.openai.com/auth": {"chatgpt_plan_type": plan},
                    }
                ),
                "accessToken": f"secret-access-{account_id}",
                "refreshToken": f"secret-refresh-{account_id}",
                "accountId": account_id,
            },
            "lastRefreshAt": "2026-06-24T00:00:00Z",
        }
    )


@pytest.mark.asyncio
async def test_codexneo_health_reports_safe_badges_and_counts(tmp_path) -> None:
    codex_home = tmp_path / "codex-home"
    accounts_dir = codex_home / "accounts"
    accounts_dir.mkdir(parents=True)
    data_dir = tmp_path / "data"
    backup_dir = data_dir / "account-backups"
    backup_dir.mkdir(parents=True)
    (accounts_dir / "registry.json").write_text(
        json.dumps(
            {
                "accounts": [
                    {"account_key": "acc_live", "email": "live@example.com"},
                    {"account_key": "acc_backup", "email": "backup@example.com"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (accounts_dir / "acc_live.auth.json").write_text('{"accessToken":"secret"}', encoding="utf-8")
    (backup_dir / "backup-registry.json").write_text(
        json.dumps({"accounts": [{"account_key": "acc_backup", "email": "backup@example.com"}]}),
        encoding="utf-8",
    )
    (backup_dir / "acc_backup.auth.json").write_text('{"refreshToken":"secret"}', encoding="utf-8")
    settings_path = data_dir / "codexneo-settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "codex_api_base_url": "http://127.0.0.1:2455/v1",
                "codexgo_api_base_url": "https://codexgo.eu/api/codex-auth",
                "codexgo_auto_refresh_enabled": True,
                "codexgo_auto_refresh_interval_minutes": 30,
                "openai_activity_log_enabled": True,
                "management_activity_log_enabled": False,
                "buyer_token_encrypted": "encrypted-token",
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "codexneo-activity.log").write_text("[12:00:00] Management API GET /api/codexneo\n")

    result = await CodexNeoHealthService(
        codex_home=codex_home,
        data_dir=data_dir,
        settings_path=settings_path,
        accounts_count_provider=_count_accounts,
    ).health()

    assert result.overall_status == "ok"
    by_key = {item.key: item for item in result.items}
    assert by_key["codex_home"].status == "ok"
    assert by_key["codex_home"].copy_value == str(codex_home.resolve())
    assert by_key["codex_registry"].detail == "2 registry account(s), 1 auth snapshot(s)"
    assert by_key["backup_store"].detail == "1 backup account(s), 1 auth snapshot(s)"
    assert by_key["accounts_sync"].detail == "2 CodexNeo account(s), 2 Codex IB account(s)"
    assert by_key["activity_log"].message == "OpenAI log on, Management log off"
    assert by_key["codexgo_auth"].message == "Buyer credential saved, auto-refresh every 30 min"
    assert by_key["openai_bridge"].copy_value == "http://127.0.0.1:2455/v1"
    assert "secret" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_codexneo_health_degrades_without_registry_or_accounts_db(tmp_path) -> None:
    codex_home = tmp_path / "missing-home"
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    async def failing_count() -> int:
        raise RuntimeError("database unavailable")

    result = await CodexNeoHealthService(
        codex_home=codex_home,
        data_dir=data_dir,
        accounts_count_provider=failing_count,
    ).health()

    by_key = {item.key: item for item in result.items}
    assert result.overall_status == "error"
    assert by_key["codex_home"].status == "error"
    assert by_key["codex_registry"].status == "warning"
    assert by_key["accounts_sync"].status == "warning"
    assert by_key["accounts_sync"].message == "Codex IB account count unavailable"


@pytest.mark.asyncio
async def test_codexneo_health_reports_mismatch_when_codex_ib_has_extra_accounts(tmp_path) -> None:
    codex_home = tmp_path / "codex-home"
    accounts_dir = codex_home / "accounts"
    accounts_dir.mkdir(parents=True)
    (accounts_dir / "registry.json").write_text(
        json.dumps({"accounts": [{"account_key": "acc_live", "email": "live@example.com"}]}),
        encoding="utf-8",
    )
    (accounts_dir / "acc_live.auth.json").write_text('{"tokens":{"accountId":"acc_live"}}', encoding="utf-8")
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    async def count_extra_accounts() -> int:
        return 2

    result = await CodexNeoHealthService(
        codex_home=codex_home,
        data_dir=data_dir,
        accounts_count_provider=count_extra_accounts,
    ).health()

    accounts_sync = {item.key: item for item in result.items}["accounts_sync"]
    assert result.overall_status == "error"
    assert accounts_sync.status == "error"
    assert accounts_sync.message == "Mismatch"
    assert accounts_sync.detail == "1 CodexNeo account(s), 2 Codex IB account(s)"


@pytest.mark.asyncio
async def test_codexneo_health_counts_root_auth_and_backup_duplicate_once(tmp_path) -> None:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    data_dir = tmp_path / "data"
    backup_dir = data_dir / "account-backups"
    backup_dir.mkdir(parents=True)
    email = "same-account@example.com"
    raw_account_id = "acc_same_identity"
    account_key = generate_unique_account_id(raw_account_id, email)
    raw = _auth_json(email=email, account_id=raw_account_id)
    (codex_home / "auth.json").write_text(raw, encoding="utf-8")
    (backup_dir / "backup-registry.json").write_text(
        json.dumps({"accounts": [{"account_key": account_key, "email": email, "plan": "pro"}]}),
        encoding="utf-8",
    )
    (backup_dir / _snapshot_filename(account_key)).write_text(raw, encoding="utf-8")

    result = await CodexNeoHealthService(
        codex_home=codex_home,
        data_dir=data_dir,
        accounts_count_provider=_count_one_account,
    ).health()

    accounts_sync = {item.key: item for item in result.items}["accounts_sync"]
    assert accounts_sync.status == "ok"
    assert accounts_sync.message == "Counts aligned"
    assert accounts_sync.detail == "1 CodexNeo account(s), 1 Codex IB account(s)"


@pytest.mark.asyncio
async def test_codexneo_health_handles_invalid_refresh_interval_setting(tmp_path) -> None:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    settings_path = data_dir / "codexneo-settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "buyer_token_encrypted": "encrypted-token",
                "codexgo_auto_refresh_enabled": True,
                "codexgo_auto_refresh_interval_minutes": "not-a-number",
            }
        ),
        encoding="utf-8",
    )

    result = await CodexNeoHealthService(
        codex_home=codex_home,
        data_dir=data_dir,
        settings_path=settings_path,
        accounts_count_provider=_count_accounts,
    ).health()

    codexgo = {item.key: item for item in result.items}["codexgo_auth"]
    assert codexgo.message == "Buyer credential saved, auto-refresh every 30 min"
