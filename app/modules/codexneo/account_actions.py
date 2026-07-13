from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.core.config.settings import get_settings as get_app_settings
from app.core.exceptions import DashboardBadRequestError
from app.core.runtime_logging import safe_command_summary
from app.modules.codexneo.command_runner import run_codex_auth_command
from app.modules.codexneo.locations import CodexNeoAccountLocationService
from app.modules.codexneo.schemas import CodexNeoActionResponse
from app.modules.codexneo.service import CodexRestartProvider
from app.modules.codexneo.snapshots import existing_snapshot_path, preferred_snapshot_path
from app.modules.codexneo.sync import (
    CodexNeoAccountsSyncService,
    is_codex_auth_schema_unsupported,
    is_codex_registry_schema_newer_than_supported,
)

type CommandRunner = Callable[..., Awaitable[tuple[bool, str]]]


class CodexNeoAccountActionService:
    def __init__(
        self,
        *,
        codex_home: Path,
        data_dir: Path | None = None,
        command_runner: CommandRunner | None = None,
        restart_provider: CodexRestartProvider | None = None,
        account_sync: CodexNeoAccountsSyncService | None = None,
        location_service: CodexNeoAccountLocationService | None = None,
    ) -> None:
        self._codex_home = codex_home.resolve()
        self._data_dir = data_dir or get_app_settings().data_dir
        self._command_runner = command_runner or run_codex_auth_command
        self._restart_provider = restart_provider
        self._account_sync = account_sync
        self._location_service = location_service

    async def mark_temporarily_unavailable(self, account_keys: list[str]) -> CodexNeoActionResponse:
        return self._update_metadata(
            account_keys,
            temporarily_unavailable=True,
            message="Marked account(s) as temporarily unavailable",
        )

    async def mark_available(self, account_keys: list[str]) -> CodexNeoActionResponse:
        return self._update_metadata(
            account_keys,
            temporarily_unavailable=False,
            message="Marked account(s) as available",
        )

    async def set_validity_date(self, account_keys: list[str], validity_date: str) -> CodexNeoActionResponse:
        if not re.fullmatch(r"\d{2}-\d{2}-\d{4}", validity_date.strip()):
            raise DashboardBadRequestError("Validity date must use dd-MM-yyyy", code="invalid_validity_date")
        return self._update_metadata(account_keys, validity_date=validity_date.strip(), message="Set validity date")

    async def clear_validity_date(self, account_keys: list[str]) -> CodexNeoActionResponse:
        return self._update_metadata(account_keys, validity_date="", message="Cleared validity date")

    async def switch_account(self, account_key: str, *, restart: bool = False) -> CodexNeoActionResponse:
        key = _one_key(account_key)
        response = (
            self._location_service.switch_account_locally(key)
            if self._location_service and is_codex_registry_schema_newer_than_supported(self._codex_home)
            else await self._run_command(["switch", key], success_message=f"Switched to {key}")
        )
        if not response.success and is_codex_auth_schema_unsupported(response.message) and self._location_service:
            response = self._location_service.switch_account_locally(key)
        if not restart or not response.success:
            return response
        if self._restart_provider is None:
            response.restart_attempted = True
            response.restart_succeeded = False
            response.success = False
            response.message = f"{response.message}; restart provider is not configured"
            return response
        restart_result = await self._restart_provider()
        response.restart_attempted = True
        response.restart_succeeded = restart_result.success
        response.restart_output = restart_result.message
        response.success = response.success and restart_result.success
        restart_message = (
            "Codex Desktop restarted"
            if restart_result.success
            else f"Codex restart failed: {restart_result.message}"
        )
        response.message = f"{response.message}; {restart_message}"
        return response

    async def delete_accounts(self, account_keys: list[str]) -> CodexNeoActionResponse:
        keys = _keys(account_keys)
        with tempfile.TemporaryDirectory(prefix="codexneo-delete-sync-") as tmp_dir:
            staged_codex_home = Path(tmp_dir) / ".codex"
            _stage_delete_snapshots(
                keys,
                source_dirs=[self._codex_home / "accounts", self._data_dir / "account-backups"],
                staged_codex_home=staged_codex_home,
            )
            response = (
                CodexNeoActionResponse(
                    success=True,
                    message=f"Deleted {len(keys)} account(s) with local registry fallback",
                )
                if self._location_service and is_codex_registry_schema_newer_than_supported(self._codex_home)
                else await self._remove_accounts(keys)
            )
            if not response.success and is_codex_auth_schema_unsupported(response.message) and self._location_service:
                response = CodexNeoActionResponse(
                    success=True,
                    message=f"Deleted {len(keys)} account(s) with local registry fallback",
                )
            if response.success and self._account_sync is not None:
                sync_result = await self._account_sync.delete_codex_keys_from_accounts(
                    keys,
                    codex_home=staged_codex_home,
                )
                response.success = response.success and sync_result.success
                response.message = f"{response.message}; Accounts sync: {sync_result.message}"
            if response.success and self._location_service is not None:
                location_result = self._location_service.delete_everywhere(keys)
                response.success = response.success and location_result.success
                response.message = f"{response.message}; Locations: {location_result.message}"
            return response

    def _update_metadata(
        self,
        account_keys: list[str],
        *,
        temporarily_unavailable: bool | None = None,
        validity_date: str | None = None,
        message: str,
    ) -> CodexNeoActionResponse:
        keys = _keys(account_keys)
        path = self._data_dir / "codexneo-account-metadata.json"
        data = _read_json(path)
        accounts = data.setdefault("accounts", {})
        data["schema_version"] = 1
        for key in keys:
            entry = accounts.setdefault(key, {})
            if temporarily_unavailable is not None:
                entry["temporarily_unavailable"] = temporarily_unavailable
            if validity_date is not None:
                entry["validity_date"] = validity_date
            if not entry.get("temporarily_unavailable") and not entry.get("validity_date"):
                accounts.pop(key, None)
        _write_json_atomic(path, data)
        return CodexNeoActionResponse(success=True, message=f"{message}. Updated {len(keys)} account(s).")

    async def _run_command(self, args: list[str], *, success_message: str) -> CodexNeoActionResponse:
        ok, output = await self._command_runner(args, codex_home=str(self._codex_home))
        summary = _safe_summary(output)
        return CodexNeoActionResponse(
            success=ok,
            message=success_message if ok else f"Command failed: {summary or 'codex-auth command failed'}",
        )

    async def _remove_accounts(self, keys: list[str]) -> CodexNeoActionResponse:
        for key in keys:
            response = await self._run_command(["remove", key], success_message=f"Deleted {key}")
            if not response.success:
                response.message = f"Delete stopped at {key}: {response.message}"
                return response
        return CodexNeoActionResponse(success=True, message=f"Deleted {len(keys)} account(s)")


def _keys(account_keys: list[str]) -> list[str]:
    keys = [key.strip() for key in account_keys if key.strip()]
    if not keys:
        raise DashboardBadRequestError("No accounts were selected", code="codexneo_no_accounts_selected")
    return keys


def _one_key(account_key: str) -> str:
    return _keys([account_key])[0]


def _stage_delete_snapshots(keys: list[str], *, source_dirs: list[Path], staged_codex_home: Path) -> None:
    staged_accounts = staged_codex_home / "accounts"
    staged_accounts.mkdir(parents=True, exist_ok=True)
    for key in keys:
        for source_dir in source_dirs:
            source = existing_snapshot_path(source_dir, key)
            if source is not None:
                preferred_snapshot_path(staged_accounts, key).write_bytes(source.read_bytes())
                break


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "accounts": {}}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"schema_version": 1, "accounts": {}}
    return loaded if isinstance(loaded, dict) else {"schema_version": 1, "accounts": {}}


def _write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _safe_summary(output: str) -> str:
    return safe_command_summary(output, max_length=500, fallback="")
