from __future__ import annotations

import base64
import json

import pytest

from app.core.auth import generate_unique_account_id
from app.modules.codexneo.accounts import CodexHomeAccountService
from app.modules.codexneo.locations import CodexNeoAccountLocationService
from app.modules.codexneo.snapshots import preferred_snapshot_path

pytestmark = pytest.mark.unit


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


def _write_live_account(codex_home, account_key: str, *, email: str | None = None, active: bool = False) -> None:
    accounts = codex_home / "accounts"
    accounts.mkdir(parents=True, exist_ok=True)
    registry = accounts / "registry.json"
    row = {
        "account_key": account_key,
        "email": email or f"{account_key}@example.com",
        "plan": "pro",
    }
    if registry.exists():
        registry_data = json.loads(registry.read_text(encoding="utf-8"))
        registry_accounts = [
            item
            for item in registry_data.get("accounts", [])
            if isinstance(item, dict) and item.get("account_key") != account_key
        ]
    else:
        registry_data = {"schema_version": 4, "active_account_key": None, "accounts": []}
        registry_accounts = []
    registry_accounts.append(row)
    registry_data["accounts"] = registry_accounts
    if active:
        registry_data["active_account_key"] = account_key
    registry.write_text(
        json.dumps(registry_data),
        encoding="utf-8",
    )
    (accounts / f"{account_key}.auth.json").write_text(
        json.dumps({"tokens": {"access_token": f"secret-{account_key}", "account_id": account_key}}),
        encoding="utf-8",
    )
    if active:
        (codex_home / "auth.json").write_text("{}", encoding="utf-8")


def test_root_auth_json_does_not_duplicate_registered_snapshot(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    email = "active-root@example.com"
    account_id = "acc-active-root"
    root_account_key = generate_unique_account_id(account_id, email)
    account_key = f"user-active::{account_id}"
    auth_json = _auth_json(email=email, account_id=account_id)
    accounts = codex_home / "accounts"
    accounts.mkdir(parents=True)
    (codex_home / "auth.json").write_text(auth_json, encoding="utf-8")
    preferred_snapshot_path(accounts, account_key).write_text(auth_json, encoding="utf-8")
    (accounts / "registry.json").write_text(
        json.dumps(
            {
                "schema_version": 4,
                "active_account_key": account_key,
                "accounts": [{"account_key": account_key, "email": email, "plan": "pro"}],
            }
        ),
        encoding="utf-8",
    )
    service = CodexNeoAccountLocationService(codex_home=codex_home, data_dir=data_dir)

    rows = service.all_account_rows()

    assert len(rows) == 1
    assert rows[0]["account_key"] == account_key
    assert rows[0]["account_key"] != root_account_key
    assert rows[0]["email"] == email
    assert rows[0]["active"] is True
    assert rows[0]["codex"] is True


def test_root_rotation_keeps_earlier_backup_identity_visible(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    codex_home.mkdir()
    first_email = "first-root@example.com"
    first_account_id = "acc_first_root"
    second_email = "second-root@example.com"
    second_account_id = "acc_second_root"
    (codex_home / "auth.json").write_text(
        _auth_json(email=first_email, account_id=first_account_id),
        encoding="utf-8",
    )
    service = CodexNeoAccountLocationService(codex_home=codex_home, data_dir=data_dir)
    assert service.set_bulk_default(location="backup", present=True).success is True

    (codex_home / "auth.json").write_text(
        _auth_json(email=second_email, account_id=second_account_id),
        encoding="utf-8",
    )
    state = CodexHomeAccountService(codex_home=codex_home, data_dir=data_dir).load_accounts()

    assert {account.email for account in state.accounts} == {first_email, second_email}
    assert len(state.accounts) == 2
    assert all(account.backup for account in state.accounts)


def test_backup_all_off_counts_logical_root_and_backup_identities(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text(
        _auth_json(email="first-root@example.com", account_id="acc_first_root"),
        encoding="utf-8",
    )
    service = CodexNeoAccountLocationService(codex_home=codex_home, data_dir=data_dir)
    assert service.set_bulk_default(location="backup", present=True).success is True
    (codex_home / "auth.json").write_text(
        _auth_json(email="second-root@example.com", account_id="acc_second_root"),
        encoding="utf-8",
    )
    assert service.set_bulk_default(location="backup", present=True).success is True

    result = service.set_bulk_default(location="backup", present=False)

    assert result.success is False
    assert result.message == (
        "Removed backup for 0 account(s). "
        "Skipped 2 account(s) because they must remain in Backup."
    )


def _write_backup_account(data_dir, account_key: str, *, email: str, auth_account_id: str) -> None:
    backup_dir = data_dir / "account-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    registry = backup_dir / "backup-registry.json"
    registry.write_text(
        json.dumps({"schema_version": 4, "accounts": [{"account_key": account_key, "email": email, "plan": "pro"}]}),
        encoding="utf-8",
    )
    preferred_snapshot_path(backup_dir, account_key).write_text(
        json.dumps({"tokens": {"access_token": f"secret-{account_key}", "account_id": auth_account_id}}),
        encoding="utf-8",
    )


def test_location_actions_resolve_equivalent_live_and_backup_keys(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    email = "same-real@example.com"
    _write_live_account(codex_home, "live-key", email=email)
    _write_backup_account(data_dir, "backup-copy-key", email=email, auth_account_id="live-key")
    service = CodexNeoAccountLocationService(codex_home=codex_home, data_dir=data_dir)

    state = CodexHomeAccountService(codex_home=codex_home, data_dir=data_dir).load_accounts()

    assert len(state.accounts) == 1
    assert state.accounts[0].account_key == "live-key"
    assert state.accounts[0].backup is True

    removed_backup = service.set_location(["live-key"], location="backup", present=False)

    assert removed_backup.success is True
    assert not (data_dir / "account-backups" / "backup-copy-key.auth.json").exists()
    backup_registry = data_dir / "account-backups" / "backup-registry.json"
    if backup_registry.exists():
        assert json.loads(backup_registry.read_text(encoding="utf-8"))["accounts"] == []


def test_backup_toggle_copies_and_removes_backup_snapshot_without_disabling_last_location(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    _write_live_account(codex_home, "acct-1")
    service = CodexNeoAccountLocationService(codex_home=codex_home, data_dir=tmp_path / "data")

    backed_up = service.set_location(["acct-1"], location="backup", present=True)

    assert backed_up.success is True
    assert (tmp_path / "data" / "account-backups" / "acct-1.auth.json").is_file()
    assert json.loads((tmp_path / "data" / "account-backups" / "backup-registry.json").read_text())["accounts"][0][
        "account_key"
    ] == "acct-1"

    removed = service.set_location(["acct-1"], location="backup", present=False)

    assert removed.success is True
    assert not (tmp_path / "data" / "account-backups" / "acct-1.auth.json").exists()

    blocked = service.set_location(["acct-1"], location="codex", present=False)

    assert blocked.success is False
    assert "Backup is off" in blocked.message
    assert (codex_home / "accounts" / "acct-1.auth.json").is_file()


def test_backup_present_replaces_older_backup_copy_for_same_auth_identity(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    _write_live_account(codex_home, "live-current-key", email="duplicate-backup@example.com")
    _write_backup_account(
        data_dir,
        "old-backup-key",
        email="duplicate-backup@example.com",
        auth_account_id="live-current-key",
    )
    service = CodexNeoAccountLocationService(codex_home=codex_home, data_dir=data_dir)

    backed_up = service.ensure_backup_present(["live-current-key"])

    assert backed_up.success is True
    backup_registry = json.loads((data_dir / "account-backups" / "backup-registry.json").read_text(encoding="utf-8"))
    assert [account["account_key"] for account in backup_registry["accounts"]] == ["live-current-key"]
    assert not (data_dir / "account-backups" / "old-backup-key.auth.json").exists()
    assert (data_dir / "account-backups" / "live-current-key.auth.json").is_file()


def test_codex_toggle_restores_from_backup_and_delete_everywhere_removes_live_and_backup(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    _write_live_account(codex_home, "acct-1", active=True)
    service = CodexNeoAccountLocationService(codex_home=codex_home, data_dir=tmp_path / "data")
    service.set_location(["acct-1"], location="backup", present=True)

    removed_from_codex = service.set_location(["acct-1"], location="codex", present=False)

    assert removed_from_codex.success is True
    assert not (codex_home / "accounts" / "acct-1.auth.json").exists()
    assert not (codex_home / "auth.json").exists()

    restored = service.set_location(["acct-1"], location="codex", present=True)

    assert restored.success is True
    assert (codex_home / "accounts" / "acct-1.auth.json").is_file()

    deleted = service.delete_everywhere(["acct-1"])

    assert deleted.success is True
    assert not (codex_home / "accounts" / "acct-1.auth.json").exists()
    assert not (tmp_path / "data" / "account-backups" / "acct-1.auth.json").exists()
    assert "Removed 1 from Codex Home and 1 from Backup" in deleted.message


def test_delete_everywhere_removes_backup_only_encoded_snapshot_key(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    account_key = "user-abc::workspace-123"
    _write_backup_account(
        data_dir,
        account_key,
        email="backup-only@example.com",
        auth_account_id="workspace-123",
    )
    snapshot = preferred_snapshot_path(data_dir / "account-backups", account_key)
    service = CodexNeoAccountLocationService(codex_home=codex_home, data_dir=data_dir)

    deleted = service.delete_everywhere([account_key])

    assert deleted.success is True
    assert "Removed 0 from Codex Home and 1 from Backup" in deleted.message
    assert not snapshot.exists()
    backup_registry = data_dir / "account-backups" / "backup-registry.json"
    assert not backup_registry.exists()


def test_backup_all_follows_visible_state_and_manual_off_disables_future_default(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    _write_live_account(codex_home, "acct-1")
    service = CodexNeoAccountLocationService(codex_home=codex_home, data_dir=tmp_path / "data")

    enabled = service.set_bulk_default(location="backup", present=True)

    assert enabled.success is True
    assert (tmp_path / "data" / "account-backups" / "acct-1.auth.json").is_file()
    assert service.location_settings()["backup_all_enabled"] is True

    service.set_location(["acct-1"], location="backup", present=False)
    service.apply_bulk_defaults()

    assert not (tmp_path / "data" / "account-backups" / "acct-1.auth.json").exists()
    assert service.location_settings()["backup_all_enabled"] is False

    _write_live_account(codex_home, "acct-2")
    service.apply_bulk_defaults()

    assert not (tmp_path / "data" / "account-backups" / "acct-1.auth.json").exists()
    assert not (tmp_path / "data" / "account-backups" / "acct-2.auth.json").exists()

    service.set_bulk_default(location="backup", present=True)

    assert (tmp_path / "data" / "account-backups" / "acct-1.auth.json").is_file()
    assert (tmp_path / "data" / "account-backups" / "acct-2.auth.json").is_file()
    assert service.location_settings()["backup_all_enabled"] is True


def test_codex_all_is_not_a_future_restore_default_for_backup_only_accounts(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    _write_live_account(codex_home, "acct-live")
    service = CodexNeoAccountLocationService(codex_home=codex_home, data_dir=data_dir)

    enabled = service.set_bulk_default(location="codex", present=True)
    assert enabled.success is True
    assert service.location_settings()["codex_all_enabled"] is True

    _write_live_account(codex_home, "acct-backup-only")
    service.set_location(["acct-backup-only"], location="backup", present=True)
    service.set_location(["acct-backup-only"], location="codex", present=False)

    service.apply_bulk_defaults()

    assert not (codex_home / "accounts" / "acct-backup-only.auth.json").exists()
    state = CodexHomeAccountService(codex_home=codex_home, data_dir=data_dir).load_accounts()
    backup_only = next(account for account in state.accounts if account.account_key == "acct-backup-only")
    assert backup_only.codex is False
    assert backup_only.backup is True


def test_account_discovery_merges_backup_only_rows_and_reports_bulk_defaults(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    _write_live_account(codex_home, "acct-1")
    location_service = CodexNeoAccountLocationService(codex_home=codex_home, data_dir=tmp_path / "data")
    location_service.set_location(["acct-1"], location="backup", present=True)
    location_service.set_location(["acct-1"], location="codex", present=False)

    state = CodexHomeAccountService(codex_home=codex_home, data_dir=tmp_path / "data").load_accounts()

    assert [account.account_key for account in state.accounts] == ["acct-1"]
    assert state.accounts[0].codex is False
    assert state.accounts[0].backup is True
    assert state.backup_all_enabled is True
