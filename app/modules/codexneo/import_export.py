from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path

from app.core.config.settings import get_settings as get_app_settings
from app.core.exceptions import DashboardBadRequestError
from app.core.runtime_logging import safe_command_summary
from app.modules.codexneo.command_runner import run_codex_auth_command
from app.modules.codexneo.schemas import CodexNeoPathResponse
from app.modules.codexneo.snapshots import account_key_from_snapshot, existing_snapshot_path
from app.modules.codexneo.sync import CodexNeoAccountsSyncService

type CommandRunner = Callable[[list[str]], Awaitable[tuple[bool, str]]]
type CommandRunnerWithHome = Callable[[list[str]], Awaitable[tuple[bool, str]]]


class CodexNeoImportExportService:
    def __init__(
        self,
        *,
        codex_home: Path,
        data_dir: Path | None = None,
        command_runner: Callable[..., Awaitable[tuple[bool, str]]] | None = None,
        account_sync: CodexNeoAccountsSyncService | None = None,
    ) -> None:
        self._codex_home = codex_home.resolve()
        self._data_dir = data_dir or get_app_settings().data_dir
        self._command_runner = command_runner or run_codex_auth_command
        self._account_sync = account_sync

    async def import_file(self, path: Path | str | None) -> CodexNeoPathResponse:
        if _blank_path(path):
            return CodexNeoPathResponse(success=False, message="No import file path was provided", path=None)
        assert path is not None
        source = _resolve_user_path(path)
        if not source.is_file():
            raise DashboardBadRequestError("Import file was not found", code="codexneo_import_file_not_found")
        _validate_json_file(source)
        result = await self._run_command(["import", str(source)], success_message="Import file completed", path=source)
        if result.success and self._account_sync is not None:
            sync_result = await self._account_sync.import_auth_json_to_accounts(source.read_bytes())
            result = _with_sync_result(result, sync_result.message, success=sync_result.success)
        return result

    async def import_folder(self, path: Path | str | None) -> CodexNeoPathResponse:
        if _blank_path(path):
            return CodexNeoPathResponse(success=False, message="No import folder path was provided", path=None)
        assert path is not None
        source = _resolve_user_path(path)
        if not source.is_dir():
            raise DashboardBadRequestError("Import folder was not found", code="codexneo_import_folder_not_found")
        result = await self._run_command(
            ["import", str(source)],
            success_message="Import folder completed",
            path=source,
        )
        if result.success and self._account_sync is not None:
            sync_result = await self._account_sync.import_folder_to_accounts(source)
            result = _with_sync_result(result, sync_result.message, success=sync_result.success)
        return result

    async def export_all(self, destination: Path | str | None = None) -> CodexNeoPathResponse:
        export_dir = self._prepare_export_dir(destination, prefix="codexneo-export")
        exported, skipped = _copy_all_snapshots(
            sources=[
                self._codex_home / "accounts",
                self._data_dir / "account-backups",
            ],
            destination=export_dir,
        )
        if exported == 0:
            return CodexNeoPathResponse(
                success=False,
                message="No account auth snapshots were found to export",
                path=str(export_dir),
            )
        message = f"Exported {exported} account auth snapshot(s) to {export_dir}"
        if skipped:
            message = f"{message}; skipped {skipped} duplicate or invalid snapshot(s)"
        return CodexNeoPathResponse(success=skipped == 0, message=message, path=str(export_dir))

    async def export_selected(
        self,
        account_keys: list[str],
        destination: Path | str | None = None,
    ) -> CodexNeoPathResponse:
        keys = [_clean_key(key) for key in account_keys if _clean_key(key)]
        if not keys:
            raise DashboardBadRequestError("No accounts were selected", code="codexneo_no_accounts_selected")
        export_dir = self._prepare_export_dir(destination, prefix="codexneo-selected-export")
        source_dirs = [self._codex_home / "accounts", self._data_dir / "account-backups"]
        exported = 0
        messages: list[str] = []
        used_names: set[str] = set()
        for key in keys:
            source = _managed_auth_snapshot(source_dirs, key)
            if source is None:
                messages.append(f"Skipped {key}: managed auth snapshot was not found")
                continue
            name = _unique_name(_safe_filename(f"{key}.auth.json"), used_names)
            target = export_dir / name
            target.write_bytes(source.read_bytes())
            exported += 1
        messages.insert(0, f"Exported {exported} of {len(keys)} selected account(s) to {export_dir}")
        return CodexNeoPathResponse(success=exported == len(keys), message="; ".join(messages), path=str(export_dir))

    def _prepare_export_dir(self, destination: Path | str | None, *, prefix: str) -> Path:
        if isinstance(destination, str) and not destination.strip():
            destination = None
        if destination is not None:
            base = Path(destination).expanduser().resolve()
        else:
            base = self._data_dir
        base.mkdir(parents=True, exist_ok=True)
        export_dir = base / f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
        export_dir.mkdir()
        return export_dir

    async def _run_command(self, args: list[str], *, success_message: str, path: Path) -> CodexNeoPathResponse:
        ok, output = await self._command_runner(args, codex_home=str(self._codex_home))
        safe_output = _safe_summary(output)
        message = success_message if ok else f"Command failed: {safe_output or 'codex-auth command failed'}"
        if ok and safe_output:
            message = f"{message}: {safe_output}"
        return CodexNeoPathResponse(success=ok, message=message, path=str(path))


def _validate_json_file(path: Path) -> None:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DashboardBadRequestError("Import file must contain JSON") from exc
    if not isinstance(parsed, dict):
        raise DashboardBadRequestError("Import file must contain a JSON object")


def _blank_path(path: Path | str | None) -> bool:
    return path is None or (isinstance(path, str) and not path.strip())


def _resolve_user_path(path: Path | str) -> Path:
    return Path(path).expanduser().resolve()


def _managed_auth_snapshot(source_dirs: list[Path], account_key: str) -> Path | None:
    for directory in source_dirs:
        candidate = existing_snapshot_path(directory, account_key)
        if candidate is not None:
            return candidate
    return None


def _copy_all_snapshots(*, sources: list[Path], destination: Path) -> tuple[int, int]:
    used_keys: set[str] = set()
    used_names: set[str] = set()
    exported = 0
    skipped = 0
    for source_dir in sources:
        if not source_dir.is_dir():
            continue
        for source in sorted(source_dir.glob("*.auth.json")):
            key = account_key_from_snapshot(source).strip()
            if not key or key.lower() in used_keys:
                skipped += 1
                continue
            used_keys.add(key.lower())
            target_name = _unique_name(_safe_filename(f"{key}.auth.json"), used_names)
            (destination / target_name).write_bytes(source.read_bytes())
            exported += 1
    return exported, skipped


def _clean_key(value: str) -> str:
    return value.strip()


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "account.auth.json"


def _unique_name(value: str, used: set[str]) -> str:
    candidate = value
    stem = Path(value).stem
    suffix = "".join(Path(value).suffixes)
    index = 2
    while candidate.lower() in used:
        candidate = f"{stem}-{index}{suffix}"
        index += 1
    used.add(candidate.lower())
    return candidate


def _safe_summary(output: str) -> str:
    return safe_command_summary(output, max_length=500, fallback="")


def _with_sync_result(response: CodexNeoPathResponse, message: str, *, success: bool) -> CodexNeoPathResponse:
    return CodexNeoPathResponse(
        success=response.success and success,
        message=f"{response.message}; Accounts sync: {message}",
        path=response.path,
    )
