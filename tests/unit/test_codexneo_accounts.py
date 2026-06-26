from __future__ import annotations

import base64
import json
import time

from app.modules.codexneo.accounts import CodexHomeAccountService

pytestmark = __import__("pytest").mark.unit


def _snapshot_filename(account_key: str) -> str:
    encoded = base64.urlsafe_b64encode(account_key.encode("utf-8")).rstrip(b"=").decode("ascii")
    return f"{encoded}.auth.json"


def test_registry_account_discovery_returns_safe_fields_and_active_marker(tmp_path) -> None:
    now = int(time.time())
    codex_home = tmp_path / ".codex"
    registry_path = codex_home / "accounts" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "active_account_key": "acct-active",
                "accounts": [
                    {
                        "account_key": "acct-active",
                        "selector": "t01.036252.89@gmail.com",
                        "email": "t01.036252.89@gmail.com",
                        "alias": "Primary",
                        "account_name": "Primary Codex",
                        "plan": "Pro",
                        "auth_mode": "chatgpt",
                        "last_usage_at": now,
                        "last_usage": {
                            "status": "ok",
                            "primary": {
                                "used_percent": 98,
                                "resets_at": "2026-06-22T18:23:00Z",
                                "window_minutes": 300,
                            },
                            "secondary": {
                                "used_percent": 49,
                                "resets_at": "2026-06-28T11:54:00Z",
                                "window_minutes": 10080,
                            },
                        },
                        "codex": True,
                        "backup": True,
                        "api": True,
                        "api_hour_count": 2,
                        "api_day_count": 7,
                        "access_token": "secret-access",
                        "refresh_token": "secret-refresh",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (codex_home / "accounts" / "acct-active.auth.json").write_text(
        json.dumps({"tokens": {"access_token": "secret-active", "account_id": "acct-active"}}),
        encoding="utf-8",
    )
    backup_dir = tmp_path / "data" / "account-backups"
    backup_dir.mkdir(parents=True)
    (backup_dir / "backup-registry.json").write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        "account_key": "acct-active",
                        "email": "t01.036252.89@gmail.com",
                        "plan": "Pro",
                    },
                    {
                        "account_key": "acct-backup",
                        "email": "backup@example.com",
                        "plan": "Plus",
                        "last_usage_at": now - (7 * 60 * 60),
                        "last_usage": {"status": "stored"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (backup_dir / "acct-active.auth.json").write_text(
        json.dumps({"tokens": {"access_token": "secret-backup", "account_id": "acct-active"}}),
        encoding="utf-8",
    )
    (backup_dir / "acct-backup.auth.json").write_text(
        json.dumps({"tokens": {"access_token": "secret-backup-only", "account_id": "acct-backup"}}),
        encoding="utf-8",
    )

    state = CodexHomeAccountService(codex_home=codex_home, data_dir=tmp_path / "data").load_accounts()
    dumped = state.model_dump_json()

    assert state.registry_path == str(registry_path)
    assert state.active_account_key == "acct-active"
    assert state.message == "Loaded 2 account(s) from Codex registry"
    assert [account.account_key for account in state.accounts] == ["acct-active", "acct-backup"]
    assert state.accounts[0].active is True
    assert state.accounts[0].email == "t01.036252.89@gmail.com"
    assert state.accounts[0].plan == "Pro"
    assert state.accounts[0].usage.primary.used_percent == 98
    assert state.accounts[0].usage.secondary.used_percent == 49
    assert state.accounts[0].codex is True
    assert state.accounts[0].backup is True
    assert state.accounts[0].api is True
    assert state.accounts[0].api_hour_count == 2
    assert state.accounts[0].api_day_count == 7
    assert state.accounts[0].availability == "Ready"
    assert state.accounts[0].status == "Fresh / just now"
    assert state.accounts[1].availability == "Backup"
    assert state.accounts[1].status == "Stored / 7h ago"
    assert "secret-access" not in dumped
    assert "secret-refresh" not in dumped


def test_registry_account_discovery_handles_missing_or_invalid_registry(tmp_path) -> None:
    codex_home = tmp_path / ".codex"

    missing = CodexHomeAccountService(codex_home=codex_home, data_dir=tmp_path / "data").load_accounts()

    assert missing.accounts == []
    assert missing.message == "Codex account registry not found"

    registry_path = codex_home / "accounts" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text("{not valid json", encoding="utf-8")

    invalid = CodexHomeAccountService(codex_home=codex_home, data_dir=tmp_path / "data").load_accounts()

    assert invalid.accounts == []
    assert invalid.registry_path == str(registry_path)
    assert invalid.message == "Codex account registry is invalid JSON"


def test_registry_account_without_snapshot_still_reports_ready_availability(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    registry_path = codex_home / "accounts" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "active_account_key": "acct-live",
                "accounts": [
                    {
                        "account_key": "acct-live",
                        "email": "live@example.com",
                        "last_usage_at": int(time.time()),
                        "last_usage": {"status": "ok"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    state = CodexHomeAccountService(codex_home=codex_home, data_dir=tmp_path / "data").load_accounts()

    assert state.accounts[0].codex is False
    assert state.accounts[0].availability == "Ready"
    assert state.accounts[0].status == "Fresh / just now"


def test_registry_account_discovery_matches_encoded_codex_auth_snapshot_filename(tmp_path) -> None:
    account_key = "user-live-key::20658dfd-4384-4993-acab-ad195ad94e79"
    codex_home = tmp_path / ".codex"
    registry_path = codex_home / "accounts" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "active_account_key": account_key,
                "accounts": [
                    {
                        "account_key": account_key,
                        "email": "encoded@example.com",
                        "last_usage_at": int(time.time()),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (codex_home / "accounts" / _snapshot_filename(account_key)).write_text(
        json.dumps({"tokens": {"access_token": "secret", "account_id": "20658dfd-4384-4993-acab-ad195ad94e79"}}),
        encoding="utf-8",
    )

    state = CodexHomeAccountService(codex_home=codex_home, data_dir=tmp_path / "data").load_accounts()

    assert state.accounts[0].account_key == account_key
    assert state.accounts[0].codex is True


def test_registry_account_discovery_deduplicates_same_real_auth_identity(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    accounts_dir = codex_home / "accounts"
    accounts_dir.mkdir(parents=True)
    accounts_dir.joinpath("registry.json").write_text(
        json.dumps(
            {
                "active_account_key": "live-key",
                "accounts": [
                    {
                        "account_key": "live-key",
                        "email": "same-real@example.com",
                        "plan": "pro",
                        "last_usage_at": int(time.time()),
                        "last_usage": {"primary": {"used_percent": 15}},
                    },
                    {
                        "account_key": "live-copy-key",
                        "email": "same-real@example.com",
                        "plan": "pro",
                        "last_usage_at": int(time.time()) - 60,
                        "last_usage": {"primary": {"used_percent": 99}},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    auth_payload = json.dumps({"tokens": {"access_token": "secret", "account_id": "acc_same_real"}})
    accounts_dir.joinpath("live-key.auth.json").write_text(auth_payload, encoding="utf-8")
    accounts_dir.joinpath("live-copy-key.auth.json").write_text(auth_payload, encoding="utf-8")
    backup_dir = tmp_path / "data" / "account-backups"
    backup_dir.mkdir(parents=True)
    backup_dir.joinpath("backup-registry.json").write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        "account_key": "backup-copy-key",
                        "email": "same-real@example.com",
                        "plan": "pro",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    backup_dir.joinpath("backup-copy-key.auth.json").write_text(auth_payload, encoding="utf-8")

    state = CodexHomeAccountService(codex_home=codex_home, data_dir=tmp_path / "data").load_accounts()

    assert len(state.accounts) == 1
    assert state.accounts[0].account_key == "live-key"
    assert state.accounts[0].codex is True
    assert state.accounts[0].backup is True
    assert state.accounts[0].status == "Fresh / just now"


def test_registry_account_with_usage_window_without_status_reports_fresh(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    registry_path = codex_home / "accounts" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        "account_key": "usage-key",
                        "email": "usage@example.com",
                        "last_usage_at": int(time.time()),
                        "last_usage": {
                            "primary": {
                                "used_percent": 51,
                                "window_minutes": 300,
                            }
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (codex_home / "accounts" / "usage-key.auth.json").write_text(
        json.dumps({"tokens": {"access_token": "secret", "account_id": "acc_usage"}}),
        encoding="utf-8",
    )

    state = CodexHomeAccountService(codex_home=codex_home, data_dir=tmp_path / "data").load_accounts()

    assert state.accounts[0].status == "Fresh / just now"
