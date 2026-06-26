from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.core.auth import claims_from_auth, parse_auth_json
from app.core.config.settings import get_settings as get_app_settings
from app.modules.codexneo.schemas import CodexNeoActionResponse
from app.modules.codexneo.snapshots import (
    account_key_from_snapshot,
    delete_snapshot_files,
    existing_snapshot_path,
    preferred_snapshot_path,
    snapshot_exists,
)

LocationName = Literal["codex", "backup"]


@dataclass(frozen=True, slots=True)
class _ResolvedLocationKeys:
    live_keys: list[str]
    backup_keys: list[str]
    live_keys_by_requested: dict[str, list[str]]
    backup_keys_by_requested: dict[str, list[str]]


class CodexNeoAccountLocationService:
    def __init__(self, *, codex_home: Path, data_dir: Path | None = None) -> None:
        self._codex_home = codex_home.resolve()
        self._data_dir = data_dir or get_app_settings().data_dir
        self._backup_dir = self._data_dir / "account-backups"
        self._settings_path = self._data_dir / "codexneo-location-settings.json"

    @property
    def backup_dir(self) -> Path:
        return self._backup_dir

    def location_settings(self) -> dict[str, Any]:
        data = _read_json(self._settings_path, default=_default_settings())
        normalized = _default_settings()
        normalized.update(data if isinstance(data, dict) else {})
        normalized["manual_codex_disabled"] = _string_list(normalized.get("manual_codex_disabled"))
        normalized["manual_backup_disabled"] = _string_list(normalized.get("manual_backup_disabled"))
        normalized["codex_all_enabled"] = bool(normalized.get("codex_all_enabled"))
        normalized["backup_all_enabled"] = bool(normalized.get("backup_all_enabled"))
        return normalized

    def set_location(
        self,
        account_keys: list[str],
        *,
        location: LocationName,
        present: bool,
    ) -> CodexNeoActionResponse:
        keys = _clean_keys(account_keys)
        if not keys:
            return CodexNeoActionResponse(success=False, message="No accounts were selected")
        result = self._set_location(keys, location=location, present=present)
        self.refresh_bulk_states()
        return result

    def set_bulk_default(self, *, location: LocationName, present: bool) -> CodexNeoActionResponse:
        accounts = [
            row["account_key"]
            for row in self.all_account_rows()
            if bool(row.get(location)) != present
        ]
        result = (
            self._set_location(accounts, location=location, present=present)
            if accounts
            else CodexNeoActionResponse(success=True, message="No account locations changed")
        )
        self.refresh_bulk_states()
        return result

    def apply_bulk_defaults(self) -> CodexNeoActionResponse:
        settings = self.location_settings()
        if not settings["backup_all_enabled"]:
            return CodexNeoActionResponse(success=True, message="No bulk defaults were enabled")
        keys = [
            row["account_key"]
            for row in self.all_account_rows()
            if row.get("codex") and not row.get("backup")
        ]
        result = (
            self._set_backup_presence(keys, present=True)
            if keys
            else CodexNeoActionResponse(success=True, message="No accounts needed backup")
        )
        self.refresh_bulk_states()
        return result

    def refresh_bulk_states(self) -> dict[str, Any]:
        settings = self.location_settings()
        rows = self.all_account_rows()
        settings["codex_all_enabled"] = _bulk_enabled(rows, "codex")
        settings["backup_all_enabled"] = _bulk_enabled(rows, "backup")
        settings["manual_codex_disabled"] = []
        settings["manual_backup_disabled"] = []
        self._write_settings(settings)
        return settings

    def ensure_backup_present(self, account_keys: list[str]) -> CodexNeoActionResponse:
        keys = _clean_keys(account_keys)
        if not keys:
            return CodexNeoActionResponse(success=True, message="No accounts needed backup")
        return self._set_backup_presence(keys, present=True)

    def switch_account_locally(self, account_key: str) -> CodexNeoActionResponse:
        keys = _clean_keys([account_key])
        if not keys:
            return CodexNeoActionResponse(success=False, message="No account was selected")
        requested_key = keys[0]
        live_root = self._live_registry()
        backup_root = self._backup_registry()
        resolved = self._resolve_equivalent_keys([requested_key], live_root=live_root, backup_root=backup_root)
        live_key = _first_preferred_key(resolved.live_keys_by_requested.get(requested_key, []), requested_key)
        if live_key is None:
            backup_key = _first_preferred_key(resolved.backup_keys_by_requested.get(requested_key, []), requested_key)
            if backup_key is None:
                return CodexNeoActionResponse(success=False, message=f"Account {requested_key} was not found")
            restored = self._restore_to_codex([backup_key])
            if not restored.success:
                return restored
            live_key = backup_key
            live_root = self._live_registry()
        source = existing_snapshot_path(self._live_accounts_dir(), live_key)
        if source is None:
            return CodexNeoActionResponse(success=False, message=f"Auth snapshot for {live_key} was not found")
        previous_key = live_root.get("active_account_key")
        if previous_key != live_key:
            live_root["previous_active_account_key"] = previous_key
        live_root["active_account_key"] = live_key
        live_root["active_account_activated_at_ms"] = int(time.time() * 1000)
        self._save_live_registry(live_root)
        (self._codex_home / "auth.json").write_bytes(source.read_bytes())
        return CodexNeoActionResponse(
            success=True,
            message=f"Switched to {live_key} with local registry fallback",
        )

    def delete_everywhere(self, account_keys: list[str]) -> CodexNeoActionResponse:
        keys = _clean_keys(account_keys)
        live_root = self._live_registry()
        backup_root = self._backup_registry()
        resolved = self._resolve_equivalent_keys(keys, live_root=live_root, backup_root=backup_root)
        live_removed = 0
        backup_removed = 0
        active_removed = False
        for key in resolved.live_keys:
            active_removed = active_removed or _is_active(live_root, key)
            removed_account = _remove_account(live_root, key, clear_active=True)
            removed_snapshot = _delete_snapshot(self._live_accounts_dir(), key)
            if removed_account or removed_snapshot:
                live_removed += 1
        for key in resolved.backup_keys:
            removed_account = _remove_account(backup_root, key, clear_active=False)
            removed_snapshot = _delete_snapshot(self._backup_dir, key)
            if removed_account or removed_snapshot:
                backup_removed += 1
        if active_removed:
            try:
                (self._codex_home / "auth.json").unlink()
            except FileNotFoundError:
                pass
        self._save_live_registry(live_root)
        self._save_or_delete_backup_registry(backup_root)
        return CodexNeoActionResponse(
            success=True,
            message=(
                f"Deleted {len(keys)} account(s). Removed {live_removed} from Codex Home "
                f"and {backup_removed} from Backup."
            ),
        )

    def all_account_rows(self) -> list[dict[str, Any]]:
        live_root = self._live_registry()
        backup_root = self._backup_registry()
        live_map = _account_map(live_root)
        backup_map = _account_map(backup_root)
        rows: list[dict[str, Any]] = []
        for key, row in live_map.items():
            merged = dict(row)
            merged["codex_registered"] = True
            merged["codex"] = snapshot_exists(self._live_accounts_dir(), key)
            merged["backup"] = key in backup_map and snapshot_exists(self._backup_dir, key)
            rows.append(merged)
        for key, row in backup_map.items():
            if key in live_map or not snapshot_exists(self._backup_dir, key):
                continue
            merged = dict(row)
            merged["codex"] = False
            merged["backup"] = True
            rows.append(merged)
        return rows

    def _set_location(self, keys: list[str], *, location: LocationName, present: bool) -> CodexNeoActionResponse:
        if location == "backup":
            return self._set_backup_presence(keys, present=present)
        return self._set_codex_presence(keys, present=present)

    def _set_backup_presence(self, keys: list[str], *, present: bool) -> CodexNeoActionResponse:
        if present:
            return self._add_to_backup(keys)
        resolved = self._resolve_equivalent_keys(keys)
        live_keys = set(_account_map(self._live_registry()))
        backup_root = self._backup_registry()
        changed = 0
        blocked = 0
        for requested_key in keys:
            matching_live = resolved.live_keys_by_requested.get(requested_key, [])
            matching_backup = resolved.backup_keys_by_requested.get(requested_key, [])
            if not any(key in live_keys for key in matching_live):
                blocked += 1
                continue
            for key in matching_backup:
                if _remove_account(backup_root, key, clear_active=False):
                    changed += 1
                _delete_snapshot(self._backup_dir, key)
        self._save_or_delete_backup_registry(backup_root)
        return CodexNeoActionResponse(
            success=blocked == 0,
            message=f"Removed backup for {changed} account(s)."
            + (f" Skipped {blocked} account(s) because they must remain in Backup." if blocked else ""),
        )

    def _set_codex_presence(self, keys: list[str], *, present: bool) -> CodexNeoActionResponse:
        if present:
            return self._restore_to_codex(keys)
        resolved = self._resolve_equivalent_keys(keys)
        backup_keys = set(_account_map(self._backup_registry()))
        live_root = self._live_registry()
        changed = 0
        blocked = 0
        active_removed = False
        for requested_key in keys:
            matching_live = resolved.live_keys_by_requested.get(requested_key, [])
            matching_backup = resolved.backup_keys_by_requested.get(requested_key, [])
            if not any(key in backup_keys for key in matching_backup):
                blocked += 1
                continue
            for key in matching_live:
                active_removed = active_removed or _is_active(live_root, key)
                if _remove_account(live_root, key, clear_active=True):
                    changed += 1
                _delete_snapshot(self._live_accounts_dir(), key)
        if active_removed:
            try:
                (self._codex_home / "auth.json").unlink()
            except FileNotFoundError:
                pass
        self._save_live_registry(live_root)
        return CodexNeoActionResponse(
            success=blocked == 0,
            message=f"Removed from Codex Home {changed} account(s)."
            + (f" Skipped {blocked} account(s) because Backup is off." if blocked else ""),
        )

    def _add_to_backup(self, keys: list[str]) -> CodexNeoActionResponse:
        live_root = self._live_registry()
        live_map = _account_map(live_root)
        backup_root = self._backup_registry()
        changed = 0
        skipped = 0
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        for key in keys:
            source = existing_snapshot_path(self._live_accounts_dir(), key)
            row = live_map.get(key)
            if row is None or source is None:
                skipped += 1
                continue
            identity = _identity_for_key(
                key,
                live_row=row,
                backup_row=None,
                live_dir=self._live_accounts_dir(),
                backup_dir=self._backup_dir,
            )
            _remove_equivalent_backup_copies(
                backup_root,
                source_key=key,
                source_identity=identity,
                backup_dir=self._backup_dir,
            )
            _upsert_account(backup_root, row)
            _snapshot_path(self._backup_dir, key).write_bytes(source.read_bytes())
            changed += 1
        self._save_or_delete_backup_registry(backup_root)
        return CodexNeoActionResponse(
            success=skipped == 0,
            message=f"Backed up {changed} account(s)."
            + (f" Skipped {skipped} account(s) because live Codex data was missing." if skipped else ""),
        )

    def _restore_to_codex(self, keys: list[str]) -> CodexNeoActionResponse:
        backup_root = self._backup_registry()
        backup_map = _account_map(backup_root)
        live_root = self._live_registry()
        changed = 0
        skipped = 0
        self._live_accounts_dir().mkdir(parents=True, exist_ok=True)
        for key in keys:
            source = existing_snapshot_path(self._backup_dir, key)
            row = backup_map.get(key)
            if row is None or source is None:
                skipped += 1
                continue
            _upsert_account(live_root, row)
            _snapshot_path(self._live_accounts_dir(), key).write_bytes(source.read_bytes())
            changed += 1
        self._save_live_registry(live_root)
        return CodexNeoActionResponse(
            success=skipped == 0,
            message=f"Restored {changed} account(s) to Codex Home."
            + (f" Skipped {skipped} account(s) because backup data was missing." if skipped else ""),
        )

    def _live_accounts_dir(self) -> Path:
        return self._codex_home / "accounts"

    def _live_registry_path(self) -> Path:
        return self._live_accounts_dir() / "registry.json"

    def _backup_registry_path(self) -> Path:
        return self._backup_dir / "backup-registry.json"

    def _live_registry(self) -> dict[str, Any]:
        return _ensure_registry(_read_json(self._live_registry_path(), default={}))

    def _backup_registry(self) -> dict[str, Any]:
        return _ensure_registry(_read_json(self._backup_registry_path(), default={}))

    def _resolve_equivalent_keys(
        self,
        keys: list[str],
        *,
        live_root: dict[str, Any] | None = None,
        backup_root: dict[str, Any] | None = None,
    ) -> "_ResolvedLocationKeys":
        live_root = live_root or self._live_registry()
        backup_root = backup_root or self._backup_registry()
        live_map = _account_map(live_root)
        backup_map = _account_map(backup_root)
        live_dir = self._live_accounts_dir()
        backup_dir = self._backup_dir
        live_candidates = _ordered_unique([*live_map, *_snapshot_keys(live_dir)])
        backup_candidates = _ordered_unique([*backup_map, *_snapshot_keys(backup_dir)])
        identities: dict[str, tuple[str, ...]] = {}
        for key in set(keys) | set(live_candidates) | set(backup_candidates):
            identities[key] = _identity_for_key(
                key,
                live_row=live_map.get(key),
                backup_row=backup_map.get(key),
                live_dir=live_dir,
                backup_dir=backup_dir,
            )
        live_by_requested: dict[str, list[str]] = {}
        backup_by_requested: dict[str, list[str]] = {}
        for requested in keys:
            identity = identities.get(requested, ("key", requested))
            live_matches = [key for key in live_candidates if identities.get(key) == identity]
            backup_matches = [key for key in backup_candidates if identities.get(key) == identity]
            live_by_requested[requested] = live_matches or (
                [requested] if requested in live_map or snapshot_exists(live_dir, requested) else []
            )
            backup_by_requested[requested] = backup_matches or (
                [requested] if requested in backup_map or snapshot_exists(backup_dir, requested) else []
            )
        return _ResolvedLocationKeys(
            live_keys=_ordered_unique(key for values in live_by_requested.values() for key in values),
            backup_keys=_ordered_unique(key for values in backup_by_requested.values() for key in values),
            live_keys_by_requested=live_by_requested,
            backup_keys_by_requested=backup_by_requested,
        )

    def _save_live_registry(self, root: dict[str, Any]) -> None:
        self._live_accounts_dir().mkdir(parents=True, exist_ok=True)
        _write_json_atomic(self._live_registry_path(), _ensure_registry(root))

    def _save_or_delete_backup_registry(self, root: dict[str, Any]) -> None:
        root = _ensure_registry(root)
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        if not root["accounts"]:
            try:
                self._backup_registry_path().unlink()
            except FileNotFoundError:
                pass
            return
        _write_json_atomic(self._backup_registry_path(), root)

    def _write_settings(self, settings: dict[str, Any]) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(self._settings_path, settings)


def _default_settings() -> dict[str, Any]:
    return {
        "codex_all_enabled": False,
        "backup_all_enabled": False,
        "manual_codex_disabled": [],
        "manual_backup_disabled": [],
    }


def _clean_keys(account_keys: list[str]) -> list[str]:
    return [key.strip() for key in account_keys if key.strip()]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(str(item).strip() for item in value if str(item).strip())


def _bulk_enabled(rows: list[dict[str, Any]], location: LocationName) -> bool:
    return bool(rows) and all(bool(row.get(location)) for row in rows)


def _read_json(path: Path, *, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return dict(default)
    return loaded if isinstance(loaded, dict) else dict(default)


def _ensure_registry(root: dict[str, Any]) -> dict[str, Any]:
    root = dict(root)
    root["schema_version"] = int(root.get("schema_version") or 4)
    root.setdefault("active_account_key", None)
    root.setdefault("previous_active_account_key", None)
    root.setdefault("active_account_activated_at_ms", None)
    if not isinstance(root.get("accounts"), list):
        root["accounts"] = []
    return root


def _account_map(root: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in root.get("accounts", []):
        if not isinstance(item, dict):
            continue
        key = str(item.get("account_key") or "").strip()
        if key:
            result[key] = dict(item)
    return result


def _upsert_account(root: dict[str, Any], account: dict[str, Any]) -> None:
    root = _ensure_registry(root)
    key = str(account.get("account_key") or "").strip()
    accounts = root["accounts"]
    for index, item in enumerate(accounts):
        if isinstance(item, dict) and item.get("account_key") == key:
            accounts[index] = dict(account)
            return
    accounts.append(dict(account))


def _remove_account(root: dict[str, Any], account_key: str, *, clear_active: bool) -> bool:
    before = len(root.get("accounts", []))
    root["accounts"] = [
        item
        for item in root.get("accounts", [])
        if not (isinstance(item, dict) and item.get("account_key") == account_key)
    ]
    removed = len(root["accounts"]) < before
    if clear_active:
        if root.get("active_account_key") == account_key:
            root["active_account_key"] = None
            root["active_account_activated_at_ms"] = None
        if root.get("previous_active_account_key") == account_key:
            root["previous_active_account_key"] = None
    return removed


def _remove_equivalent_backup_copies(
    root: dict[str, Any],
    *,
    source_key: str,
    source_identity: tuple[str, ...],
    backup_dir: Path,
) -> None:
    if source_identity[0] == "key":
        return
    backup_map = _account_map(root)
    for key in _ordered_unique([*backup_map, *_snapshot_keys(backup_dir)]):
        if key == source_key:
            continue
        identity = _identity_for_key(
            key,
            live_row=None,
            backup_row=backup_map.get(key),
            live_dir=Path("__codexneo_no_live_dir__"),
            backup_dir=backup_dir,
        )
        if identity != source_identity:
            continue
        _remove_account(root, key, clear_active=False)
        _delete_snapshot(backup_dir, key)


def _is_active(root: dict[str, Any], account_key: str) -> bool:
    return root.get("active_account_key") == account_key


def _snapshot_keys(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return _ordered_unique(account_key_from_snapshot(path) for path in sorted(directory.glob("*.auth.json")))


def _identity_for_key(
    account_key: str,
    *,
    live_row: dict[str, Any] | None,
    backup_row: dict[str, Any] | None,
    live_dir: Path,
    backup_dir: Path,
) -> tuple[str, ...]:
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
    row = live_row or backup_row
    email = str((row or {}).get("email") or (row or {}).get("selector") or "").strip().lower()
    return ("email", email) if email else ("key", account_key)


def _ordered_unique(values) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _first_preferred_key(keys: list[str], preferred: str) -> str | None:
    if preferred in keys:
        return preferred
    return keys[0] if keys else None


def _snapshot_path(directory: Path, account_key: str) -> Path:
    return preferred_snapshot_path(directory, account_key)


def _delete_snapshot(directory: Path, account_key: str) -> bool:
    existed = existing_snapshot_path(directory, account_key) is not None
    delete_snapshot_files(directory, account_key)
    return existed


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
