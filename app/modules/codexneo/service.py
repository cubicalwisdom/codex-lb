from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import aiohttp

from app.core.config.settings import get_settings as get_app_settings
from app.core.crypto import TokenEncryptor
from app.core.exceptions import DashboardBadRequestError
from app.modules.codexneo.activity_log import CodexNeoActivityLogService
from app.modules.codexneo.home import resolve_configured_codex_home
from app.modules.codexneo.schemas import CodexNeoActionResponse, CodexNeoSettingsResponse
from app.modules.codexneo.sync import CodexNeoAccountsSyncService

DEFAULT_CODEX_API_BASE_URL = "http://127.0.0.1:2455/v1"
DEFAULT_CODEXGO_API_BASE_URL = "https://codexgo.eu/api/codex-auth"
MIN_REFRESH_INTERVAL_MINUTES = 5
MAX_REFRESH_INTERVAL_MINUTES = 1440
MIN_CODEX_HOME_REFRESH_INTERVAL_SECONDS = 5
MAX_CODEX_HOME_REFRESH_INTERVAL_SECONDS = 3600
CONFIG_BEGIN_MARKER = "# BEGIN CodexNeo provider"
CONFIG_END_MARKER = "# END CodexNeo provider"
CONFIG_LEGACY_BEGIN_MARKER = "# BEGIN RC Codex Auth Switcher provider"
CONFIG_LEGACY_END_MARKER = "# END RC Codex Auth Switcher provider"
CONFIG_LEGACY_PROVIDER_ID = "rc_switcher"
CONFIG_ORIGINAL_BACKUP_SUFFIX = "codexneo-original"
CONFIG_OPERATION_BACKUP_LABEL = "codexneo-backup"
CONFIG_OPERATION_BACKUP_KEEP_LATEST = 10
CONFIG_OPERATION_BACKUP_MIN_KEEP = 3
CONFIG_OPERATION_BACKUP_MAX_AGE_DAYS = 14

type CodexGoProvider = Callable[[str, str], Awaitable[dict[str, Any]]]
type CodexRestartProvider = Callable[[], Awaitable["CodexRestartResult"]]


class CodexGoAction(StrEnum):
    USE = "use"
    REFRESH = "refresh"


@dataclass(frozen=True)
class CodexRestartResult:
    success: bool
    message: str


def default_codex_home() -> Path:
    return Path.home() / ".codex"


def default_settings_path() -> Path:
    return get_app_settings().data_dir / "codexneo-settings.json"


def normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise DashboardBadRequestError("URL must be an absolute http(s) URL", code="invalid_codexneo_url")
    return normalized


def normalize_codexgo_provider_base_url(value: str) -> str:
    normalized = normalize_base_url(value)
    lowered = normalized.lower()
    for suffix in ("/use", "/refresh"):
        if lowered.endswith(suffix):
            return normalized[: -len(suffix)].rstrip("/")
    return normalized


def _clamp_refresh_interval(value: int) -> int:
    return max(MIN_REFRESH_INTERVAL_MINUTES, min(MAX_REFRESH_INTERVAL_MINUTES, int(value)))


def _safe_refresh_interval(value: Any) -> int:
    try:
        return _clamp_refresh_interval(int(value))
    except (TypeError, ValueError):
        return 30


def _clamp_codex_home_refresh_interval_seconds(value: int) -> int:
    return max(
        MIN_CODEX_HOME_REFRESH_INTERVAL_SECONDS,
        min(MAX_CODEX_HOME_REFRESH_INTERVAL_SECONDS, int(value)),
    )


def _safe_codex_home_refresh_interval_seconds(value: Any) -> int:
    try:
        return _clamp_codex_home_refresh_interval_seconds(int(value))
    except (TypeError, ValueError):
        return 30


class CodexNeoService:
    def __init__(
        self,
        *,
        settings_path: Path | None = None,
        codex_home: Path | None = None,
        encryptor: TokenEncryptor | None = None,
        codexgo_provider: CodexGoProvider | None = None,
        codex_restart_provider: CodexRestartProvider | None = None,
        activity_log_service: CodexNeoActivityLogService | None = None,
        account_sync: CodexNeoAccountsSyncService | None = None,
    ) -> None:
        self._settings_path = settings_path or default_settings_path()
        self._codex_home = (codex_home or resolve_configured_codex_home(settings_path=self._settings_path)).resolve()
        self._encryptor = encryptor or TokenEncryptor()
        self._codexgo_provider = codexgo_provider or _post_codexgo_provider
        self._codex_restart_provider = codex_restart_provider or restart_codex_desktop
        self._activity_log_service = activity_log_service or CodexNeoActivityLogService()
        self._account_sync = account_sync

    @property
    def codex_home(self) -> Path:
        return self._codex_home

    async def get_settings(self) -> CodexNeoSettingsResponse:
        data = self._read_settings_data()
        return self._settings_response(data)

    async def update_settings(
        self,
        *,
        codex_api_base_url: str | None = None,
        codexgo_api_base_url: str | None = None,
        codexgo_auto_refresh_enabled: bool | None = None,
        codexgo_auto_refresh_interval_minutes: int | None = None,
        openai_activity_log_enabled: bool | None = None,
        management_activity_log_enabled: bool | None = None,
        codex_home_auto_refresh_enabled: bool | None = None,
        codex_home_auto_refresh_interval_seconds: int | None = None,
        codex_home_auto_sync_enabled: bool | None = None,
        minimize_to_tray_enabled: bool | None = None,
        buyer_token: str | None = None,
        clear_buyer_token: bool = False,
    ) -> CodexNeoSettingsResponse:
        data = self._read_settings_data()
        if codex_api_base_url is not None:
            data["codex_api_base_url"] = normalize_base_url(codex_api_base_url)
        if codexgo_api_base_url is not None:
            data["codexgo_api_base_url"] = normalize_codexgo_provider_base_url(codexgo_api_base_url)
        if codexgo_auto_refresh_enabled is not None:
            data["codexgo_auto_refresh_enabled"] = bool(codexgo_auto_refresh_enabled)
        if codexgo_auto_refresh_interval_minutes is not None:
            data["codexgo_auto_refresh_interval_minutes"] = _clamp_refresh_interval(
                codexgo_auto_refresh_interval_minutes
            )
        if openai_activity_log_enabled is not None:
            data["openai_activity_log_enabled"] = bool(openai_activity_log_enabled)
        if management_activity_log_enabled is not None:
            data["management_activity_log_enabled"] = bool(management_activity_log_enabled)
        if codex_home_auto_refresh_enabled is not None:
            data["codex_home_auto_refresh_enabled"] = bool(codex_home_auto_refresh_enabled)
        if codex_home_auto_refresh_interval_seconds is not None:
            data["codex_home_auto_refresh_interval_seconds"] = _clamp_codex_home_refresh_interval_seconds(
                codex_home_auto_refresh_interval_seconds
            )
        if codex_home_auto_sync_enabled is not None:
            data["codex_home_auto_sync_enabled"] = bool(codex_home_auto_sync_enabled)
        if minimize_to_tray_enabled is not None:
            data["minimize_to_tray_enabled"] = bool(minimize_to_tray_enabled)
        if clear_buyer_token:
            data["buyer_token_encrypted"] = None
        elif buyer_token is not None:
            token = buyer_token.strip()
            if token:
                data["buyer_token_encrypted"] = self._encryptor.encrypt(token).decode("utf-8")
        self._write_settings_data(data)
        return self._settings_response(data)

    async def test_api_provider(self, codex_api_base_url: str | None = None) -> CodexNeoActionResponse:
        base_url = normalize_base_url(codex_api_base_url or self._read_settings_data()["codex_api_base_url"])
        test_url = f"{base_url}/models"
        timeout = aiohttp.ClientTimeout(total=8)
        try:
            async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
                async with session.get(test_url) as response:
                    if response.status < 400:
                        return CodexNeoActionResponse(success=True, message=f"Codex API reachable at {base_url}")
                    body = await response.text()
                    return CodexNeoActionResponse(
                        success=False,
                        message=f"Codex API returned HTTP {response.status}: {body[:200]}",
                    )
        except Exception as exc:
            return CodexNeoActionResponse(success=False, message=f"Codex API test failed: {exc}")

    async def set_api_provider(self, codex_api_base_url: str | None = None) -> CodexNeoActionResponse:
        base_url = normalize_base_url(codex_api_base_url or self._read_settings_data()["codex_api_base_url"])
        config_path = self._codex_home / "config.toml"
        current = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        _ensure_original_config_backup(config_path, current)
        updated = _apply_provider_config(current, base_url=base_url)
        backup_path = _backup_file(config_path, CONFIG_OPERATION_BACKUP_LABEL) if config_path.exists() else None
        _write_text_atomic(config_path, updated)
        _prune_config_operation_backups(config_path)
        _verify_provider_config(config_path, base_url=base_url)
        await self.update_settings(codex_api_base_url=base_url)
        response = CodexNeoActionResponse(
            success=True,
            message=f"Codex API provider set to {base_url}; restart Codex manually to apply",
            config_path=str(config_path),
            backup_path=str(backup_path) if backup_path else None,
        )
        return response

    async def revert_api_provider(self) -> CodexNeoActionResponse:
        config_path = self._codex_home / "config.toml"
        current = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        original_backup_path = _original_config_backup_path(config_path)
        updated = (
            original_backup_path.read_text(encoding="utf-8")
            if original_backup_path.exists()
            else _remove_provider_config(current)
        )
        backup_path = _backup_file(config_path, CONFIG_OPERATION_BACKUP_LABEL) if config_path.exists() else None
        _write_text_atomic(config_path, updated)
        _prune_config_operation_backups(config_path)
        _verify_provider_reverted(config_path)
        response = CodexNeoActionResponse(
            success=True,
            message="CodexNeo provider override reverted; restart Codex manually to apply",
            config_path=str(config_path),
            backup_path=str(backup_path) if backup_path else None,
        )
        return response

    async def apply_codexgo_auth(self, action: CodexGoAction) -> CodexNeoActionResponse:
        data = self._read_settings_data()
        token = self._decrypt_buyer_token(data)
        if not token:
            raise DashboardBadRequestError("Buyer token is required", code="codexneo_buyer_token_required")
        base_url = normalize_codexgo_provider_base_url(data["codexgo_api_base_url"])
        response = await self._codexgo_provider(f"{base_url}/{action.value}", token)
        _validate_auth_json(response)
        auth_path = self._codex_home / "auth.json"
        backup_path = _backup_file(auth_path, "codexgo-backup") if auth_path.exists() else None
        _write_text_atomic(auth_path, json.dumps(response, indent=2, sort_keys=True) + "\n")
        action_response = CodexNeoActionResponse(
            success=True,
            message=f"CodexGO auth {action.value} applied",
            auth_path=str(auth_path),
            backup_path=str(backup_path) if backup_path else None,
        )
        if self._account_sync is not None:
            sync_result = await self._account_sync.sync_codex_home_to_accounts()
            action_response.success = action_response.success and sync_result.success
            action_response.message = f"{action_response.message}; Accounts sync: {sync_result.message}"
        return action_response

    async def restart_codex_app(self) -> CodexNeoActionResponse:
        restart_result = await self._codex_restart_provider()
        message = (
            "Codex Desktop restarted"
            if restart_result.success
            else f"Codex restart failed: {restart_result.message}"
        )
        return CodexNeoActionResponse(
            success=restart_result.success,
            message=message,
            restart_attempted=True,
            restart_succeeded=restart_result.success,
            restart_output=restart_result.message,
        )

    def _read_settings_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "codex_api_base_url": DEFAULT_CODEX_API_BASE_URL,
            "codexgo_api_base_url": DEFAULT_CODEXGO_API_BASE_URL,
            "codexgo_auto_refresh_enabled": False,
            "codexgo_auto_refresh_interval_minutes": 30,
            "openai_activity_log_enabled": False,
            "management_activity_log_enabled": False,
            "codex_home_auto_refresh_enabled": False,
            "codex_home_auto_refresh_interval_seconds": 30,
            "codex_home_auto_sync_enabled": False,
            "minimize_to_tray_enabled": False,
            "codex_home_path": None,
            "buyer_token_encrypted": None,
        }
        if self._settings_path.exists():
            try:
                loaded = json.loads(self._settings_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise DashboardBadRequestError("CodexNeo settings file is invalid JSON") from exc
            if isinstance(loaded, dict):
                data.update(loaded)
        data["codex_api_base_url"] = normalize_base_url(str(data["codex_api_base_url"]))
        data["codexgo_api_base_url"] = normalize_codexgo_provider_base_url(str(data["codexgo_api_base_url"]))
        data["codexgo_auto_refresh_enabled"] = bool(data["codexgo_auto_refresh_enabled"])
        data["codexgo_auto_refresh_interval_minutes"] = _safe_refresh_interval(
            data["codexgo_auto_refresh_interval_minutes"]
        )
        data["openai_activity_log_enabled"] = bool(data["openai_activity_log_enabled"])
        data["management_activity_log_enabled"] = bool(data["management_activity_log_enabled"])
        data["codex_home_auto_refresh_enabled"] = bool(data["codex_home_auto_refresh_enabled"])
        data["codex_home_auto_refresh_interval_seconds"] = _safe_codex_home_refresh_interval_seconds(
            data["codex_home_auto_refresh_interval_seconds"]
        )
        data["codex_home_auto_sync_enabled"] = bool(data["codex_home_auto_sync_enabled"])
        data["minimize_to_tray_enabled"] = bool(data["minimize_to_tray_enabled"])
        if data.get("buyer_token_encrypted") is not None:
            data["buyer_token_encrypted"] = str(data["buyer_token_encrypted"])
        return data

    def _write_settings_data(self, data: dict[str, Any]) -> None:
        persisted = {
            "codex_api_base_url": data["codex_api_base_url"],
            "codexgo_api_base_url": data["codexgo_api_base_url"],
            "codexgo_auto_refresh_enabled": data["codexgo_auto_refresh_enabled"],
            "codexgo_auto_refresh_interval_minutes": data["codexgo_auto_refresh_interval_minutes"],
            "openai_activity_log_enabled": data["openai_activity_log_enabled"],
            "management_activity_log_enabled": data["management_activity_log_enabled"],
            "codex_home_auto_refresh_enabled": data["codex_home_auto_refresh_enabled"],
            "codex_home_auto_refresh_interval_seconds": data["codex_home_auto_refresh_interval_seconds"],
            "codex_home_auto_sync_enabled": data["codex_home_auto_sync_enabled"],
            "minimize_to_tray_enabled": data["minimize_to_tray_enabled"],
            "codex_home_path": data.get("codex_home_path"),
            "buyer_token_encrypted": data.get("buyer_token_encrypted"),
        }
        _write_text_atomic(self._settings_path, json.dumps(persisted, indent=2, sort_keys=True) + "\n")

    def _settings_response(self, data: dict[str, Any]) -> CodexNeoSettingsResponse:
        return CodexNeoSettingsResponse(
            codex_api_base_url=data["codex_api_base_url"],
            codexgo_api_base_url=data["codexgo_api_base_url"],
            codexgo_auto_refresh_enabled=data["codexgo_auto_refresh_enabled"],
            codexgo_auto_refresh_interval_minutes=data["codexgo_auto_refresh_interval_minutes"],
            openai_activity_log_enabled=data["openai_activity_log_enabled"],
            management_activity_log_enabled=data["management_activity_log_enabled"],
            codex_home_auto_refresh_enabled=data["codex_home_auto_refresh_enabled"],
            codex_home_auto_refresh_interval_seconds=data["codex_home_auto_refresh_interval_seconds"],
            codex_home_auto_sync_enabled=data["codex_home_auto_sync_enabled"],
            minimize_to_tray_enabled=data["minimize_to_tray_enabled"],
            buyer_token_saved=bool(data.get("buyer_token_encrypted")),
        )

    def _decrypt_buyer_token(self, data: dict[str, Any]) -> str | None:
        encrypted = data.get("buyer_token_encrypted")
        if not encrypted:
            return None
        return self._encryptor.decrypt(str(encrypted).encode("utf-8"))

    async def _attach_restart_result(
        self, response: CodexNeoActionResponse, *, action_label: str
    ) -> CodexNeoActionResponse:
        restart_result = await self._codex_restart_provider()
        if restart_result.success:
            response.message = f"{response.message}; Codex Desktop restarted"
            response.restart_attempted = True
            response.restart_succeeded = True
            response.restart_output = restart_result.message
            return response
        safe_message = restart_result.message.strip() or "unknown restart error"
        failure_summary = f"Codex restart failed after {action_label}: {safe_message}"
        self._activity_log_service.append("management", failure_summary)
        response.success = False
        response.message = f"{response.message}; Codex restart failed: {safe_message}"
        response.restart_attempted = True
        response.restart_succeeded = False
        response.restart_output = safe_message
        return response


async def _post_codexgo_provider(url: str, token: str) -> dict[str, Any]:
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
        async with session.post(url, headers=headers, json={}) as response:
            text = await response.text()
            if response.status >= 400:
                raise DashboardBadRequestError(
                    f"CodexGO provider returned HTTP {response.status}", code="codexgo_provider_error"
                )
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise DashboardBadRequestError("CodexGO provider did not return JSON") from exc
            if not isinstance(parsed, dict):
                raise DashboardBadRequestError("CodexGO provider did not return an object")
            return parsed


async def restart_codex_desktop() -> CodexRestartResult:
    if platform.system().lower() != "windows":
        return CodexRestartResult(success=False, message="Codex Desktop restart is only supported on Windows")
    return await asyncio_to_thread(_restart_codex_desktop_sync)


async def asyncio_to_thread(func: Callable[[], CodexRestartResult]) -> CodexRestartResult:
    import asyncio

    return await asyncio.to_thread(func)


def _restart_codex_desktop_sync() -> CodexRestartResult:
    script = r'''
$ErrorActionPreference = "Continue"
$output = New-Object System.Collections.Generic.List[string]
$targets = @(Get-Process -Name "Codex" -ErrorAction SilentlyContinue | Where-Object {
    try {
        ($_.Path -like "*\WindowsApps\OpenAI.Codex_*") -or ($_.ProcessName -ieq "Codex")
    } catch {
        $_.ProcessName -ieq "Codex"
    }
})
if ($targets.Count -eq 0) {
    $output.Add("No running Codex Desktop processes found.")
} else {
    $output.Add("Closing $($targets.Count) Codex Desktop process(es)...")
}
foreach ($target in $targets) {
    try {
        if ($target.MainWindowHandle -ne 0) {
            [void]$target.CloseMainWindow()
        }
    } catch {}
}
Start-Sleep -Milliseconds 1500
foreach ($target in $targets) {
    try {
        if (-not $target.HasExited) {
            Stop-Process -Id $target.Id -Force -ErrorAction Stop
        }
    } catch {
        $output.Add("Could not close process $($target.Id): $($_.Exception.Message)")
    }
}
try {
    Start-Process "shell:AppsFolder\OpenAI.Codex_2p2nqsd0c76g0!App"
    $output.Add("Codex Desktop launch requested.")
    $output -join [Environment]::NewLine
    exit 0
} catch {
    $output.Add("Could not relaunch Codex Desktop: $($_.Exception.Message)")
    $output -join [Environment]::NewLine
    exit 1
}
'''
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        check=False,
    )
    output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    return CodexRestartResult(success=completed.returncode == 0, message=output or "Codex Desktop restart completed")


def _validate_auth_json(data: dict[str, Any]) -> None:
    tokens = data.get("tokens")
    if not isinstance(tokens, dict):
        raise DashboardBadRequestError("CodexGO provider did not return valid Codex auth JSON")
    access_token = tokens.get("access_token")
    account_id = tokens.get("account_id")
    id_token = tokens.get("id_token")
    if not isinstance(access_token, str) or not access_token.strip():
        raise DashboardBadRequestError("CodexGO provider did not return valid Codex auth JSON")
    if not (
        (isinstance(account_id, str) and account_id.strip())
        or (isinstance(id_token, str) and id_token.strip())
    ):
        raise DashboardBadRequestError("CodexGO provider did not return valid Codex auth JSON")


def _verify_provider_config(config_path: Path, *, base_url: str) -> None:
    text = config_path.read_text(encoding="utf-8")
    if (
        CONFIG_BEGIN_MARKER not in text
        or CONFIG_END_MARKER not in text
        or 'model_provider = "openai"' not in text
        or f'openai_base_url = "{base_url}"' not in text
    ):
        raise RuntimeError("Codex API provider config verification failed")


def _verify_provider_reverted(config_path: Path) -> None:
    text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    if (
        CONFIG_BEGIN_MARKER in text
        or CONFIG_END_MARKER in text
        or CONFIG_LEGACY_BEGIN_MARKER in text
        or CONFIG_LEGACY_END_MARKER in text
        or "openai_base_url" in text
        or CONFIG_LEGACY_PROVIDER_ID in text
    ):
        raise RuntimeError("Codex API provider revert verification failed")


def _apply_provider_config(text: str, *, base_url: str) -> str:
    lines = _remove_provider_config(text).splitlines()
    top_level, rest = _split_top_level(lines)
    top_level = [line for line in top_level if not _is_top_level_provider_line(line)]
    managed = [
        CONFIG_BEGIN_MARKER,
        'model_provider = "openai"',
        f'openai_base_url = "{base_url}"',
        CONFIG_END_MARKER,
    ]
    insert_at = _provider_insert_index(top_level)
    top_level = top_level[:insert_at] + managed + top_level[insert_at:]
    combined = top_level + rest
    return "\n".join(combined).rstrip() + "\n"


def _remove_provider_config(text: str) -> str:
    lines = text.splitlines()
    stripped: list[str] = []
    inside_managed = False
    for line in lines:
        if line.strip() in {CONFIG_BEGIN_MARKER, CONFIG_LEGACY_BEGIN_MARKER}:
            inside_managed = True
            continue
        if inside_managed and line.strip() in {CONFIG_END_MARKER, CONFIG_LEGACY_END_MARKER}:
            inside_managed = False
            continue
        if inside_managed:
            continue
        stripped.append(line)
    top_level, rest = _split_top_level(stripped)
    has_openai_base_url_override = any(_is_top_level_key(line, "openai_base_url") for line in top_level)
    top_level = [
        line
        for line in top_level
        if not _is_top_level_key(line, "openai_base_url")
        and not _is_model_provider_line(line, CONFIG_LEGACY_PROVIDER_ID)
        and not (has_openai_base_url_override and _is_model_provider_line(line, "openai"))
    ]
    return "\n".join(top_level + rest).rstrip() + ("\n" if top_level or rest else "")


def _split_top_level(lines: list[str]) -> tuple[list[str], list[str]]:
    for index, line in enumerate(lines):
        if line.lstrip().startswith("["):
            return lines[:index], lines[index:]
    return lines, []


def _is_top_level_provider_line(line: str) -> bool:
    return _is_top_level_key(line, "model_provider") or _is_top_level_key(line, "openai_base_url")


def _is_top_level_key(line: str, key: str) -> bool:
    left = line.split("=", 1)[0].strip()
    return left == key


def _is_model_provider_line(line: str, provider_id: str) -> bool:
    if not _is_top_level_key(line, "model_provider") or "=" not in line:
        return False
    value = line.split("=", 1)[1].strip().strip("\"'")
    return value == provider_id


def _provider_insert_index(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == "model":
            return index + 1
    return len(lines)


def _backup_file(path: Path, label: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = path.with_name(f"{path.name}.{label}-{timestamp}")
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    return backup_path


def _original_config_backup_path(config_path: Path) -> Path:
    return config_path.with_name(f"{config_path.name}.{CONFIG_ORIGINAL_BACKUP_SUFFIX}")


def _ensure_original_config_backup(config_path: Path, current: str) -> Path | None:
    if not config_path.exists():
        return None
    original_backup_path = _original_config_backup_path(config_path)
    if original_backup_path.exists():
        return original_backup_path
    _write_text_atomic(original_backup_path, _remove_provider_config(current))
    return original_backup_path


def _prune_config_operation_backups(config_path: Path) -> None:
    pattern = f"{config_path.name}.{CONFIG_OPERATION_BACKUP_LABEL}-*"
    backups = sorted(config_path.parent.glob(pattern), key=lambda path: path.name, reverse=True)
    now = datetime.now()
    for index, backup in enumerate(backups):
        should_prune_by_count = index >= CONFIG_OPERATION_BACKUP_KEEP_LATEST
        should_prune_by_age = (
            index >= CONFIG_OPERATION_BACKUP_MIN_KEEP
            and _backup_age_days(backup, now=now) > CONFIG_OPERATION_BACKUP_MAX_AGE_DAYS
        )
        if not should_prune_by_count and not should_prune_by_age:
            continue
        try:
            backup.unlink()
        except FileNotFoundError:
            continue


def _backup_age_days(path: Path, *, now: datetime) -> int:
    prefix = f"{path.name.split(CONFIG_OPERATION_BACKUP_LABEL, 1)[0]}{CONFIG_OPERATION_BACKUP_LABEL}-"
    timestamp = path.name.removeprefix(prefix)
    try:
        created_at = datetime.strptime(timestamp, "%Y%m%d-%H%M%S-%f")
    except ValueError:
        created_at = datetime.fromtimestamp(path.stat().st_mtime)
    return (now - created_at).days


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)
