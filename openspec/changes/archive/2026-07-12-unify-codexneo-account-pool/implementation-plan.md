# Unified CodexNeo Account Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make Codex LB Accounts the one durable pool for both CodexGO delivery paths and rebuild CodexNeo as its Accounts and Activity controller/views.

**Architecture:** Provider payloads and root-file changes enter one backend ingestion operation that normalizes identity, updates encrypted Accounts credentials, and writes one app-owned managed snapshot. CodexNeo reads decorated canonical pool rows rather than reconciling a second routing inventory. A new activity service combines safe Codex LB and CodexNeo events in one 24-hour store.

**Tech Stack:** FastAPI, SQLAlchemy async sessions, existing AccountsService and CodexNeo services, React/TypeScript, TanStack Query, Vitest, pytest.

## Global Constraints

- Do not change proxy routing, request execution, main Accounts-page behavior, dashboard behavior, or Electron launcher behavior.
- Do not restart Codex Desktop or the running portable app.
- Never expose access tokens, refresh tokens, buyer tokens, or raw auth JSON.
- Preserve aggregate usage statistics when an account is removed.
- Mirror verified runtime changes into `dist/CodexIB-Electron-Portable` only at the final delivery task.

---

### Task 1: Canonical provider ingestion

**Files:**
- Modify: `app/modules/codexneo/sync.py`
- Modify: `app/modules/codexneo/service.py`
- Modify: `app/modules/codexneo/locations.py`
- Test: `tests/unit/test_codexneo_account_discovery_sync.py`
- Test: `tests/unit/test_codexneo_service.py`

**Interfaces:**
- Consumes: a valid `bytes` auth payload from root-file discovery or `CodexGoAction` provider response.
- Produces: one normalized Accounts row plus one `account-backups/<account_key>.auth.json` snapshot per identity.

- [ ] Add failing tests for two different CodexGO provider responses and assert both identities remain in Accounts and Backup after the second response.
- [ ] Add a failing test for a root-only valid auth payload and assert sync writes its Backup snapshot before returning success.
- [ ] Replace root-retirement behavior with an ingestion helper that calls `AccountsService.import_account`, resolves the generated account key, and invokes `CodexNeoAccountLocationService.ensure_backup_present` using the root auth fallback.
- [ ] Update `apply_codexgo_auth` so the provider response is ingested through that helper before atomic root replacement completion is reported.
- [ ] Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_codexneo_account_discovery_sync.py tests\unit\test_codexneo_service.py -q`.

### Task 2: Backend-owned root reconciliation

**Files:**
- Create: `app/modules/codexneo/reconciler.py`
- Modify: `app/main.py`
- Modify: `app/modules/codexneo/schemas.py`
- Test: `tests/unit/test_codexneo_reconciler.py`

**Interfaces:**
- Produces: `CodexNeoRootReconciler.start()`, `stop()`, and `reconcile_once()`.
- Consumes: configured Codex Home, `CodexNeoAccountsSyncService`, and a safe fingerprint of root auth bytes.

- [ ] Add failing tests that mutate a temp root auth file between `reconcile_once()` calls and assert exactly one new durable pool/snapshot ingestion.
- [ ] Implement a cancellable periodic reconciler with a bounded interval and a last-successful-file fingerprint; skip invalid or unchanged files without logging token material.
- [ ] Start and stop the reconciler in FastAPI lifespan alongside existing CodexGO scheduler lifecycle hooks.
- [ ] Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_codexneo_reconciler.py tests\unit\test_codexneo_account_discovery_sync.py -q`.

### Task 3: Canonical decorated rows and safe deletion

**Files:**
- Modify: `app/modules/codexneo/accounts.py`
- Modify: `app/modules/codexneo/account_actions.py`
- Modify: `app/modules/codexneo/locations.py`
- Modify: `app/modules/codexneo/sync.py`
- Test: `tests/unit/test_codexneo_accounts.py`
- Test: `tests/unit/test_codexneo_locations.py`
- Test: `tests/unit/test_codexneo_import_export_actions.py`

**Interfaces:**
- Consumes: canonical Accounts rows and managed snapshot identity matching.
- Produces: one CodexNeo row per canonical pool identity and delete results that preserve aggregate usage history.

- [ ] Add failing tests where stale backup registry `auth_path` values point at root auth and assert all distinct valid snapshot identities still appear exactly once.
- [ ] Refactor CodexNeo row construction to begin with Accounts rows, then add provider/current-live/backup decoration matched by normalized auth identity rather than a mutable root path.
- [ ] Add failing tests for selected deletion proving pool row, Backup snapshot/registry, and app-managed Codex Home snapshot/registry are removed while `UsageHistory` remains retained/de-associated.
- [ ] Implement confirmation-backed delete action using existing write route guards; clear root auth only when the deleted identity is actually current-live; never restart Codex Desktop.
- [ ] Restrict quota auto-delete to rows whose latest successful secondary/weekly record explicitly reports zero remaining; reject null, missing, stale, and positive values.
- [ ] Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_codexneo_accounts.py tests\unit\test_codexneo_locations.py tests\unit\test_codexneo_import_export_actions.py -q`.

### Task 4: Import/export and combined activity backend

**Files:**
- Modify: `app/modules/codexneo/import_export.py`
- Modify: `app/modules/codexneo/activity_log.py`
- Modify: `app/modules/codexneo/activity_middleware.py`
- Modify: `app/modules/codexneo/api.py`
- Modify: `app/modules/codexneo/schemas.py`
- Test: `tests/unit/test_codexneo_import_export_actions.py`
- Test: `tests/unit/test_codexneo_activity_log.py`
- Test: `tests/integration/test_codexneo_upload_import_api.py`

**Interfaces:**
- Consumes: an import folder, an explicit export destination, selected account keys, and redacted Codex LB/CodexNeo events.
- Produces: import result counts, selected-export output, paged/filterable activity response, and 24-hour pruning.

- [ ] Add failing import tests proving every valid source file invokes canonical ingestion and receives a managed Backup snapshot.
- [ ] Add failing selected-export tests proving only checked canonical identities are written to an explicitly supplied destination.
- [ ] Add activity tests for component/source filters, secret redaction, a 24-hour cutoff, and cleanup without a read request.
- [ ] Replace bounded line-only activity storage with timestamped redacted event records and prune records older than `now - 24 hours` on append, query, and scheduled reconciliation.
- [ ] Route Codex LB safe request/routing/quota events and CodexNeo/provider events to the combined stream; exclude activity API self-logging.
- [ ] Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_codexneo_import_export_actions.py tests\unit\test_codexneo_activity_log.py tests\integration\test_codexneo_upload_import_api.py -q`.

### Task 5: CodexNeo Accounts and Activity UI

**Files:**
- Modify: `frontend/src/features/codexneo/components/codexneo-page.tsx`
- Modify: `frontend/src/features/codexneo/components/codexneo-page.test.tsx`
- Modify: `frontend/src/features/codexneo/hooks/use-codexneo.ts`
- Modify: `frontend/src/features/codexneo/api.ts`
- Modify: `frontend/src/features/codexneo/schemas.ts`
- Create: `frontend/src/features/codexneo/components/codexneo-activity-page.tsx`
- Create: `frontend/src/features/codexneo/components/codexneo-activity-page.test.tsx`

**Interfaces:**
- Consumes: canonical CodexNeo rows, selected account keys, import/export endpoints, and combined activity query.
- Produces: Accounts and Activity views with no duplicate pool table.

- [ ] Add failing component tests asserting OpenAI/Management log toggles are absent, Auth→API is embedded in Accounts, Set uses success styling, and Revert uses danger styling.
- [ ] Add failing tests for Select all, Refresh selected, Export selected, confirmation-gated Delete selected, separate import source/export destination controls, and row-level Switch / Switch & Restart.
- [ ] Implement the Accounts view as the sole CodexNeo pool view and invalidate both CodexNeo and main Accounts queries after mutations.
- [ ] Add failing Activity-view tests for a separate tab, scrollable event container, sticky filters/header, component/account/error filters, and visible 24-hour retention text.
- [ ] Implement the Activity view using the combined activity API; remove the inline CodexNeo activity panel and its stream toggles from provider settings.
- [ ] Run: `npm run test -- --run src/features/codexneo` and `npm run build` from `frontend`.

### Task 6: Verify, document, and mirror portable runtime

**Files:**
- Modify: `HANDOVER_CODEXNEO_INTEGRATION.md`
- Modify: `CODEXNEO_IMPLEMENTATION_LIST.md`
- Mirror: changed `app/**` and built frontend assets to `dist/CodexIB-Electron-Portable/**`

- [ ] Run strict validation: `npx --yes openspec validate unify-codexneo-account-pool --strict`.
- [ ] Run focused backend and frontend command sets from Tasks 1–5, then `ruff check` on changed Python files and `npx tsc -b` in `frontend`.
- [ ] Verify source/portable hashes for every mirrored runtime file and run portable backend syntax compilation without launching or restarting it.
- [ ] Update handover and implementation inventory with exact verification output, scope boundary, and manual restart note.
- [ ] Commit only the unified CodexNeo pool work on `codexneo-unified-pool`.

