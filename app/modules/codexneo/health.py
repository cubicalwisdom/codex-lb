from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from app.modules.codexneo.activity_log import default_activity_log_path
from app.modules.codexneo.home import default_settings_path, resolve_configured_codex_home
from app.modules.codexneo.locations import CodexNeoAccountLocationService
from app.modules.codexneo.schemas import CodexNeoHealthItem, CodexNeoHealthResponse
from app.modules.codexneo.service import (
    DEFAULT_CODEX_API_BASE_URL,
    DEFAULT_CODEXGO_API_BASE_URL,
    normalize_base_url,
    normalize_codexgo_provider_base_url,
)

AccountsCountProvider = Callable[[], Awaitable[int]]


class CodexNeoHealthService:
    def __init__(
        self,
        *,
        codex_home: Path | None = None,
        data_dir: Path,
        settings_path: Path | None = None,
        accounts_count_provider: AccountsCountProvider | None = None,
    ) -> None:
        self._settings_path = settings_path or default_settings_path()
        self._codex_home = (codex_home or resolve_configured_codex_home(settings_path=self._settings_path)).resolve()
        self._data_dir = data_dir.resolve()
        self._accounts_count_provider = accounts_count_provider

    async def health(self) -> CodexNeoHealthResponse:
        settings = _read_settings(self._settings_path)
        codex_account_count, codex_snapshot_count, registry_status = _codex_registry_counts(self._codex_home)
        backup_account_count, backup_snapshot_count, backup_status = _backup_counts(self._data_dir)
        codexneo_count = _safe_visible_account_count(self._codex_home, self._data_dir)
        accounts_count: int | None = None
        accounts_error = False
        if self._accounts_count_provider is not None:
            try:
                accounts_count = await self._accounts_count_provider()
            except Exception:
                accounts_error = True

        items = [
            CodexNeoHealthItem(
                key="codex_ib",
                label="Codex IB",
                status="ok",
                message="Dashboard API responding",
                detail="/health",
                copy_value="/health",
            ),
            CodexNeoHealthItem(
                key="codex_home",
                label="Codex Home",
                status="ok" if self._codex_home.is_dir() else "error",
                message="Detected" if self._codex_home.is_dir() else "Folder not found",
                detail=str(self._codex_home),
                copy_value=str(self._codex_home),
            ),
            CodexNeoHealthItem(
                key="codex_registry",
                label="Codex registry",
                status=registry_status,
                message=_registry_message(registry_status),
                detail=f"{codex_account_count} registry account(s), {codex_snapshot_count} auth snapshot(s)",
                copy_value=str(self._codex_home / "accounts" / "registry.json"),
            ),
            CodexNeoHealthItem(
                key="backup_store",
                label="Backup store",
                status=backup_status,
                message=_backup_message(backup_status),
                detail=f"{backup_account_count} backup account(s), {backup_snapshot_count} auth snapshot(s)",
                copy_value=str(self._data_dir / "account-backups"),
            ),
            CodexNeoHealthItem(
                key="accounts_sync",
                label="Accounts sync",
                status=_accounts_sync_status(codexneo_count, accounts_count, accounts_error),
                message=_accounts_sync_message(codexneo_count, accounts_count, accounts_error),
                detail=_accounts_sync_detail(codexneo_count, accounts_count),
            ),
            CodexNeoHealthItem(
                key="activity_log",
                label="Activity log",
                status=(
                    "ok"
                    if settings["openai_activity_log_enabled"] or settings["management_activity_log_enabled"]
                    else "warning"
                ),
                message=_activity_log_message(settings),
                detail=_activity_log_detail(),
                copy_value=str(default_activity_log_path()),
            ),
            CodexNeoHealthItem(
                key="codexgo_auth",
                label="CodexGO auth",
                status="ok" if settings["buyer_credential_saved"] else "warning",
                message=_codexgo_message(settings),
                detail=settings["codexgo_api_base_url"],
                copy_value=settings["codexgo_api_base_url"],
            ),
            CodexNeoHealthItem(
                key="openai_bridge",
                label="OpenAI bridge",
                status="ok",
                message="Configured",
                detail=settings["codex_api_base_url"],
                copy_value=settings["codex_api_base_url"],
            ),
        ]
        return CodexNeoHealthResponse(overall_status=_overall_status(items), items=items)


def _read_settings(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {
        "codex_api_base_url": DEFAULT_CODEX_API_BASE_URL,
        "codexgo_api_base_url": DEFAULT_CODEXGO_API_BASE_URL,
        "codexgo_auto_refresh_enabled": False,
        "codexgo_auto_refresh_interval_minutes": 30,
        "openai_activity_log_enabled": False,
        "management_activity_log_enabled": False,
        "buyer_token_encrypted": None,
    }
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            loaded = {}
        if isinstance(loaded, dict):
            data.update(loaded)
    data["codex_api_base_url"] = _safe_normalize_url(str(data.get("codex_api_base_url") or DEFAULT_CODEX_API_BASE_URL))
    data["codexgo_api_base_url"] = _safe_normalize_codexgo_url(
        str(data.get("codexgo_api_base_url") or DEFAULT_CODEXGO_API_BASE_URL)
    )
    data["codexgo_auto_refresh_enabled"] = bool(data.get("codexgo_auto_refresh_enabled"))
    data["codexgo_auto_refresh_interval_minutes"] = _safe_refresh_interval(
        data.get("codexgo_auto_refresh_interval_minutes")
    )
    data["openai_activity_log_enabled"] = bool(data.get("openai_activity_log_enabled"))
    data["management_activity_log_enabled"] = bool(data.get("management_activity_log_enabled"))
    data["buyer_credential_saved"] = bool(data.get("buyer_token_encrypted"))
    return data


def _safe_normalize_url(value: str) -> str:
    try:
        return normalize_base_url(value)
    except Exception:
        return DEFAULT_CODEX_API_BASE_URL


def _safe_normalize_codexgo_url(value: str) -> str:
    try:
        return normalize_codexgo_provider_base_url(value)
    except Exception:
        return DEFAULT_CODEXGO_API_BASE_URL


def _safe_refresh_interval(value: Any) -> int:
    try:
        return int(value or 30)
    except (TypeError, ValueError):
        return 30


def _codex_registry_counts(codex_home: Path) -> tuple[int, int, str]:
    accounts_dir = codex_home / "accounts"
    registry_path = accounts_dir / "registry.json"
    snapshot_count = _snapshot_count(accounts_dir)
    if not registry_path.exists():
        return 0, snapshot_count, "warning"
    try:
        root = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0, snapshot_count, "error"
    accounts = root.get("accounts") if isinstance(root, dict) else None
    if not isinstance(accounts, list):
        return 0, snapshot_count, "error"
    return len([item for item in accounts if isinstance(item, dict)]), snapshot_count, "ok"


def _backup_counts(data_dir: Path) -> tuple[int, int, str]:
    backup_dir = data_dir / "account-backups"
    registry_path = backup_dir / "backup-registry.json"
    snapshot_count = _snapshot_count(backup_dir)
    if not backup_dir.exists():
        return 0, 0, "warning"
    if not registry_path.exists():
        return 0, snapshot_count, "warning" if snapshot_count else "ok"
    try:
        root = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0, snapshot_count, "error"
    accounts = root.get("accounts") if isinstance(root, dict) else None
    if not isinstance(accounts, list):
        return 0, snapshot_count, "error"
    return len([item for item in accounts if isinstance(item, dict)]), snapshot_count, "ok"


def _snapshot_count(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.glob("*.auth.json") if path.is_file())


def _safe_visible_account_count(codex_home: Path, data_dir: Path) -> int:
    try:
        return len(CodexNeoAccountLocationService(codex_home=codex_home, data_dir=data_dir).all_account_rows())
    except Exception:
        return 0


def _registry_message(status: str) -> str:
    if status == "ok":
        return "Registry readable"
    if status == "warning":
        return "Registry not found"
    return "Registry invalid"


def _backup_message(status: str) -> str:
    if status == "ok":
        return "Backup readable"
    if status == "warning":
        return "Backup registry not found"
    return "Backup registry invalid"


def _accounts_sync_status(codexneo_count: int, accounts_count: int | None, accounts_error: bool) -> str:
    if accounts_error or accounts_count is None:
        return "warning"
    if accounts_count != codexneo_count:
        return "error"
    return "ok"


def _accounts_sync_message(codexneo_count: int, accounts_count: int | None, accounts_error: bool) -> str:
    if accounts_error or accounts_count is None:
        return "Codex IB account count unavailable"
    if accounts_count != codexneo_count:
        return "Mismatch"
    return "Counts aligned"


def _accounts_sync_detail(codexneo_count: int, accounts_count: int | None) -> str:
    if accounts_count is None:
        return f"{codexneo_count} CodexNeo account(s), unknown Codex IB account count"
    return f"{codexneo_count} CodexNeo account(s), {accounts_count} Codex IB account(s)"


def _activity_log_message(settings: dict[str, Any]) -> str:
    openai = "on" if settings["openai_activity_log_enabled"] else "off"
    management = "on" if settings["management_activity_log_enabled"] else "off"
    return f"OpenAI log {openai}, Management log {management}"


def _activity_log_detail() -> str:
    path = default_activity_log_path()
    if path.exists():
        return "Temporary log file present"
    return "Temporary log file not present"


def _codexgo_message(settings: dict[str, Any]) -> str:
    if not settings["buyer_credential_saved"]:
        return "Buyer credential missing"
    if settings["codexgo_auto_refresh_enabled"]:
        return f"Buyer credential saved, auto-refresh every {settings['codexgo_auto_refresh_interval_minutes']} min"
    return "Buyer credential saved, auto-refresh off"


def _overall_status(items: list[CodexNeoHealthItem]) -> str:
    statuses = {item.status for item in items}
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    return "ok"
