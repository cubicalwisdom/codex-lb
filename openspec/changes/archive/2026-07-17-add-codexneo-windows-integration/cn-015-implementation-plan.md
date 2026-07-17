# CN-015 Codex Home Account Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to implement this plan task-by-task.

**Goal:** Sync accounts created by CodexGO/native Codex in the configured Codex Home into Codex IB's encrypted Accounts database and app-owned backup store, without adding any Codex login flow.

**Architecture:** Add a discovery sync method to the existing CodexNeo sync service. CodexNeo account loads and CodexGO use/refresh calls invoke that method after local Codex Home state is read or written. The existing Accounts-tab import path continues to register uploaded accounts into the configured Codex Home so CodexNeo sees them.

**Tech Stack:** FastAPI, SQLAlchemy async sessions, existing `AccountsService`, existing CodexNeo location/backup service, pytest.

---

### Task 1: Codex Home And Backup Discovery Sync

**Files:**
- Modify: `app/modules/codexneo/sync.py`
- Test: `tests/unit/test_codexneo_account_discovery_sync.py`

- [x] Write failing tests that create a temporary Codex Home with `accounts/<key>.auth.json`, `accounts/registry.json`, and root `auth.json`, then assert the sync imports valid snapshots into the Accounts database and skips invalid/non-auth JSON without leaking token text.
- [x] Write failing tests that create a backup-only account under `account-backups/<key>.auth.json` plus `backup-registry.json`, then assert the sync imports the backup snapshot into the Accounts database.
- [x] Implement snapshot discovery for root `auth.json`, `accounts/*.auth.json`, parseable `accounts/*.json`, and `account-backups/*.auth.json`.
- [x] Use `AccountsService.import_account(raw)` for valid snapshots so existing identity and duplicate rules remain authoritative.
- [x] Copy live Codex Home snapshots into Backup through `CodexNeoAccountLocationService` so newly discovered CodexGO accounts get an app-owned backup.

### Task 2: Trigger Sync From CodexNeo Refresh And CodexGO Auth

**Files:**
- Modify: `app/modules/codexneo/accounts.py`
- Modify: `app/modules/codexneo/api.py`
- Modify: `app/modules/codexneo/service.py`
- Test: `tests/integration/test_codexneo_account_discovery_sync_api.py`

- [x] Write a failing API test where `GET /api/codexneo/accounts` sees a Codex Home auth snapshot and the main `GET /api/accounts` response contains the same synced account.
- [x] Write a failing unit/API test where CodexGO auth use/refresh writes `auth.json`, invokes sync, and reports a safe sync summary.
- [x] Add an async account-load path for CodexNeo that runs discovery sync before returning account rows.
- [x] Wire `GET /api/codexneo/accounts` to the async load path.
- [x] Invoke sync after CodexGO use/refresh writes and validates root `auth.json`.

### Task 3: Verify And Restart Native Server

**Files:**
- Modify: `CODEXNEO_IMPLEMENTATION_LIST.md`
- Modify: `HANDOVER_CODEXNEO_INTEGRATION.md`
- Modify: `openspec/changes/add-codexneo-windows-integration/tasks.md`

- [x] Run focused pytest for the new sync tests and existing CodexNeo sync/import tests.
- [x] Run OpenSpec validation.
- [x] Run Ruff on touched backend files/tests.
- [x] Restart only the native codex-lb server if the live `127.0.0.1:2455` process needs the new code loaded.
- [x] Update this change's task list, implementation list, and handover with exact verification results.
