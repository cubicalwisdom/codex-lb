from __future__ import annotations

import base64
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.codexneo.account_actions import CodexNeoAccountActionService
from app.modules.codexneo.import_export import CodexNeoImportExportService
from app.modules.codexneo.locations import CodexNeoAccountLocationService
from app.modules.codexneo.service import CodexRestartResult

pytestmark = pytest.mark.unit


class FakeCommandRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str]] = []

    async def __call__(self, args: list[str], *, codex_home: str) -> tuple[bool, str]:
        self.calls.append((args, codex_home))
        return True, "command ok"


class RemovingCommandRunner(FakeCommandRunner):
    async def __call__(self, args: list[str], *, codex_home: str) -> tuple[bool, str]:
        self.calls.append((args, codex_home))
        if args and args[0] == "remove":
            for key in args[1:]:
                try:
                    (Path(codex_home) / "accounts" / f"{key}.auth.json").unlink()
                except FileNotFoundError:
                    pass
        return True, "command ok"


class FailingRemoveCommandRunner(FakeCommandRunner):
    async def __call__(self, args: list[str], *, codex_home: str) -> tuple[bool, str]:
        self.calls.append((args, codex_home))
        if args and args[0] == "remove":
            return False, "remove failed"
        return True, "command ok"


class StrictSingleRemoveCommandRunner(FakeCommandRunner):
    async def __call__(self, args: list[str], *, codex_home: str) -> tuple[bool, str]:
        self.calls.append((args, codex_home))
        if args and args[0] == "remove" and len(args) != 2:
            return False, "error: unexpected extra selector for 'remove'"
        if args and args[0] == "remove":
            key = args[1]
            try:
                (Path(codex_home) / "accounts" / f"{key}.auth.json").unlink()
            except FileNotFoundError:
                pass
        return True, "command ok"


class SchemaUnsupportedRemoveCommandRunner(FakeCommandRunner):
    async def __call__(self, args: list[str], *, codex_home: str) -> tuple[bool, str]:
        self.calls.append((args, codex_home))
        if args and args[0] == "remove":
            return False, "error: registry schema version 5 is newer than this codex-auth binary supports (max 3)"
        return True, "command ok"


class SchemaUnsupportedSwitchCommandRunner(FakeCommandRunner):
    async def __call__(self, args: list[str], *, codex_home: str) -> tuple[bool, str]:
        self.calls.append((args, codex_home))
        if args and args[0] == "switch":
            return False, "error: registry schema version 5 is newer than this codex-auth binary supports (max 3)"
        return True, "command ok"


class UnexpectedSwitchCommandRunner(FakeCommandRunner):
    async def __call__(self, args: list[str], *, codex_home: str) -> tuple[bool, str]:
        self.calls.append((args, codex_home))
        if args and args[0] == "switch":
            return False, "switch should not be called for unsupported registry schema"
        return True, "command ok"


class UnexpectedRemoveCommandRunner(FakeCommandRunner):
    async def __call__(self, args: list[str], *, codex_home: str) -> tuple[bool, str]:
        self.calls.append((args, codex_home))
        if args and args[0] == "remove":
            return False, "remove should not be called for unsupported registry schema"
        return True, "command ok"


class FakeAccountSync:
    def __init__(self) -> None:
        self.imported: list[bytes] = []
        self.deleted_keys: list[tuple[str, ...]] = []
        self.snapshot_presence: list[bool] = []

    async def import_auth_json_to_accounts(self, raw: bytes):
        self.imported.append(raw)
        return SimpleNamespace(success=True, message="synced 1 account")

    async def delete_codex_keys_from_accounts(self, account_keys: list[str], *, codex_home):
        del codex_home
        self.deleted_keys.append(tuple(account_keys))
        return SimpleNamespace(success=True, message=f"deleted {len(account_keys)} account(s)")


class SnapshotCheckingAccountSync(FakeAccountSync):
    async def delete_codex_keys_from_accounts(self, account_keys: list[str], *, codex_home):
        self.deleted_keys.append(tuple(account_keys))
        self.snapshot_presence.extend(
            (Path(codex_home) / "accounts" / f"{key}.auth.json").is_file() for key in account_keys
        )
        return SimpleNamespace(success=all(self.snapshot_presence), message=f"deleted {len(account_keys)} account(s)")


def _encode_jwt(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    return f"header.{body}.sig"


def _auth_json(email: str = "a@test", account_id: str = "acct-1") -> dict:
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


def _snapshot_filename(account_key: str) -> str:
    encoded = base64.urlsafe_b64encode(account_key.encode("utf-8")).rstrip(b"=").decode("ascii")
    return f"{encoded}.auth.json"


def _write_registry(codex_home, account_key: str = "acct-1") -> None:
    accounts = codex_home / "accounts"
    accounts.mkdir(parents=True)
    (accounts / "registry.json").write_text(
        json.dumps({"active_account_key": account_key, "accounts": [{"account_key": account_key, "email": "a@test"}]}),
        encoding="utf-8",
    )
    (accounts / f"{account_key}.auth.json").write_text(
        json.dumps(_auth_json(account_id=account_key)),
        encoding="utf-8",
    )


def _write_registry_entries(codex_home, entries: list[tuple[str, str]], *, schema_version: int | None = None) -> None:
    accounts = codex_home / "accounts"
    accounts.mkdir(parents=True, exist_ok=True)
    registry_accounts = []
    for account_key, email in entries:
        registry_accounts.append({"account_key": account_key, "email": email})
        (accounts / f"{account_key}.auth.json").write_text(
            json.dumps(_auth_json(email=email, account_id=account_key)),
            encoding="utf-8",
        )
    registry = {"active_account_key": entries[0][0], "accounts": registry_accounts}
    if schema_version is not None:
        registry["schema_version"] = schema_version
    (accounts / "registry.json").write_text(json.dumps(registry), encoding="utf-8")


def _write_backup_entries(data_dir, entries: list[tuple[str, str]]) -> None:
    backups = data_dir / "account-backups"
    backups.mkdir(parents=True, exist_ok=True)
    registry_accounts = []
    for account_key, email in entries:
        registry_accounts.append({"account_key": account_key, "email": email})
        (backups / f"{account_key}.auth.json").write_text(
            json.dumps(_auth_json(email=email, account_id=account_key)),
            encoding="utf-8",
        )
    (backups / "backup-registry.json").write_text(json.dumps({"accounts": registry_accounts}), encoding="utf-8")


@pytest.mark.asyncio
async def test_import_file_routes_to_codex_auth_command_with_selected_home(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    snapshot = tmp_path / "snapshot.auth.json"
    snapshot.write_text(json.dumps({"tokens": {"access_token": "secret", "account_id": "acct-1"}}), encoding="utf-8")
    runner = FakeCommandRunner()
    service = CodexNeoImportExportService(codex_home=codex_home, data_dir=tmp_path / "data", command_runner=runner)

    result = await service.import_file(snapshot)

    assert result.success is True
    assert runner.calls == [(["import", str(snapshot.resolve())], str(codex_home.resolve()))]
    assert "secret" not in result.message


@pytest.mark.asyncio
async def test_import_file_syncs_supported_auth_snapshot_to_accounts_database(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    snapshot = tmp_path / "snapshot.auth.json"
    snapshot.write_text(json.dumps(_auth_json()), encoding="utf-8")
    runner = FakeCommandRunner()
    sync = FakeAccountSync()
    service = CodexNeoImportExportService(
        codex_home=codex_home,
        data_dir=tmp_path / "data",
        command_runner=runner,
        account_sync=sync,
    )

    result = await service.import_file(snapshot)

    assert result.success is True
    assert sync.imported == [snapshot.read_bytes()]
    assert "secret-access" not in result.message
    assert "Accounts sync" in result.message


@pytest.mark.asyncio
async def test_import_file_empty_path_returns_safe_failure_without_running_picker(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    runner = FakeCommandRunner()
    service = CodexNeoImportExportService(
        codex_home=codex_home,
        data_dir=tmp_path / "data",
        command_runner=runner,
    )

    result = await service.import_file("")

    assert result.success is False
    assert result.message == "No import file path was provided"
    assert runner.calls == []


@pytest.mark.asyncio
async def test_import_folder_empty_path_is_safe_and_export_all_uses_default_directory(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    runner = FakeCommandRunner()
    service = CodexNeoImportExportService(
        codex_home=codex_home,
        data_dir=tmp_path / "data",
        command_runner=runner,
    )

    import_result = await service.import_folder("")
    export_result = await service.export_all("")

    assert import_result.success is False
    assert import_result.message == "No import folder path was provided"
    assert export_result.success is False
    assert export_result.message == "No account auth snapshots were found to export"
    assert "codexneo-export-" in export_result.path
    assert runner.calls == []


@pytest.mark.asyncio
async def test_export_all_uses_timestamped_directory_and_selected_export_copies_safe_files(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    _write_registry(codex_home)
    data_dir = tmp_path / "data"
    backup_dir = data_dir / "account-backups"
    backup_dir.mkdir(parents=True)
    (backup_dir / "backup-registry.json").write_text(
        json.dumps({"accounts": [{"account_key": "acct-2", "email": "backup@test"}]}),
        encoding="utf-8",
    )
    (backup_dir / "acct-2.auth.json").write_text(
        json.dumps(_auth_json(email="backup@test", account_id="acct-2")),
        encoding="utf-8",
    )
    runner = FakeCommandRunner()
    service = CodexNeoImportExportService(codex_home=codex_home, data_dir=data_dir, command_runner=runner)

    all_result = await service.export_all()
    selected_result = await service.export_selected(["acct-1", "acct-2"])

    assert all_result.success is True
    assert "codexneo-export-" in all_result.path
    exported_files = sorted(path.name for path in Path(all_result.path).glob("*.auth.json"))
    assert exported_files == ["acct-1.auth.json", "acct-2.auth.json"]
    assert runner.calls == []
    assert selected_result.success is True
    selected_exported_files = list(data_dir.glob("codexneo-selected-export-*/*.auth.json"))
    assert sorted(path.name for path in selected_exported_files) == ["acct-1.auth.json", "acct-2.auth.json"]
    assert "secret" not in selected_result.message


@pytest.mark.asyncio
async def test_export_selected_finds_codex_auth_encoded_snapshot_filename(tmp_path) -> None:
    account_key = "user-live-key::20658dfd-4384-4993-acab-ad195ad94e79"
    codex_home = tmp_path / ".codex"
    accounts = codex_home / "accounts"
    accounts.mkdir(parents=True)
    (accounts / "registry.json").write_text(
        json.dumps({"active_account_key": account_key, "accounts": [{"account_key": account_key}]}),
        encoding="utf-8",
    )
    (accounts / _snapshot_filename(account_key)).write_text(
        json.dumps(_auth_json(email="encoded@test", account_id="20658dfd-4384-4993-acab-ad195ad94e79")),
        encoding="utf-8",
    )
    data_dir = tmp_path / "data"
    service = CodexNeoImportExportService(codex_home=codex_home, data_dir=data_dir, command_runner=FakeCommandRunner())

    result = await service.export_selected([account_key])

    assert result.success is True
    exported_files = list(data_dir.glob("codexneo-selected-export-*/*.auth.json"))
    assert len(exported_files) == 1
    assert "secret" not in result.message


@pytest.mark.asyncio
async def test_account_metadata_switch_delete_and_restart_actions_use_safe_stores(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    _write_registry(codex_home)
    runner = FakeCommandRunner()
    restart_calls = 0

    async def restart_provider() -> CodexRestartResult:
        nonlocal restart_calls
        restart_calls += 1
        return CodexRestartResult(success=True, message="restart ok")

    service = CodexNeoAccountActionService(
        codex_home=codex_home,
        data_dir=tmp_path / "data",
        command_runner=runner,
        restart_provider=restart_provider,
    )

    unavailable = await service.mark_temporarily_unavailable(["acct-1"])
    validity = await service.set_validity_date(["acct-1"], "30-06-2026")
    switched = await service.switch_account("acct-1", restart=True)
    deleted = await service.delete_accounts(["acct-1"])

    assert unavailable.success is True
    assert validity.success is True
    metadata = json.loads((tmp_path / "data" / "codexneo-account-metadata.json").read_text(encoding="utf-8"))
    assert metadata["accounts"]["acct-1"]["temporarily_unavailable"] is True
    assert metadata["accounts"]["acct-1"]["validity_date"] == "30-06-2026"
    assert runner.calls[-2:] == [
        (["switch", "acct-1"], str(codex_home.resolve())),
        (["remove", "acct-1"], str(codex_home.resolve())),
    ]
    assert switched.restart_attempted is True
    assert switched.restart_succeeded is True
    assert restart_calls == 1
    assert deleted.success is True


@pytest.mark.asyncio
async def test_switch_account_uses_local_fallback_for_unsupported_runtime_registry_schema(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    _write_registry_entries(codex_home, [("acct-1", "one@test"), ("acct-2", "two@test")], schema_version=4)
    runner = SchemaUnsupportedSwitchCommandRunner()
    service = CodexNeoAccountActionService(
        codex_home=codex_home,
        data_dir=tmp_path / "data",
        command_runner=runner,
        location_service=CodexNeoAccountLocationService(codex_home=codex_home, data_dir=tmp_path / "data"),
    )

    result = await service.switch_account("acct-2")

    registry = json.loads((codex_home / "accounts" / "registry.json").read_text(encoding="utf-8"))
    root_auth = json.loads((codex_home / "auth.json").read_text(encoding="utf-8"))
    assert result.success is True
    assert "local registry fallback" in result.message
    assert runner.calls == [(["switch", "acct-2"], str(codex_home.resolve()))]
    assert registry["active_account_key"] == "acct-2"
    assert root_auth["tokens"]["accountId"] == "acct-2"


@pytest.mark.asyncio
async def test_switch_and_restart_bypasses_command_when_configured_registry_schema_is_unsupported(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    _write_registry_entries(codex_home, [("acct-1", "one@test"), ("acct-2", "two@test")], schema_version=5)
    restart_calls = 0

    async def restart_provider() -> CodexRestartResult:
        nonlocal restart_calls
        restart_calls += 1
        return CodexRestartResult(success=True, message="restart ok")

    runner = UnexpectedSwitchCommandRunner()
    service = CodexNeoAccountActionService(
        codex_home=codex_home,
        data_dir=tmp_path / "data",
        command_runner=runner,
        restart_provider=restart_provider,
        location_service=CodexNeoAccountLocationService(codex_home=codex_home, data_dir=tmp_path / "data"),
    )

    result = await service.switch_account("acct-2", restart=True)

    registry = json.loads((codex_home / "accounts" / "registry.json").read_text(encoding="utf-8"))
    assert result.success is True
    assert result.restart_attempted is True
    assert result.restart_succeeded is True
    assert restart_calls == 1
    assert runner.calls == []
    assert registry["active_account_key"] == "acct-2"
    assert (codex_home / "auth.json").is_file()


@pytest.mark.asyncio
async def test_delete_accounts_syncs_removed_codex_keys_to_accounts_database(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    _write_registry(codex_home)
    runner = FakeCommandRunner()
    sync = FakeAccountSync()
    service = CodexNeoAccountActionService(
        codex_home=codex_home,
        data_dir=tmp_path / "data",
        command_runner=runner,
        account_sync=sync,
    )

    result = await service.delete_accounts(["acct-1"])

    assert result.success is True
    assert sync.deleted_keys == [("acct-1",)]
    assert "Accounts sync" in result.message


@pytest.mark.asyncio
async def test_delete_accounts_syncs_accounts_before_codex_auth_remove_deletes_snapshots(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    _write_registry(codex_home)
    runner = RemovingCommandRunner()
    sync = SnapshotCheckingAccountSync()
    service = CodexNeoAccountActionService(
        codex_home=codex_home,
        data_dir=tmp_path / "data",
        command_runner=runner,
        account_sync=sync,
    )

    result = await service.delete_accounts(["acct-1"])

    assert result.success is True
    assert sync.deleted_keys == [("acct-1",)]
    assert sync.snapshot_presence == [True]
    assert runner.calls == [(["remove", "acct-1"], str(codex_home.resolve()))]


@pytest.mark.asyncio
async def test_delete_accounts_does_not_sync_accounts_when_codex_auth_remove_fails(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    _write_registry(codex_home)
    runner = FailingRemoveCommandRunner()
    sync = SnapshotCheckingAccountSync()
    service = CodexNeoAccountActionService(
        codex_home=codex_home,
        data_dir=tmp_path / "data",
        command_runner=runner,
        account_sync=sync,
    )

    result = await service.delete_accounts(["acct-1"])

    assert result.success is False
    assert sync.deleted_keys == []
    assert (codex_home / "accounts" / "acct-1.auth.json").is_file()


@pytest.mark.asyncio
async def test_delete_accounts_runs_single_remove_per_selected_account_and_deletes_locations(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    entries = [("acct-1", "one@test"), ("acct-2", "two@test")]
    _write_registry_entries(codex_home, entries)
    _write_backup_entries(data_dir, entries)
    runner = StrictSingleRemoveCommandRunner()
    sync = FakeAccountSync()
    service = CodexNeoAccountActionService(
        codex_home=codex_home,
        data_dir=data_dir,
        command_runner=runner,
        account_sync=sync,
        location_service=CodexNeoAccountLocationService(codex_home=codex_home, data_dir=data_dir),
    )

    result = await service.delete_accounts(["acct-1", "acct-2"])

    assert result.success is True
    assert runner.calls == [
        (["remove", "acct-1"], str(codex_home.resolve())),
        (["remove", "acct-2"], str(codex_home.resolve())),
    ]
    assert sync.deleted_keys == [("acct-1", "acct-2")]
    assert not (codex_home / "accounts" / "acct-1.auth.json").exists()
    assert not (codex_home / "accounts" / "acct-2.auth.json").exists()
    assert not (data_dir / "account-backups" / "acct-1.auth.json").exists()
    assert not (data_dir / "account-backups" / "acct-2.auth.json").exists()


@pytest.mark.asyncio
async def test_delete_accounts_uses_local_remove_when_codex_auth_schema_is_unsupported(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    entries = [("acct-1", "one@test")]
    _write_registry_entries(codex_home, entries)
    _write_backup_entries(data_dir, entries)
    runner = SchemaUnsupportedRemoveCommandRunner()
    sync = FakeAccountSync()
    service = CodexNeoAccountActionService(
        codex_home=codex_home,
        data_dir=data_dir,
        command_runner=runner,
        account_sync=sync,
        location_service=CodexNeoAccountLocationService(codex_home=codex_home, data_dir=data_dir),
    )

    result = await service.delete_accounts(["acct-1"])

    assert result.success is True
    assert "local registry fallback" in result.message
    assert sync.deleted_keys == [("acct-1",)]
    assert not (codex_home / "accounts" / "acct-1.auth.json").exists()
    assert not (data_dir / "account-backups" / "acct-1.auth.json").exists()


@pytest.mark.asyncio
async def test_delete_accounts_bypasses_codex_auth_remove_when_registry_schema_is_newer(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    data_dir = tmp_path / "data"
    entries = [("acct-1", "one@test")]
    _write_registry_entries(codex_home, entries, schema_version=5)
    _write_backup_entries(data_dir, entries)
    runner = UnexpectedRemoveCommandRunner()
    sync = FakeAccountSync()
    service = CodexNeoAccountActionService(
        codex_home=codex_home,
        data_dir=data_dir,
        command_runner=runner,
        account_sync=sync,
        location_service=CodexNeoAccountLocationService(codex_home=codex_home, data_dir=data_dir),
    )

    result = await service.delete_accounts(["acct-1"])

    assert result.success is True
    assert "local registry fallback" in result.message
    assert runner.calls == []
    assert sync.deleted_keys == [("acct-1",)]
    assert not (codex_home / "accounts" / "acct-1.auth.json").exists()
    assert not (data_dir / "account-backups" / "acct-1.auth.json").exists()
