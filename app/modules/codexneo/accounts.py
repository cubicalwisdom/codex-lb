from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.auth import claims_from_auth, parse_auth_json
from app.core.config.settings import get_settings as get_app_settings
from app.db.models import Account, AccountStatus, UsageHistory
from app.db.session import get_background_session
from app.modules.accounts.repository import AccountsRepository
from app.modules.codexneo.home import resolve_configured_codex_home
from app.modules.codexneo.locations import CodexNeoAccountLocationService
from app.modules.codexneo.schemas import (
    CodexNeoAccountRow,
    CodexNeoAccountsResponse,
    CodexNeoAccountUsage,
    CodexNeoAccountUsageWindow,
)
from app.modules.codexneo.snapshots import existing_snapshot_path
from app.modules.codexneo.sync import CodexNeoAccountsSyncService
from app.modules.usage.repository import UsageRepository


@dataclass(frozen=True)
class _CodexIbAccountState:
    id: str
    status: AccountStatus
    deactivation_reason: str | None


class CodexHomeAccountService:
    def __init__(
        self,
        *,
        codex_home: Path | None = None,
        settings_path: Path | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self._codex_home = (codex_home or resolve_configured_codex_home(settings_path=settings_path)).resolve()
        self._data_dir = data_dir or get_app_settings().data_dir

    def load_accounts(self) -> CodexNeoAccountsResponse:
        registry_path = self._codex_home / "accounts" / "registry.json"
        location_service = CodexNeoAccountLocationService(codex_home=self._codex_home, data_dir=self._data_dir)
        location_service.apply_bulk_defaults()
        location_settings = location_service.refresh_bulk_states()
        if not registry_path.exists():
            backup_items = _dedupe_registry_items(
                location_service.all_account_rows(),
                live_dir=self._codex_home / "accounts",
                backup_dir=location_service.backup_dir,
                active_key=None,
            )
            backup_rows = [
                _account_from_registry_item(item, active_key=None)
                for item in backup_items
            ]
            return CodexNeoAccountsResponse(
                accounts=backup_rows,
                active_account_key=None,
                registry_path=str(registry_path),
                message=(
                    "Codex account registry not found"
                    if not backup_rows
                    else f"Loaded {len(backup_rows)} backup account(s)"
                ),
                codex_all_enabled=location_settings["codex_all_enabled"],
                backup_all_enabled=location_settings["backup_all_enabled"],
            )
        try:
            loaded = json.loads(registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return CodexNeoAccountsResponse(
                accounts=[],
                active_account_key=None,
                registry_path=str(registry_path),
                message="Codex account registry is invalid JSON",
                codex_all_enabled=location_settings["codex_all_enabled"],
                backup_all_enabled=location_settings["backup_all_enabled"],
            )
        if not isinstance(loaded, dict):
            return CodexNeoAccountsResponse(
                accounts=[],
                active_account_key=None,
                registry_path=str(registry_path),
                message="Codex account registry has an unsupported format",
                codex_all_enabled=location_settings["codex_all_enabled"],
                backup_all_enabled=location_settings["backup_all_enabled"],
            )
        active_key = _optional_str(loaded.get("active_account_key"))
        raw_accounts = _dedupe_registry_items(
            location_service.all_account_rows(),
            live_dir=self._codex_home / "accounts",
            backup_dir=location_service.backup_dir,
            active_key=active_key,
        )
        accounts = [
            _account_from_registry_item(item, active_key=active_key)
            for item in raw_accounts
            if isinstance(item, dict) and _optional_str(item.get("account_key"))
        ]
        return CodexNeoAccountsResponse(
            accounts=accounts,
            active_account_key=active_key,
            registry_path=str(registry_path),
            message=f"Loaded {len(accounts)} account(s) from Codex registry",
            codex_all_enabled=location_settings["codex_all_enabled"],
            backup_all_enabled=location_settings["backup_all_enabled"],
        )

    async def sync_and_load_accounts(self) -> CodexNeoAccountsResponse:
        sync_service = CodexNeoAccountsSyncService(codex_home=self._codex_home, data_dir=self._data_dir)
        await sync_service.sync_codex_home_to_accounts()
        return await self.load_accounts_with_codex_ib_usage()

    async def load_accounts_with_codex_ib_usage(self) -> CodexNeoAccountsResponse:
        response = self.load_accounts()
        if not response.accounts:
            return response

        async with get_background_session() as session:
            codex_ib_accounts = await AccountsRepository(session).list_accounts(refresh_existing=True)
            matches = {
                row.account_key: (
                    _codex_ib_account_state(match)
                    if (match := _matching_codex_ib_account(row, codex_ib_accounts)) is not None
                    else None
                )
                for row in response.accounts
            }
            account_ids = {
                account.id
                for account in matches.values()
                if account is not None
            }
            usage_repo = UsageRepository(session)
            primary_by_account = await usage_repo.latest_by_account("primary", account_ids=account_ids)
            secondary_by_account = await usage_repo.latest_by_account("secondary", account_ids=account_ids)

        accounts: list[CodexNeoAccountRow] = []
        for row in response.accounts:
            match = matches[row.account_key]
            accounts.append(
                _merge_codex_ib_usage(
                    row,
                    account=match,
                    primary=primary_by_account.get(match.id) if match is not None else None,
                    secondary=secondary_by_account.get(match.id) if match is not None else None,
                )
            )
        return response.model_copy(update={"accounts": accounts})


def _account_from_registry_item(item: dict[str, Any], *, active_key: str | None) -> CodexNeoAccountRow:
    account_key = _optional_str(item.get("account_key"))
    assert account_key is not None
    usage = item.get("last_usage")
    usage_data = usage if isinstance(usage, dict) else {}
    codex_present = bool(item.get("codex", False))
    backup_present = bool(item.get("backup", False))
    last_usage_at = item.get("last_usage_at") or item.get("last_used_at")
    return CodexNeoAccountRow(
        account_key=account_key,
        selector=_optional_str(item.get("selector")),
        email=_optional_str(item.get("email")),
        alias=_optional_str(item.get("alias")),
        account_name=_optional_str(item.get("account_name")),
        plan=_optional_str(item.get("plan")),
        auth_mode=_optional_str(item.get("auth_mode")),
        active=account_key == active_key or bool(item.get("active")),
        last_usage_at=_optional_str(last_usage_at),
        usage=_usage_from_registry(usage_data),
        codex=codex_present,
        backup=backup_present,
        api=bool(item.get("api", False)),
        api_hour_count=_optional_int(item.get("api_hour_count")) or 0,
        api_day_count=_optional_int(item.get("api_day_count")) or 0,
        availability=_format_availability(item, codex=codex_present, backup=backup_present),
        status=_format_status_last(item, usage_data=usage_data, codex=codex_present, backup=backup_present),
    )


def _matching_codex_ib_account(
    row: CodexNeoAccountRow,
    accounts: list[Account],
) -> Account | None:
    exact = [account for account in accounts if account.id == row.account_key]
    if len(exact) == 1:
        return exact[0]

    normalized_email = _normalize_email(row.email or row.selector)
    if normalized_email is None:
        return None
    email_matches = [
        account
        for account in accounts
        if _normalize_email(account.email) == normalized_email
    ]
    if len(email_matches) == 1:
        return email_matches[0]
    return None


def _merge_codex_ib_usage(
    row: CodexNeoAccountRow,
    *,
    account: _CodexIbAccountState | None,
    primary: UsageHistory | None,
    secondary: UsageHistory | None,
) -> CodexNeoAccountRow:
    registry_last = _parse_timestamp(row.last_usage_at)
    use_primary = _history_should_replace_registry_window(
        row.usage.primary,
        registry_last=registry_last,
        history=primary,
    )
    use_secondary = _history_should_replace_registry_window(
        row.usage.secondary,
        registry_last=registry_last,
        history=secondary,
    )
    if account is None and not use_primary and not use_secondary:
        return row

    merged_primary = _usage_window_from_history(primary) if use_primary else row.usage.primary
    merged_secondary = _usage_window_from_history(secondary) if use_secondary else row.usage.secondary
    selected_history = [
        history
        for use_history, history in ((use_primary, primary), (use_secondary, secondary))
        if use_history and history is not None
    ]
    latest_history_at = max((_history_recorded_at(history) for history in selected_history), default=None)
    latest_usage_at = _latest_timestamp(registry_last, latest_history_at)
    last_usage_at = latest_usage_at.isoformat() if latest_usage_at is not None else row.last_usage_at
    update: dict[str, Any] = {}
    if use_primary or use_secondary:
        update.update(
            {
                "last_usage_at": last_usage_at,
                "usage": CodexNeoAccountUsage(
                    primary=merged_primary,
                    secondary=merged_secondary,
                ),
            }
        )

    if account is not None:
        account_status = account.status
        update.update(
            {
                "codex_ib_account_id": account.id,
                "codex_ib_status": account_status.value,
                "codex_ib_status_reason": account.deactivation_reason,
                "codex_ib_routable": _is_codex_ib_routable(account_status),
            }
        )
        if account_status == AccountStatus.ACTIVE:
            if use_primary or use_secondary:
                update["status"] = f"Fresh / {_format_relative_time(last_usage_at)}"
        else:
            label = _codex_ib_status_label(account_status)
            update["availability"] = label
            update["status"] = f"{label} / {_format_relative_time(last_usage_at)}"
    elif use_primary or use_secondary:
        update["status"] = f"Fresh / {_format_relative_time(last_usage_at)}"

    return row.model_copy(update=update)


def _is_codex_ib_routable(status: AccountStatus) -> bool:
    return status == AccountStatus.ACTIVE


def _codex_ib_status_label(status: AccountStatus) -> str:
    return {
        AccountStatus.ACTIVE: "Ready",
        AccountStatus.RATE_LIMITED: "Rate limited",
        AccountStatus.QUOTA_EXCEEDED: "Quota exceeded",
        AccountStatus.PAUSED: "Paused",
        AccountStatus.REAUTH_REQUIRED: "Re-auth required",
        AccountStatus.DEACTIVATED: "Deactivated",
    }.get(status, status.value.replace("_", " ").title())


def _codex_ib_account_state(account: Account) -> _CodexIbAccountState:
    return _CodexIbAccountState(
        id=account.id,
        status=_coerce_account_status(account.status),
        deactivation_reason=account.deactivation_reason,
    )


def _coerce_account_status(status: AccountStatus | str) -> AccountStatus:
    if isinstance(status, AccountStatus):
        return status
    try:
        return AccountStatus(status)
    except ValueError:
        return AccountStatus.DEACTIVATED


def _history_should_replace_registry_window(
    registry_window: CodexNeoAccountUsageWindow | None,
    *,
    registry_last: datetime | None,
    history: UsageHistory | None,
) -> bool:
    if history is None:
        return False
    if registry_window is None:
        return True
    if registry_last is None:
        return False
    return _history_recorded_at(history) > registry_last


def _usage_window_from_history(history: UsageHistory | None) -> CodexNeoAccountUsageWindow | None:
    if history is None:
        return None
    used_percent = _clamp_percent(int(float(history.used_percent)))
    return CodexNeoAccountUsageWindow(
        used_percent=used_percent,
        remaining_percent=100 - used_percent if used_percent is not None else None,
        resets_at=str(history.reset_at) if history.reset_at is not None else None,
        window_minutes=history.window_minutes,
    )


def _history_recorded_at(history: UsageHistory) -> datetime:
    recorded_at = history.recorded_at
    if recorded_at.tzinfo is None:
        return recorded_at.replace(tzinfo=UTC)
    return recorded_at.astimezone(UTC)


def _latest_timestamp(*values: datetime | None) -> datetime | None:
    available = [value for value in values if value is not None]
    return max(available) if available else None


def _normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _dedupe_registry_items(
    items: list[dict[str, Any]],
    *,
    live_dir: Path,
    backup_dir: Path,
    active_key: str | None,
) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str, str, str, str] | tuple[str, str], dict[str, Any]] = {}
    order: list[tuple[str, str, str, str, str] | tuple[str, str]] = []
    for item in items:
        if not isinstance(item, dict) or not _optional_str(item.get("account_key")):
            continue
        identity = _identity_for_registry_item(item, live_dir=live_dir, backup_dir=backup_dir)
        if identity not in deduped:
            deduped[identity] = dict(item)
            order.append(identity)
            continue
        deduped[identity] = _merge_duplicate_registry_item(
            deduped[identity],
            item,
            active_key=active_key,
        )
    return [deduped[identity] for identity in order]


def _identity_for_registry_item(
    item: dict[str, Any],
    *,
    live_dir: Path,
    backup_dir: Path,
) -> tuple[str, str, str, str, str] | tuple[str, str]:
    account_key = _optional_str(item.get("account_key"))
    auth_path = _optional_str(item.get("auth_path"))
    if auth_path:
        try:
            auth = parse_auth_json(Path(auth_path).read_bytes())
            claims = claims_from_auth(auth)
        except Exception:
            pass
        else:
            if claims.account_id or claims.email or claims.workspace_id or claims.workspace_label:
                return (
                    "auth",
                    claims.account_id or "",
                    (claims.email or "").strip().lower(),
                    claims.workspace_id or "",
                    claims.workspace_label or "",
                )
    if account_key:
        for directory in (live_dir, backup_dir):
            snapshot = existing_snapshot_path(directory, account_key)
            if snapshot is None:
                continue
            try:
                auth = parse_auth_json(snapshot.read_bytes())
                claims = claims_from_auth(auth)
            except Exception:
                continue
            if claims.account_id or claims.email or claims.workspace_id or claims.workspace_label:
                return (
                    "auth",
                    claims.account_id or "",
                    (claims.email or "").strip().lower(),
                    claims.workspace_id or "",
                    claims.workspace_label or "",
                )
    email = _optional_str(item.get("email") or item.get("selector"))
    if email:
        return ("email", email.lower())
    return ("key", account_key or "")


def _merge_duplicate_registry_item(
    current: dict[str, Any],
    incoming: dict[str, Any],
    *,
    active_key: str | None,
) -> dict[str, Any]:
    if _should_prefer_registry_item(incoming, current, active_key=active_key):
        preferred = dict(incoming)
        secondary = current
    else:
        preferred = dict(current)
        secondary = incoming

    preferred["codex"] = bool(current.get("codex")) or bool(incoming.get("codex"))
    preferred["backup"] = bool(current.get("backup")) or bool(incoming.get("backup"))
    preferred["codex_registered"] = bool(current.get("codex_registered")) or bool(incoming.get("codex_registered"))
    usage_source = _freshest_usage_item(preferred, secondary)
    for field in ("last_usage", "last_usage_at", "last_used_at", "usage_status", "usage_override", "status"):
        if usage_source.get(field):
            preferred[field] = usage_source.get(field)
    for field in ("email", "selector", "plan", "alias", "account_name", "auth_mode", "availability", "status"):
        if not preferred.get(field) and secondary.get(field):
            preferred[field] = secondary[field]
    return preferred


def _freshest_usage_item(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    primary_last = _parse_timestamp(primary.get("last_usage_at") or primary.get("last_used_at"))
    secondary_last = _parse_timestamp(secondary.get("last_usage_at") or secondary.get("last_used_at"))
    if secondary_last and (not primary_last or secondary_last > primary_last):
        return secondary
    if primary.get("last_usage") or primary_last:
        return primary
    if secondary.get("last_usage") or secondary_last:
        return secondary
    return primary


def _should_prefer_registry_item(
    candidate: dict[str, Any],
    current: dict[str, Any],
    *,
    active_key: str | None,
) -> bool:
    candidate_key = _optional_str(candidate.get("account_key"))
    current_key = _optional_str(current.get("account_key"))
    if active_key:
        if candidate_key == active_key and current_key != active_key:
            return True
        if current_key == active_key and candidate_key != active_key:
            return False
    if bool(candidate.get("codex")) != bool(current.get("codex")):
        return bool(candidate.get("codex"))
    candidate_last = _parse_timestamp(candidate.get("last_usage_at") or candidate.get("last_used_at"))
    current_last = _parse_timestamp(current.get("last_usage_at") or current.get("last_used_at"))
    if candidate_last and current_last and candidate_last != current_last:
        return candidate_last > current_last
    if candidate_last and not current_last:
        return True
    return False


def _usage_from_registry(usage: dict[str, Any]) -> CodexNeoAccountUsage:
    return CodexNeoAccountUsage(
        primary=_usage_window_from_registry(usage.get("primary")),
        secondary=_usage_window_from_registry(usage.get("secondary")),
    )


def _usage_window_from_registry(value: Any) -> CodexNeoAccountUsageWindow | None:
    if not isinstance(value, dict):
        return None
    used_percent = _optional_int(value.get("used_percent"))
    remaining_percent = _optional_int(value.get("remaining_percent"))
    if remaining_percent is None and used_percent is not None:
        remaining_percent = 100 - used_percent
    return CodexNeoAccountUsageWindow(
        used_percent=_clamp_percent(used_percent),
        remaining_percent=_clamp_percent(remaining_percent),
        resets_at=_optional_str(value.get("resets_at")),
        window_minutes=_optional_int(value.get("window_minutes")),
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clamp_percent(value: int | None) -> int | None:
    if value is None:
        return None
    return max(0, min(100, value))


def _format_availability(item: dict[str, Any], *, codex: bool, backup: bool) -> str:
    if bool(item.get("temporarily_unavailable")):
        return "Temp off"
    existing = _optional_str(item.get("availability"))
    if existing:
        return existing
    if codex or bool(item.get("codex_registered")):
        return "Ready"
    if backup:
        return "Backup"
    return "-"


def _format_status_last(
    item: dict[str, Any],
    *,
    usage_data: dict[str, Any],
    codex: bool,
    backup: bool,
) -> str:
    existing = _optional_str(item.get("status"))
    if existing and "/" in existing:
        return existing
    status = _format_usage_status(
        _optional_str(usage_data.get("status") or item.get("usage_status") or existing),
        _optional_str(usage_data.get("override") or item.get("usage_override")),
        codex=codex,
        backup=backup,
        has_usage_window=_has_usage_window(usage_data),
    )
    last = _format_relative_time(item.get("last_usage_at") or item.get("last_used_at"))
    return f"{status} / {last}"


def _format_usage_status(
    status: str | None,
    override: str | None,
    *,
    codex: bool,
    backup: bool,
    has_usage_window: bool,
) -> str:
    if override and override.strip().lower() == "timedout":
        return "Stale"
    normalized = (status or "").strip().lower()
    if normalized == "ok":
        return "Fresh"
    if normalized == "local":
        return "Local"
    if normalized == "stored":
        return "Stored"
    if normalized == "error":
        return "Needs attention"
    if status:
        return status.strip()
    if codex and has_usage_window:
        return "Fresh"
    if backup and not codex:
        return "Stored"
    return "Unknown"


def _has_usage_window(usage_data: dict[str, Any]) -> bool:
    for key in ("primary", "secondary"):
        value = usage_data.get(key)
        if isinstance(value, dict) and any(value.get(field) is not None for field in ("used_percent", "resets_at")):
            return True
    return False


def _format_relative_time(value: Any) -> str:
    timestamp = _parse_timestamp(value)
    if timestamp is None:
        return "-"
    span = datetime.now(UTC) - timestamp
    total_seconds = max(0, int(span.total_seconds()))
    if total_seconds < 60:
        return "just now"
    total_minutes = total_seconds // 60
    if total_minutes < 60:
        return f"{total_minutes}m ago"
    total_hours = total_minutes // 60
    if total_hours < 24:
        return f"{total_hours}h ago"
    return f"{total_hours // 24}d ago"


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromtimestamp(float(text), tz=UTC)
    except (OverflowError, OSError, ValueError):
        pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
