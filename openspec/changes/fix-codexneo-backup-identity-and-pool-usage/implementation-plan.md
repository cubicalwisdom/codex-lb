# CodexNeo Backup Identity and Pool Usage Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make Backup-all state, bulk messages, and quota display use the same canonical logical account identities shown in the CodexNeo table.

**Architecture:** Managed snapshot files are immutable identity authority; backup registry rows hold stable metadata only. Location operations deduplicate equivalent physical rows before acting. Usage history is loaded for the complete canonical Accounts set and then applied to both decorated and pool-only rows.

**Tech Stack:** FastAPI backend, SQLAlchemy async repositories, pytest, Ruff, OpenSpec.

---

### Task 1: Stable backup identity and logical bulk counts

**Files:**
- Modify: `tests/unit/test_codexneo_locations.py`
- Modify: `app/modules/codexneo/locations.py`

- [x] Add a failing test that backs up root account A, rotates root to B, and asserts `CodexHomeAccountService.load_accounts()` returns A and B once with A still `backup=True`.
- [x] Add a failing test with root B plus its backup row and backup-only A; call `set_bulk_default(location="backup", present=False)` and assert the message counts two logical accounts rather than three physical rows.
- [x] Run `uv run pytest tests/unit/test_codexneo_locations.py -q` and confirm the new assertions fail for identity drift/raw-row counting.
- [x] Add `_stable_backup_row()` to drop `auth_path`, `active`, `codex`, `backup`, and `codex_registered` before `_upsert_account()` writes Backup metadata.
- [x] Make `_identity_for_key()` and account discovery prefer an existing account-specific snapshot; use mutable `auth_path` only when no snapshot exists.
- [x] Add a location-row dedupe helper based on `_identity_for_key()` and use it in `set_bulk_default()`, `apply_bulk_defaults()`, and `refresh_bulk_states()`.
- [x] Re-run the focused location tests and confirm green.

### Task 2: Canonical pool-only usage

**Files:**
- Modify: `tests/unit/test_codexneo_accounts.py`
- Modify: `app/modules/codexneo/accounts.py`

- [x] Add a failing async test that imports an Accounts-only identity, writes primary/secondary usage, and asserts CodexNeo returns remaining percentages and `last_usage_at`.
- [x] Run that test and confirm it fails with empty usage windows.
- [x] Change the usage lookup id set to `{account.id for account in codex_ib_accounts}` and reuse those maps for filesystem-matched and pool-only rows.
- [x] Re-run the focused account test and confirm green.

### Task 3: Verify and stage

**Files:**
- Modify: `openspec/specs/codexneo-windows-integration/spec.md`
- Modify: `HANDOVER_CODEXNEO_INTEGRATION.md`
- Modify: `CODEXNEO_IMPLEMENTATION_LIST.md`
- Mirror: `app/modules/codexneo/accounts.py`, `app/modules/codexneo/locations.py`

- [x] Run `uv run pytest tests/unit/test_codexneo_locations.py tests/unit/test_codexneo_accounts.py -q`.
- [x] Run all CodexNeo unit/integration tests and scoped Ruff.
- [x] Run `npx --yes openspec validate fix-codexneo-backup-identity-and-pool-usage --strict` and `npx --yes openspec validate --specs`.
- [x] Mirror the two verified Python modules into `dist/CodexIB-Electron-Portable`, compare SHA-256 hashes, and run portable `py_compile`.
- [x] Do not restart or close the running portable app; report that activation requires the user's manual restart.
