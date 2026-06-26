from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest

from app.core.auth import generate_unique_account_id
from app.db.models import DashboardSettings
from app.db.session import get_background_session
from app.modules.accounts.repository import AccountsRepository
from app.modules.accounts.service import AccountsService
from app.modules.codexneo.locations import CodexNeoAccountLocationService
from app.modules.codexneo.sync import CodexNeoAccountsSyncService
from app.modules.usage.updater import UsageUpdater

pytestmark = pytest.mark.unit


class StrictSingleRemoveCommandRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str]] = []

    async def __call__(self, args: list[str], *, codex_home: str) -> tuple[bool, str]:
        self.calls.append((args, codex_home))
        if args and args[0] == "remove" and len(args) != 2:
            return False, "error: unexpected extra selector for 'remove'"
        return True, "command ok"


class SchemaUnsupportedRemoveCommandRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str]] = []

    async def __call__(self, args: list[str], *, codex_home: str) -> tuple[bool, str]:
        self.calls.append((args, codex_home))
        if args and args[0] == "remove":
            return False, "error: registry schema version 5 is newer than this codex-auth binary supports (max 3)"
        return True, "command ok"


class UnexpectedRemoveCommandRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str]] = []

    async def __call__(self, args: list[str], *, codex_home: str) -> tuple[bool, str]:
        self.calls.append((args, codex_home))
        if args and args[0] == "remove":
            return False, "remove should not be called for unsupported registry schema"
        return True, "command ok"


class RecordingCommandRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str]] = []

    async def __call__(self, args: list[str], *, codex_home: str) -> tuple[bool, str]:
        self.calls.append((args, codex_home))
        return True, "command ok"


def _encode_jwt(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    return f"header.{body}.sig"


def _auth_json(*, email: str, account_id: str, plan: str = "pro") -> bytes:
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
    ).encode("utf-8")


def _write_live_account(
    codex_home,
    account_key: str,
    *,
    email: str,
    raw_account_id: str,
    schema_version: int = 4,
) -> None:
    accounts_dir = codex_home / "accounts"
    accounts_dir.mkdir(parents=True, exist_ok=True)
    registry_path = accounts_dir / "registry.json"
    if registry_path.exists():
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry_accounts = [
            item
            for item in registry.get("accounts", [])
            if isinstance(item, dict) and item.get("account_key") != account_key
        ]
    else:
        registry = {"schema_version": schema_version, "active_account_key": account_key, "accounts": []}
        registry_accounts = []
    registry_accounts.append(
        {
            "account_key": account_key,
            "email": email,
            "plan": "pro",
        }
    )
    registry["schema_version"] = schema_version
    registry["accounts"] = registry_accounts
    registry["active_account_key"] = registry.get("active_account_key") or account_key
    (accounts_dir / "registry.json").write_text(
        json.dumps(registry),
        encoding="utf-8",
    )
    (accounts_dir / f"{account_key}.auth.json").write_bytes(
        _auth_json(email=email, account_id=raw_account_id),
    )
    (accounts_dir / "not-auth.json").write_text('{"not":"auth"}', encoding="utf-8")


def _write_backup_account(data_dir, account_key: str, *, email: str, raw_account_id: str) -> None:
    backup_dir = data_dir / "account-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / "backup-registry.json").write_text(
        json.dumps(
            {
                "schema_version": 4,
                "accounts": [
                    {
                        "account_key": account_key,
                        "email": email,
                        "plan": "plus",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (backup_dir / f"{account_key}.auth.json").write_bytes(
        _auth_json(email=email, account_id=raw_account_id, plan="plus"),
    )


async def _account_ids() -> list[str]:
    async with get_background_session() as session:
        repo = AccountsRepository(session)
        accounts = await repo.list_accounts(refresh_existing=True)
        return sorted(account.id for account in accounts)


async def _import_account_to_db(raw: bytes) -> None:
    async with get_background_session() as session:
        await AccountsService(AccountsRepository(session)).import_account(raw)


@pytest.mark.asyncio
async def test_sync_codex_home_snapshots_to_accounts_and_backup(tmp_path, db_setup) -> None:
    del db_setup
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    _write_live_account(
        codex_home,
        "existing-live-key",
        email="existing-live@example.com",
        raw_account_id="acc_existing_live",
    )
    location_service = CodexNeoAccountLocationService(codex_home=codex_home, data_dir=data_dir)
    assert location_service.set_bulk_default(location="backup", present=True).success is True
    email = "codexgo-live@example.com"
    raw_account_id = "acc_codexgo_live"
    _write_live_account(codex_home, "live-key", email=email, raw_account_id=raw_account_id)
    service = CodexNeoAccountsSyncService(codex_home=codex_home, data_dir=data_dir)

    result = await service.sync_codex_home_to_accounts()

    assert result.success is True
    assert result.count == 2
    assert generate_unique_account_id(raw_account_id, email) in await _account_ids()
    assert (data_dir / "account-backups" / "live-key.auth.json").is_file()
    assert "secret-access" not in result.message
    assert "not-auth" not in result.message


@pytest.mark.asyncio
async def test_sync_codex_home_does_not_backup_live_accounts_when_backup_all_is_off(tmp_path, db_setup) -> None:
    del db_setup
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    email = "codexgo-live-no-backup@example.com"
    raw_account_id = "acc_codexgo_live_no_backup"
    _write_live_account(codex_home, "live-no-backup-key", email=email, raw_account_id=raw_account_id)
    service = CodexNeoAccountsSyncService(codex_home=codex_home, data_dir=data_dir)

    result = await service.sync_codex_home_to_accounts()

    assert result.success is True
    assert result.count == 1
    assert generate_unique_account_id(raw_account_id, email) in await _account_ids()
    assert not (data_dir / "account-backups" / "live-no-backup-key.auth.json").exists()
    assert "Backup:" not in result.message


@pytest.mark.asyncio
async def test_sync_root_auth_json_without_managed_snapshot_to_accounts(tmp_path, db_setup) -> None:
    del db_setup
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    data_dir = tmp_path / "data"
    email = "root-auth@example.com"
    raw_account_id = "acc_root_auth"
    (codex_home / "auth.json").write_bytes(_auth_json(email=email, account_id=raw_account_id))
    service = CodexNeoAccountsSyncService(codex_home=codex_home, data_dir=data_dir)

    result = await service.sync_codex_home_to_accounts()

    assert result.success is True
    assert result.count == 1
    assert generate_unique_account_id(raw_account_id, email) in await _account_ids()
    assert "secret-access" not in result.message


@pytest.mark.asyncio
async def test_sync_backup_only_snapshots_to_accounts(tmp_path, db_setup) -> None:
    del db_setup
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    email = "backup-only@example.com"
    raw_account_id = "acc_backup_only"
    _write_backup_account(data_dir, "backup-key", email=email, raw_account_id=raw_account_id)
    service = CodexNeoAccountsSyncService(codex_home=codex_home, data_dir=data_dir)

    result = await service.sync_codex_home_to_accounts()

    assert result.success is True
    assert result.count == 1
    assert generate_unique_account_id(raw_account_id, email) in await _account_ids()
    assert "secret-refresh" not in result.message


@pytest.mark.asyncio
async def test_refresh_selected_account_usage_resolves_codexneo_key(tmp_path, db_setup, monkeypatch) -> None:
    del db_setup
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    email = "selected-refresh@example.com"
    raw_account_id = "acc_selected_refresh"
    expected_account_id = generate_unique_account_id(raw_account_id, email)
    _write_live_account(codex_home, "selected-key", email=email, raw_account_id=raw_account_id)
    refreshed_ids: list[str] = []

    async def fake_force_refresh(self, account):
        del self
        refreshed_ids.append(account.id)
        return True

    monkeypatch.setattr(UsageUpdater, "force_refresh", fake_force_refresh)
    service = CodexNeoAccountsSyncService(codex_home=codex_home, data_dir=data_dir)

    result = await service.refresh_selected_account_usage(["selected-key"])

    assert result.success is True
    assert result.count == 1
    assert refreshed_ids == [expected_account_id]


@pytest.mark.asyncio
async def test_discovery_sync_is_idempotent_when_import_without_overwrite_is_enabled(tmp_path, db_setup) -> None:
    del db_setup
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    email = "repeat-discovery@example.com"
    raw_account_id = "acc_repeat_discovery"
    expected_account_id = generate_unique_account_id(raw_account_id, email)
    _write_live_account(codex_home, "repeat-key", email=email, raw_account_id=raw_account_id)
    async with get_background_session() as session:
        session.add(DashboardSettings(id=1, import_without_overwrite=True))
        await session.commit()
    service = CodexNeoAccountsSyncService(codex_home=codex_home, data_dir=data_dir)

    first = await service.sync_codex_home_to_accounts()
    second = await service.sync_codex_home_to_accounts()

    assert first.success is True
    assert second.success is True
    account_ids = await _account_ids()
    assert account_ids == [expected_account_id]
    assert all("__copy" not in account_id for account_id in account_ids)


@pytest.mark.asyncio
async def test_accounts_delete_removes_matching_codex_home_keys_one_selector_at_a_time(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    email = "delete-many@example.com"
    raw_account_id = "acc_delete_many"
    _write_live_account(codex_home, "live-key-1", email=email, raw_account_id=raw_account_id)
    _write_live_account(codex_home, "live-key-2", email=email, raw_account_id=raw_account_id)
    runner = StrictSingleRemoveCommandRunner()
    account = SimpleNamespace(
        email=email,
        chatgpt_account_id=raw_account_id,
        workspace_id=None,
        workspace_label=None,
    )
    service = CodexNeoAccountsSyncService(codex_home=codex_home, data_dir=tmp_path / "data", command_runner=runner)

    result = await service.remove_account_from_codex_home(account)

    assert result.success is True
    assert result.count == 2
    assert runner.calls == [
        (["remove", "live-key-1"], str(codex_home.resolve())),
        (["remove", "live-key-2"], str(codex_home.resolve())),
    ]


@pytest.mark.asyncio
async def test_accounts_delete_removes_matching_backup_when_codex_auth_remove_succeeds(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    email = "delete-backup-copy@example.com"
    raw_account_id = "acc_delete_backup_copy"
    _write_live_account(codex_home, "live-delete-key", email=email, raw_account_id=raw_account_id)
    _write_backup_account(data_dir, "backup-delete-key", email=email, raw_account_id=raw_account_id)
    runner = StrictSingleRemoveCommandRunner()
    account = SimpleNamespace(
        email=email,
        chatgpt_account_id=raw_account_id,
        workspace_id=None,
        workspace_label=None,
    )
    service = CodexNeoAccountsSyncService(codex_home=codex_home, data_dir=data_dir, command_runner=runner)

    result = await service.remove_account_from_codex_home(account)

    assert result.success is True
    assert result.count == 1
    assert runner.calls == [(["remove", "live-delete-key"], str(codex_home.resolve()))]
    assert not (data_dir / "account-backups" / "backup-delete-key.auth.json").exists()
    backup_registry = data_dir / "account-backups" / "backup-registry.json"
    assert not backup_registry.exists()


@pytest.mark.asyncio
async def test_accounts_delete_removes_backup_only_match_when_codex_home_has_no_live_key(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    email = "delete-backup-only@example.com"
    raw_account_id = "acc_delete_backup_only"
    _write_backup_account(data_dir, "backup-only-delete-key", email=email, raw_account_id=raw_account_id)
    runner = StrictSingleRemoveCommandRunner()
    account = SimpleNamespace(
        email=email,
        chatgpt_account_id=raw_account_id,
        workspace_id=None,
        workspace_label=None,
    )
    service = CodexNeoAccountsSyncService(codex_home=codex_home, data_dir=data_dir, command_runner=runner)

    result = await service.remove_account_from_codex_home(account)

    assert result.success is True
    assert result.count == 1
    assert runner.calls == []
    assert not (data_dir / "account-backups" / "backup-only-delete-key.auth.json").exists()
    assert not (data_dir / "account-backups" / "backup-registry.json").exists()


@pytest.mark.asyncio
async def test_accounts_delete_uses_local_remove_when_codex_auth_schema_is_unsupported(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    email = "delete-schema-newer@example.com"
    raw_account_id = "acc_delete_schema_newer"
    _write_live_account(codex_home, "schema-newer-key", email=email, raw_account_id=raw_account_id)
    _write_backup_account(data_dir, "schema-newer-key", email=email, raw_account_id=raw_account_id)
    runner = SchemaUnsupportedRemoveCommandRunner()
    account = SimpleNamespace(
        email=email,
        chatgpt_account_id=raw_account_id,
        workspace_id=None,
        workspace_label=None,
    )
    service = CodexNeoAccountsSyncService(codex_home=codex_home, data_dir=data_dir, command_runner=runner)

    result = await service.remove_account_from_codex_home(account)

    assert result.success is True
    assert result.count == 1
    assert "local registry fallback" in result.message
    assert not (codex_home / "accounts" / "schema-newer-key.auth.json").exists()
    assert not (data_dir / "account-backups" / "schema-newer-key.auth.json").exists()


@pytest.mark.asyncio
async def test_accounts_delete_bypasses_codex_auth_remove_when_registry_schema_is_newer(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    email = "delete-schema-bypass@example.com"
    raw_account_id = "acc_delete_schema_bypass"
    _write_live_account(
        codex_home,
        "schema-bypass-key",
        email=email,
        raw_account_id=raw_account_id,
        schema_version=5,
    )
    _write_backup_account(data_dir, "schema-bypass-key", email=email, raw_account_id=raw_account_id)
    runner = UnexpectedRemoveCommandRunner()
    account = SimpleNamespace(
        email=email,
        chatgpt_account_id=raw_account_id,
        workspace_id=None,
        workspace_label=None,
    )
    service = CodexNeoAccountsSyncService(codex_home=codex_home, data_dir=data_dir, command_runner=runner)

    result = await service.remove_account_from_codex_home(account)

    assert result.success is True
    assert result.count == 1
    assert "local registry fallback" in result.message
    assert runner.calls == []
    assert not (codex_home / "accounts" / "schema-bypass-key.auth.json").exists()
    assert not (data_dir / "account-backups" / "schema-bypass-key.auth.json").exists()


@pytest.mark.asyncio
async def test_sync_all_accounts_writes_master_list_and_reconciles_both_directions(tmp_path, db_setup) -> None:
    del db_setup
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    backup_email = "backup-master-sync@example.com"
    backup_raw_account_id = "acc_backup_master_sync"
    ib_email = "codex-ib-master-sync@example.com"
    ib_raw_account_id = "acc_codex_ib_master_sync"
    _write_backup_account(data_dir, "backup-master-key", email=backup_email, raw_account_id=backup_raw_account_id)
    await _import_account_to_db(_auth_json(email=ib_email, account_id=ib_raw_account_id))
    runner = RecordingCommandRunner()
    service = CodexNeoAccountsSyncService(codex_home=codex_home, data_dir=data_dir, command_runner=runner)

    result = await service.sync_all_accounts()

    assert result.success is True
    assert generate_unique_account_id(backup_raw_account_id, backup_email) in await _account_ids()
    import_calls = [args for args, _ in runner.calls if args and args[0] == "import"]
    assert len(import_calls) == 1
    master_path = data_dir / "codexneo-master-registry.json"
    master_text = master_path.read_text(encoding="utf-8")
    master = json.loads(master_text)
    assert "secret-access" not in master_text
    assert "secret-refresh" not in master_text
    sources_by_email = {
        entry["email"]: set(entry["sources"])
        for entry in master["accounts"]
    }
    assert sources_by_email[backup_email] >= {"backup", "codex_ib"}
    assert "codex_ib" in sources_by_email[ib_email]
