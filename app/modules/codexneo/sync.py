from __future__ import annotations

import asyncio
import hashlib
import json
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.auth import DEFAULT_EMAIL, claims_from_auth, extract_id_token_claims, parse_auth_json
from app.core.config.settings import get_settings as get_app_settings
from app.core.plan_types import normalize_account_plan_type
from app.core.usage.quota import apply_usage_quota
from app.db.models import Account, AccountStatus, UsageHistory
from app.db.session import get_background_session
from app.modules.accounts.repository import AccountsRepository
from app.modules.accounts.service import AccountsService
from app.modules.codexneo.command_runner import run_codex_auth_command
from app.modules.codexneo.home import resolve_configured_codex_home
from app.modules.codexneo.locations import CodexNeoAccountLocationService, register_auth_snapshot_locally
from app.modules.codexneo.snapshots import account_key_from_snapshot, existing_snapshot_path
from app.modules.usage.repository import AdditionalUsageRepository, UsageRepository
from app.modules.usage.updater import UsageUpdater

_CODEXGO_ROOT_STATE_FILENAME = "codexgo-root-state.json"
_CODEXGO_ROOT_STATE_LOCK = asyncio.Lock()


@dataclass(frozen=True, slots=True)
class CodexNeoSyncResult:
    success: bool
    message: str
    count: int = 0


class CodexNeoAccountsSyncService:
    def __init__(
        self,
        *,
        codex_home: Path | None = None,
        data_dir: Path | None = None,
        command_runner=run_codex_auth_command,
    ) -> None:
        self._codex_home = (codex_home or resolve_configured_codex_home()).resolve()
        self._data_dir = data_dir or get_app_settings().data_dir
        self._command_runner = command_runner

    async def import_auth_json_to_accounts(self, raw: bytes) -> CodexNeoSyncResult:
        try:
            parse_auth_json(raw)
        except Exception:
            return CodexNeoSyncResult(success=False, message="Auth snapshot is not supported by Accounts import")
        async with get_background_session() as session:
            service = AccountsService(AccountsRepository(session))
            try:
                response = await service.import_account(raw)
            except Exception:
                return CodexNeoSyncResult(success=False, message="Accounts import failed")
        return CodexNeoSyncResult(
            success=True,
            message=f"Synced account {response.account_id} into Accounts",
            count=1,
        )

    async def import_folder_to_accounts(self, path: Path) -> CodexNeoSyncResult:
        imported = 0
        skipped = 0
        for candidate in sorted(path.rglob("*.json")):
            raw = candidate.read_bytes()
            result = await self.import_auth_json_to_accounts(raw)
            if result.success:
                imported += result.count or 1
            else:
                skipped += 1
        if imported == 0 and skipped == 0:
            return CodexNeoSyncResult(success=True, message="No JSON auth snapshots found", count=0)
        return CodexNeoSyncResult(
            success=imported > 0,
            message=f"Synced {imported} account(s) into Accounts; skipped {skipped}",
            count=imported,
        )

    async def sync_codex_home_to_accounts(self) -> CodexNeoSyncResult:
        async with codexgo_root_state_guard():
            return await self._sync_codex_home_to_accounts_unlocked()

    async def _sync_codex_home_to_accounts_unlocked(self) -> CodexNeoSyncResult:
        candidates = _discover_auth_snapshots(self._codex_home, self._data_dir)
        imported = 0
        skipped = 0
        live_backup_keys: list[str] = []
        seen_identities: set[tuple[str, str, str, str] | tuple[str, str]] = set()
        async with get_background_session() as session:
            repo = AccountsRepository(session)
            service = AccountsService(repo)
            for candidate in candidates:
                try:
                    auth = parse_auth_json(candidate.path.read_bytes())
                    claims = claims_from_auth(auth)
                except Exception:
                    skipped += 1
                    continue
                identity = _auth_identity(claims, candidate.path)
                if identity in seen_identities:
                    skipped += 1
                    continue
                seen_identities.add(identity)
                try:
                    response = await service.import_account(
                        candidate.path.read_bytes(),
                        preserve_unknown_workspace_duplicates=False,
                    )
                except Exception:
                    skipped += 1
                    continue
                imported += 1
                if candidate.source == "codex" and candidate.account_key:
                    live_backup_keys.append(candidate.account_key)
                elif candidate.source == "root":
                    live_backup_keys.append(response.account_id)
            await repo.consolidate_generated_copy_duplicates()

        backup_message = ""
        if live_backup_keys:
            location_service = CodexNeoAccountLocationService(codex_home=self._codex_home, data_dir=self._data_dir)
            backup_result = location_service.ensure_backup_present(live_backup_keys)
            location_service.refresh_bulk_states()
            backup_message = f"; Backup: {backup_result.message}"

        if imported == 0 and skipped == 0:
            return CodexNeoSyncResult(success=True, message="No Codex Home auth snapshots found", count=0)
        return CodexNeoSyncResult(
            success=True,
            message=(
                f"Synced {imported} unique account snapshot(s) into Accounts; "
                f"skipped {skipped}{backup_message}"
            ),
            count=imported,
        )

    async def sync_all_accounts(self) -> CodexNeoSyncResult:
        async with codexgo_root_state_guard():
            return await self._sync_all_accounts_unlocked()

    async def _sync_all_accounts_unlocked(self) -> CodexNeoSyncResult:
        inbound = await self._sync_codex_home_to_accounts_unlocked()
        existing_identities = _snapshot_identities(
            _discover_auth_snapshots(self._codex_home, self._data_dir),
            include_root=False,
        )
        tracked_codexgo_identities = _tracked_codexgo_root_fingerprints(self._data_dir)
        registered = 0
        skipped = 0
        async with get_background_session() as session:
            repo = AccountsRepository(session)
            await repo.consolidate_generated_copy_duplicates()
            accounts = await repo.list_accounts(refresh_existing=True)
            service = AccountsService(repo)
            for account in accounts:
                identity = _account_identity(account)
                if identity in existing_identities:
                    continue
                if _identity_fingerprint(identity) in tracked_codexgo_identities:
                    skipped += 1
                    continue
                if account.status in {AccountStatus.REAUTH_REQUIRED, AccountStatus.DEACTIVATED}:
                    skipped += 1
                    continue
                export = await service.export_auth(account.id)
                if export is None:
                    skipped += 1
                    continue
                raw = export.codex_auth_json.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8")
                result = await self.register_auth_json_to_codex_home(raw)
                if result.success:
                    registered += 1
                    existing_identities.add(identity)
                else:
                    skipped += 1
        master_count = await self.refresh_master_registry()
        return CodexNeoSyncResult(
            success=inbound.success,
            message=(
                f"CodexNeo -> Accounts: {inbound.message}; "
                f"Accounts -> Codex Home: registered {registered}, skipped {skipped}; "
                f"Master list: {master_count} account(s)"
            ),
            count=master_count,
        )

    async def _retire_tracked_codexgo_root_accounts(self) -> int:
        state = _read_codexgo_root_state(self._data_dir)
        retired_fingerprints = set(_string_list(state.get("retired_identity_sha256")))
        if not retired_fingerprints:
            return 0

        preserved_fingerprints: set[str] = set()
        for candidate in _discover_auth_snapshots(self._codex_home, self._data_dir):
            if candidate.source == "root":
                continue
            try:
                fingerprint = _auth_fingerprint(candidate.path.read_bytes())
            except Exception:
                continue
            if fingerprint in retired_fingerprints:
                preserved_fingerprints.add(fingerprint)

        removable_fingerprints = retired_fingerprints - preserved_fingerprints

        deleted = 0
        async with get_background_session() as session:
            repo = AccountsRepository(session)
            accounts = await repo.list_accounts(refresh_existing=True, include_generated_copies=True)
            for account in accounts:
                if _identity_fingerprint(_account_identity(account)) not in removable_fingerprints:
                    continue
                if await repo.delete(account.id, delete_history=False):
                    deleted += 1

        state["retired_identity_sha256"] = []
        _write_codexgo_root_state(self._data_dir, state)
        return deleted

    async def refresh_master_registry(self) -> int:
        entries: dict[tuple[str, str, str, str] | tuple[str, str], dict[str, Any]] = {}
        for candidate in _discover_auth_snapshots(self._codex_home, self._data_dir):
            try:
                auth = parse_auth_json(candidate.path.read_bytes())
                claims = claims_from_auth(auth)
            except Exception:
                continue
            identity = _auth_identity(claims, candidate.path)
            entry = _master_entry(entries, identity)
            entry["account_id"] = entry["account_id"] or claims.account_id
            entry["email"] = entry["email"] or claims.email
            entry["workspace_id"] = entry["workspace_id"] or claims.workspace_id
            entry["workspace_label"] = entry["workspace_label"] or claims.workspace_label
            entry["plan"] = entry["plan"] or claims.plan_type
            _add_unique(entry["sources"], candidate.source)
            if candidate.account_key:
                _add_unique(entry["account_keys"], candidate.account_key)

        async with get_background_session() as session:
            repo = AccountsRepository(session)
            accounts = await repo.list_accounts(refresh_existing=True)
            for account in accounts:
                identity = _account_identity(account)
                entry = _master_entry(entries, identity)
                entry["codex_ib_account_id"] = entry["codex_ib_account_id"] or account.id
                entry["account_id"] = entry["account_id"] or account.chatgpt_account_id
                entry["email"] = entry["email"] or account.email
                entry["workspace_id"] = entry["workspace_id"] or account.workspace_id
                entry["workspace_label"] = entry["workspace_label"] or account.workspace_label
                entry["plan"] = entry["plan"] or account.plan_type
                _add_unique(entry["sources"], "codex_ib")

        payload = {
            "schema_version": 1,
            "accounts": sorted(
                entries.values(),
                key=lambda entry: ((entry.get("email") or ""), str(entry["identity"])),
            ),
        }
        _write_json_atomic(self._master_registry_path(), payload)
        return len(payload["accounts"])

    async def auto_delete_free_reauth_plan_drift_accounts(self) -> CodexNeoSyncResult:
        previous_paid_claims: list[tuple[str, Any]] = []
        for candidate in _discover_auth_snapshots(self._codex_home, self._data_dir):
            if not candidate.account_key:
                continue
            try:
                claims = claims_from_auth(parse_auth_json(candidate.path.read_bytes()))
            except Exception:
                continue
            if normalize_account_plan_type(claims.plan_type) in {"pro", "plus"}:
                previous_paid_claims.append((candidate.account_key, claims))
        if not previous_paid_claims:
            return CodexNeoSyncResult(success=True, message="Auto delete found 0 eligible account(s)", count=0)

        keys_to_delete: list[str] = []
        account_ids_to_delete: set[str] = set()
        async with get_background_session() as session:
            repo = AccountsRepository(session)
            accounts = await repo.list_accounts(refresh_existing=True, include_generated_copies=True)
            for account in accounts:
                if account.status in {AccountStatus.RATE_LIMITED, AccountStatus.PAUSED}:
                    continue
                if (
                    normalize_account_plan_type(account.plan_type) != "free"
                    and account.status != AccountStatus.REAUTH_REQUIRED
                ):
                    continue
                matched_keys = [
                    key
                    for key, claims in previous_paid_claims
                    if _claims_match_account(claims, account)
                ]
                if not matched_keys:
                    continue
                account_ids_to_delete.add(account.id)
                for key in matched_keys:
                    _add_unique(keys_to_delete, key)
        if not account_ids_to_delete or not keys_to_delete:
            return CodexNeoSyncResult(success=True, message="Auto delete found 0 eligible account(s)", count=0)

        location_result = self._delete_with_local_registry_fallback(keys_to_delete)
        if not location_result.success:
            return location_result

        deleted = 0
        async with get_background_session() as session:
            repo = AccountsRepository(session)
            for account_id in sorted(account_ids_to_delete):
                if await repo.delete(account_id, delete_history=False):
                    deleted += 1
        return CodexNeoSyncResult(
            success=True,
            message=(
                f"Auto-deleted {deleted} free/auth-required account(s); "
                f"removed {len(keys_to_delete)} CodexNeo source(s)"
            ),
            count=deleted,
        )

    async def auto_delete_quota_exceeded_weekly_exhausted_accounts(self) -> CodexNeoSyncResult:
        keys_to_delete: list[str] = []
        account_ids_to_delete: set[str] = set()
        async with get_background_session() as session:
            accounts_repo = AccountsRepository(session)
            usage_repo = UsageRepository(session)
            accounts = await accounts_repo.list_accounts(refresh_existing=True, include_generated_copies=True)
            primary_usage = await usage_repo.latest_by_account(
                "primary",
                account_ids=[account.id for account in accounts],
            )
            secondary_usage = await usage_repo.latest_by_account(
                "secondary",
                account_ids=[account.id for account in accounts],
            )
            for account in accounts:
                usage = secondary_usage.get(account.id)
                if usage is None or float(usage.used_percent) != 100.0:
                    continue
                if not _is_quota_exceeded_for_auto_delete(
                    account,
                    primary=primary_usage.get(account.id),
                    secondary=usage,
                ):
                    continue
                matched_keys = _matching_codexneo_keys_for_account(
                    self._codex_home,
                    self._data_dir,
                    account,
                )
                if not matched_keys:
                    continue
                account_ids_to_delete.add(account.id)
                for key in matched_keys:
                    _add_unique(keys_to_delete, key)
        if not account_ids_to_delete or not keys_to_delete:
            return CodexNeoSyncResult(
                success=True,
                message="Auto delete found 0 eligible quota-exceeded account(s)",
                count=0,
            )

        location_result = self._delete_with_local_registry_fallback(keys_to_delete)
        if not location_result.success:
            return location_result

        deleted = 0
        async with get_background_session() as session:
            repo = AccountsRepository(session)
            for account_id in sorted(account_ids_to_delete):
                if await repo.delete(account_id, delete_history=False):
                    deleted += 1
        return CodexNeoSyncResult(
            success=True,
            message=(
                f"Auto-deleted {deleted} quota-exceeded account(s); "
                f"removed {len(keys_to_delete)} CodexNeo source(s)"
            ),
            count=deleted,
        )

    async def register_auth_json_to_codex_home(self, raw: bytes) -> CodexNeoSyncResult:
        try:
            parse_auth_json(raw)
        except Exception:
            return CodexNeoSyncResult(success=False, message="Auth snapshot is not supported by Codex Home import")
        temp_path = self._data_dir / f"codexneo-sync-{os.getpid()}-{uuid4().hex}.auth.json"
        try:
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(raw)
            try:
                ok, output = await self._command_runner(["import", str(temp_path)], codex_home=str(self._codex_home))
            except Exception as exc:
                return CodexNeoSyncResult(
                    success=False,
                    message=f"Codex Home import failed: {_safe_summary(str(exc))}",
                )
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
        if ok:
            register_auth_snapshot_locally(self._codex_home, raw)
            return CodexNeoSyncResult(success=True, message="Registered account in Codex Home", count=1)
        try:
            register_auth_snapshot_locally(self._codex_home, raw)
        except Exception:
            return CodexNeoSyncResult(
                success=False,
                message=f"Codex Home import failed: {_safe_summary(output)}",
            )
        return CodexNeoSyncResult(
            success=True,
            message="Registered account in Codex Home with local registry fallback",
            count=1,
        )

    async def remove_account_from_codex_home(self, account: Account) -> CodexNeoSyncResult:
        keys = _matching_codex_keys_for_account(self._codex_home, account)
        cleanup_keys = _matching_codexneo_keys_for_account(self._codex_home, self._data_dir, account)
        if not cleanup_keys:
            return CodexNeoSyncResult(success=True, message="No matching CodexNeo account was found", count=0)
        if not keys:
            cleanup_result = self._delete_with_local_registry_fallback(cleanup_keys)
            return CodexNeoSyncResult(
                success=cleanup_result.success,
                message=(
                    "No matching Codex Home account was found; cleaned matching CodexNeo backup"
                    if cleanup_result.success
                    else cleanup_result.message
                ),
                count=cleanup_result.count,
            )
        if is_codex_registry_schema_newer_than_supported(self._codex_home):
            return self._delete_with_local_registry_fallback(cleanup_keys)
        for key in keys:
            try:
                ok, output = await self._command_runner(["remove", key], codex_home=str(self._codex_home))
            except Exception as exc:
                return CodexNeoSyncResult(
                    success=False,
                    message=f"Codex Home remove failed: {_safe_summary(str(exc))}",
                )
            if not ok:
                if is_codex_auth_schema_unsupported(output):
                    return self._delete_with_local_registry_fallback(cleanup_keys)
                return CodexNeoSyncResult(
                    success=False,
                    message=f"Codex Home remove failed: {_safe_summary(output)}",
                )
        cleanup_result = self._delete_with_local_registry_fallback(cleanup_keys)
        if not cleanup_result.success:
            return cleanup_result
        return CodexNeoSyncResult(
            success=True,
            message=f"Removed {len(keys)} Codex Home account(s) and cleaned matching CodexNeo backup",
            count=len(keys),
        )

    async def delete_codex_keys_from_accounts(self, account_keys: list[str], *, codex_home: Path) -> CodexNeoSyncResult:
        deleted = 0
        skipped = 0
        async with get_background_session() as session:
            repo = AccountsRepository(session)
            accounts = await repo.list_accounts(refresh_existing=True, include_generated_copies=True)
            for key in account_keys:
                snapshot = existing_snapshot_path(codex_home / "accounts", key)
                if snapshot is None:
                    skipped += 1
                    continue
                try:
                    auth = parse_auth_json(snapshot.read_bytes())
                except Exception:
                    skipped += 1
                    continue
                claims = claims_from_auth(auth)
                matching_ids = _matching_account_ids(accounts, claims)
                if not matching_ids:
                    skipped += 1
                    continue
                for account_id in matching_ids:
                    if await repo.delete(account_id, delete_history=False):
                        deleted += 1
        return CodexNeoSyncResult(
            success=True,
            message=f"Deleted {deleted} matching Accounts row(s); skipped {skipped}",
            count=deleted,
        )

    async def refresh_selected_account_usage(self, account_keys: list[str]) -> CodexNeoSyncResult:
        selected_keys = [key for key in dict.fromkeys(account_keys) if key]
        if not selected_keys:
            return CodexNeoSyncResult(success=False, message="Select at least one account to refresh", count=0)

        sync_result = await self.sync_codex_home_to_accounts()
        selected_claims = [
            claims
            for key in selected_keys
            if (claims := _claims_for_account_key(self._codex_home, self._data_dir, key)) is not None
        ]
        if not selected_claims:
            return CodexNeoSyncResult(success=False, message="No selected auth snapshots were found", count=0)

        refreshed = 0
        skipped = 0
        async with get_background_session() as session:
            repo = AccountsRepository(session)
            await repo.consolidate_generated_copy_duplicates()
            accounts = await repo.list_accounts(refresh_existing=True)
            usage_repo = UsageRepository(session)
            additional_usage_repo = AdditionalUsageRepository(session)
            updater = UsageUpdater(usage_repo, repo, additional_usage_repo)
            selected_account_ids: set[str] = set()
            for claims in selected_claims:
                matching_ids = _matching_account_ids(accounts, claims)
                if not matching_ids:
                    skipped += 1
                    continue
                selected_account_ids.update(matching_ids)
            for account in accounts:
                if account.id not in selected_account_ids:
                    continue
                if await updater.force_refresh(account):
                    refreshed += 1
                else:
                    skipped += 1

        message = f"Refreshed {refreshed} selected account(s); skipped {skipped}"
        if sync_result.message:
            message = f"{message}; Sync: {sync_result.message}"
        return CodexNeoSyncResult(success=True, message=message, count=refreshed)

    def _master_registry_path(self) -> Path:
        return self._data_dir / "codexneo-master-registry.json"

    def _delete_with_local_registry_fallback(self, keys: list[str]) -> CodexNeoSyncResult:
        location_result = CodexNeoAccountLocationService(
            codex_home=self._codex_home,
            data_dir=self._data_dir,
        ).delete_everywhere(keys)
        return CodexNeoSyncResult(
            success=location_result.success,
            message=(
                f"Removed {len(keys)} managed account source(s) with local registry fallback"
                if location_result.success
                else f"Codex Home remove fallback failed: {location_result.message}"
            ),
            count=len(keys) if location_result.success else 0,
        )


def _matching_codex_keys_for_account(codex_home: Path, account: Account) -> list[str]:
    accounts_dir = codex_home / "accounts"
    if not accounts_dir.is_dir():
        return []
    keys: list[str] = []
    for snapshot in sorted(accounts_dir.glob("*.auth.json")):
        try:
            auth = parse_auth_json(snapshot.read_bytes())
        except Exception:
            continue
        claims = claims_from_auth(auth)
        if _claims_match_account(claims, account):
            keys.append(account_key_from_snapshot(snapshot))
    return keys


def _matching_codexneo_keys_for_account(codex_home: Path, data_dir: Path, account: Account) -> list[str]:
    keys: list[str] = []
    for candidate in _discover_auth_snapshots(codex_home, data_dir):
        if not candidate.account_key:
            continue
        try:
            auth = parse_auth_json(candidate.path.read_bytes())
        except Exception:
            continue
        claims = claims_from_auth(auth)
        if _claims_match_account(claims, account):
            _add_unique(keys, candidate.account_key)
    return keys


def _matching_backup_keys_for_account(data_dir: Path, account: Account) -> list[str]:
    backup_dir = data_dir / "account-backups"
    if not backup_dir.is_dir():
        return []
    keys: list[str] = []
    for snapshot in sorted(backup_dir.glob("*.auth.json")):
        try:
            auth = parse_auth_json(snapshot.read_bytes())
        except Exception:
            continue
        claims = claims_from_auth(auth)
        if _claims_match_account(claims, account):
            _add_unique(keys, account_key_from_snapshot(snapshot))
    return keys


def _is_quota_exceeded_for_auto_delete(
    account: Account,
    *,
    primary: UsageHistory | None,
    secondary: UsageHistory,
) -> bool:
    if account.status == AccountStatus.QUOTA_EXCEEDED:
        return True
    if account.status != AccountStatus.ACTIVE:
        return False
    effective_status, _, _ = apply_usage_quota(
        status=account.status,
        primary_used=float(primary.used_percent) if primary is not None else None,
        primary_reset=primary.reset_at if primary is not None else None,
        primary_window_minutes=primary.window_minutes if primary is not None else None,
        runtime_reset=float(account.reset_at) if account.reset_at is not None else None,
        secondary_used=float(secondary.used_percent),
        secondary_reset=secondary.reset_at,
        credits_has=secondary.credits_has,
        credits_unlimited=secondary.credits_unlimited,
        credits_balance=secondary.credits_balance,
    )
    return effective_status == AccountStatus.QUOTA_EXCEEDED


def _matching_account_ids(accounts: list[Account], claims: Any) -> list[str]:
    return [account.id for account in accounts if _claims_match_account(claims, account)]


def _snapshot_identities(
    candidates: list[_AuthSnapshotCandidate],
    *,
    include_root: bool = True,
) -> set[tuple[str, str, str, str] | tuple[str, str]]:
    identities: set[tuple[str, str, str, str] | tuple[str, str]] = set()
    for candidate in candidates:
        if not include_root and candidate.source == "root":
            continue
        try:
            claims = claims_from_auth(parse_auth_json(candidate.path.read_bytes()))
        except Exception:
            continue
        identities.add(_auth_identity(claims, candidate.path))
    return identities


def _account_identity(account: Account) -> tuple[str, str, str, str]:
    return (
        account.chatgpt_account_id or "",
        account.email or "",
        account.workspace_id or "",
        account.workspace_label or "",
    )


def _master_entry(
    entries: dict[tuple[str, str, str, str] | tuple[str, str], dict[str, Any]],
    identity: tuple[str, str, str, str] | tuple[str, str],
) -> dict[str, Any]:
    if identity not in entries:
        entries[identity] = {
            "identity": "|".join(identity),
            "account_id": None,
            "codex_ib_account_id": None,
            "email": None,
            "workspace_id": None,
            "workspace_label": None,
            "plan": None,
            "sources": [],
            "account_keys": [],
        }
    return entries[identity]


def _add_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _claims_for_account_key(codex_home: Path, data_dir: Path, account_key: str) -> Any | None:
    for directory in (codex_home / "accounts", data_dir / "account-backups"):
        snapshot = existing_snapshot_path(directory, account_key)
        if snapshot is None:
            continue
        try:
            return claims_from_auth(parse_auth_json(snapshot.read_bytes()))
        except Exception:
            continue
    return None


def _claims_match_account(claims: Any, account: Account) -> bool:
    if claims.email and account.email != claims.email:
        return False
    if claims.account_id and account.chatgpt_account_id and account.chatgpt_account_id != claims.account_id:
        return False
    if claims.workspace_id and account.workspace_id and account.workspace_id != claims.workspace_id:
        return False
    if claims.workspace_label and account.workspace_label and account.workspace_label != claims.workspace_label:
        return False
    return bool(claims.email or claims.account_id)


def _safe_summary(output: str) -> str:
    first = output.splitlines()[0] if output else ""
    return first[:300] or "codex-auth command failed"


def is_codex_auth_schema_unsupported(output: str) -> bool:
    normalized = output.lower()
    return (
        "registry schema version" in normalized
        and "newer than this codex-auth binary supports" in normalized
    )


def is_codex_registry_schema_newer_than_supported(codex_home: Path) -> bool:
    registry_path = codex_home / "accounts" / "registry.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    version = registry.get("schema_version") if isinstance(registry, dict) else None
    return isinstance(version, int) and version >= 5


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


@asynccontextmanager
async def codexgo_root_state_guard():
    async with _CODEXGO_ROOT_STATE_LOCK:
        yield


def record_codexgo_root_replacement(
    data_dir: Path,
    *,
    current_raw: bytes,
) -> None:
    current_fingerprint = _auth_fingerprint(current_raw)
    if current_fingerprint is None:
        return
    state = _read_codexgo_root_state(data_dir)
    retired = _string_list(state.get("retired_identity_sha256"))
    tracked_fingerprint = state.get("active_identity_sha256")
    if (
        isinstance(tracked_fingerprint, str)
        and tracked_fingerprint
        and tracked_fingerprint != current_fingerprint
        and tracked_fingerprint not in retired
    ):
        retired.append(tracked_fingerprint)
    state.update(
        {
            "schema_version": 1,
            "active_identity_sha256": current_fingerprint,
            "retired_identity_sha256": retired,
        }
    )
    _write_codexgo_root_state(data_dir, state)


def _tracked_codexgo_root_fingerprints(data_dir: Path) -> set[str]:
    state = _read_codexgo_root_state(data_dir)
    tracked = set(_string_list(state.get("retired_identity_sha256")))
    active = state.get("active_identity_sha256")
    if isinstance(active, str) and active:
        tracked.add(active)
    return tracked


def _read_codexgo_root_state(data_dir: Path) -> dict[str, Any]:
    path = data_dir / _CODEXGO_ROOT_STATE_FILENAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"schema_version": 1, "active_identity_sha256": None, "retired_identity_sha256": []}
    return payload if isinstance(payload, dict) else {}


def _write_codexgo_root_state(data_dir: Path, state: dict[str, Any]) -> None:
    _write_json_atomic(data_dir / _CODEXGO_ROOT_STATE_FILENAME, state)


def codexgo_auth_identity_fingerprint(raw: bytes | None) -> str | None:
    return _auth_fingerprint(raw)


def _auth_fingerprint(raw: bytes | None) -> str | None:
    if raw is None:
        return None
    try:
        claims = claims_from_auth(parse_auth_json(raw))
        identity = (
            claims.account_id or "",
            claims.email or "",
            claims.workspace_id or "",
            claims.workspace_label or "",
        )
    except Exception:
        try:
            payload = json.loads(raw)
            tokens = payload.get("tokens") if isinstance(payload, dict) else None
            if not isinstance(tokens, dict):
                return None
            id_token = tokens.get("id_token") or tokens.get("idToken")
            token_claims = extract_id_token_claims(id_token) if isinstance(id_token, str) else None
            identity = (
                str(tokens.get("account_id") or tokens.get("accountId") or ""),
                token_claims.email if token_claims and token_claims.email else "",
                token_claims.workspace_id if token_claims and token_claims.workspace_id else "",
                token_claims.workspace_label if token_claims and token_claims.workspace_label else "",
            )
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            return None
    return _identity_fingerprint(identity) if any(identity) else None


def _identity_fingerprint(identity: tuple[str, ...]) -> str:
    normalized = list(identity)
    if len(normalized) > 1 and normalized[1] == DEFAULT_EMAIL:
        normalized[1] = ""
    encoded = json.dumps(normalized, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


@dataclass(frozen=True, slots=True)
class _AuthSnapshotCandidate:
    path: Path
    source: str
    account_key: str | None = None


def _discover_auth_snapshots(codex_home: Path, data_dir: Path) -> list[_AuthSnapshotCandidate]:
    candidates: list[_AuthSnapshotCandidate] = []
    seen_paths: set[Path] = set()

    def add(path: Path, *, source: str, account_key: str | None = None) -> None:
        resolved = path.resolve()
        if resolved in seen_paths or not path.is_file():
            return
        seen_paths.add(resolved)
        candidates.append(_AuthSnapshotCandidate(path=path, source=source, account_key=account_key))

    add(codex_home / "auth.json", source="root")
    accounts_dir = codex_home / "accounts"
    if accounts_dir.is_dir():
        for path in sorted(accounts_dir.glob("*.auth.json")):
            add(path, source="codex", account_key=account_key_from_snapshot(path))
        for path in sorted(accounts_dir.glob("*.json")):
            if path.name == "registry.json" or path.name.endswith(".auth.json"):
                continue
            add(path, source="codex-json", account_key=path.stem)
    backup_dir = data_dir / "account-backups"
    if backup_dir.is_dir():
        for path in sorted(backup_dir.glob("*.auth.json")):
            add(path, source="backup", account_key=account_key_from_snapshot(path))
    return candidates


def _auth_identity(claims: Any, path: Path) -> tuple[str, str, str, str] | tuple[str, str]:
    if claims.account_id or claims.email or claims.workspace_id or claims.workspace_label:
        return (
            claims.account_id or "",
            claims.email or "",
            claims.workspace_id or "",
            claims.workspace_label or "",
        )
    return ("path", str(path.resolve()).lower())
