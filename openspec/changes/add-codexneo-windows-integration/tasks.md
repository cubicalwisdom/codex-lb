# Tasks

## 1. Specification And Planning

- [x] Create OpenSpec proposal and delta specs.
- [x] Create implementation plan and root handover.
- [x] Validate OpenSpec with `openspec validate --specs`.

## 2. Backend

- [x] Add failing tests for settings persistence, provider config set/revert, CodexGO auth use/refresh, and scheduler behavior.
- [x] Implement CodexNeo service layer with encrypted buyer-token persistence.
- [x] Implement safe host-file writes with backups and atomic replacement.
- [x] Implement provider URL normalization and CodexGO auth validation.
- [x] Add dashboard API routes with existing auth/read-only guards.
- [x] Wire scheduler startup/shutdown into the FastAPI lifespan.

## 3. Frontend

- [x] Add failing tests for the CodexNeo page and read-only behavior.
- [x] Implement CodexNeo API client, hooks, and page controls.
- [x] Add `/codexneo` route and nav entry near APIs/Settings.

## 4. Verification

- [x] Run focused backend tests.
- [x] Run focused frontend tests.
- [x] Run frontend build/typecheck as supported by the repo.
- [x] Verify the page in a browser against the native dev server.
- [x] Update this task list and root handover with final verification results.
- [x] Restart the native `127.0.0.1:2455` server and verify `/api/codexneo` plus `/codexneo`.

## 5. CodexNeo Activity Log And Account Discovery

- [x] Add failing backend tests for activity log stream settings, append/read/clear/delete, and safe redaction.
- [x] Add failing backend tests for Codex Home registry account parsing and missing/invalid registry handling.
- [x] Implement backend activity log service and API routes.
- [x] Implement backend Codex Home account discovery service and API route.
- [x] Add failing frontend tests for activity log toggles/panel/clear and account table rendering.
- [x] Implement frontend activity log panel and account table.
- [x] Run OpenSpec validation, focused backend/frontend tests, typecheck/build, and browser smoke.
- [x] Update root handover and implementation list with final results.

## 6. Auth To API Restart Behavior

- [x] Add failing backend tests for restart invocation after successful Auth->API Set and Revert.
- [x] Add failing backend tests that config write/verification failure does not invoke restart.
- [x] Add failing backend tests that restart failure is reported in the action response and activity log.
- [x] Implement Codex Desktop restart abstraction with safe process matching and launch behavior.
- [x] Wire restart behavior into Auth->API Set/Revert after config verification.
- [x] Run OpenSpec validation, focused backend tests, Ruff, frontend checks if needed, and browser/API smoke.
- [x] Update root handover and implementation list with final results.

## 7. Codex Home Controls, Import/Export, And Account Actions

- [x] Add failing backend tests for Codex Home path save/reset/picker fallback behavior.
- [x] Add failing backend tests for timestamped export, selected export, import command routing, and safe summaries.
- [x] Add failing backend tests for account metadata actions, command-backed switch/delete, fake restart on switch-and-restart, and preferred API account persistence.
- [x] Implement backend Codex Home, import/export, account metadata, command runner, and account action services/routes.
- [x] Add failing frontend tests for Codex Home controls, import/export controls, selected account actions, and confirmation-gated destructive actions.
- [x] Implement frontend controls/actions with manual path fallback and confirmation prompts.
- [x] Run OpenSpec validation, focused backend/frontend tests, Ruff, typecheck/build, and read-only browser/API smoke without stopping or restarting Codex.
- [x] Update root handover and implementation list with final results.

## 8. Account Sync, Activity Log Polish, And Table Cleanup

- [x] Add failing backend tests for CodexNeo import syncing into the codex-lb Accounts database.
- [x] Add failing backend/API tests for Accounts-tab import/delete syncing with the configured Codex Home.
- [x] Add failing backend tests for CodexNeo delete syncing back to the codex-lb Accounts database.
- [x] Implement CodexNeo/Accounts two-way sync services and route wiring with safe status reporting.
- [x] Add failing frontend tests for CodexNeo account table cleanup and fixed-height scrollable Activity log.
- [x] Implement CodexNeo table cleanup, Activity log fixed-height scroll behavior, and cross-tab query invalidation.
- [x] Run OpenSpec validation, focused backend/frontend tests, Ruff, typecheck/build, and non-destructive browser/API smoke.
- [x] Update root handover and implementation list with final results.

## 9. Picker-backed Import/Export And Location Toggles

- [x] Add failing backend tests for import/export picker fallbacks and cancellation-safe responses.
- [x] Add failing backend tests for Codex/Backup row toggle safety, backup deletion, delete-everywhere behavior, and sticky bulk defaults.
- [x] Implement picker endpoints and path fallback behavior for Import file, Import folder, and Export all.
- [x] Implement app-owned backup store, Codex/Backup location service, row toggles, bulk defaults, and delete-everywhere integration.
- [x] Add failing frontend tests for picker-backed buttons, row Codex/Backup checkboxes, and Codex all/Backup all toggles.
- [x] Implement frontend controls, mutation wiring, and account table checkbox rendering.
- [x] Run OpenSpec validation, focused backend/frontend tests, Ruff, typecheck/build, and non-destructive browser/API smoke without stopping Codex.
- [x] Update root handover and implementation list with final results.

## 10. Browser Upload Import Fix

- [x] Diagnose the long-running Import folder overlay and identify the hidden backend Windows folder picker as the root cause.
- [x] Add failing backend upload endpoint tests for Import file and Import folder.
- [x] Add failing frontend tests for browser file/folder inputs when the import path box is empty.
- [x] Implement upload endpoints, browser picker wiring, and safe empty-path backend import responses.
- [x] Run focused backend/frontend tests, OpenSpec validation, Ruff, typecheck/build, and live smoke.
- [x] Restart the native `127.0.0.1:2455` server if needed and update root handover plus implementation list with final results.

## 11. Export All Native Snapshot Fix

- [x] Reproduce live Export all failure and identify the backend `codex-auth` subprocess boundary.
- [x] Confirm the installed `codex-auth` exposes no `export` command and Python subprocess was not resolving the Windows `.cmd` shim.
- [x] Add failing backend tests for native Export all snapshot copies and Windows codex-auth shim resolution.
- [x] Implement native Export all copying from Codex Home and app-owned Backup snapshots.
- [x] Implement codex-auth command runner shim resolution for the remaining import/switch/delete command paths.
- [x] Run focused and broad backend verification, OpenSpec validation, restart native server, and live Export all smoke.
- [x] Update root handover and implementation list with final results.

## 12. Refresh Action And Account Status Columns

- [x] Add failing backend tests for CodexNeo-style `Avail` and `Status / Last` formatting from registry usage data.
- [x] Add failing frontend tests that remove selected `Use API`, expose refresh controls, restore the `Avail` column, and show formatted status text.
- [x] Implement account availability/status formatting and relative timestamp handling.
- [x] Remove the selected-account Use API route/client/hook/button and replace the selected toolbar action with refresh.
- [x] Run focused and broad verification, rebuild/restart native server, and live-smoke the CodexNeo table.
- [x] Update root handover and implementation list with final results.

## 13. Codex Home Discovery Sync

- [x] Add failing backend tests for scanning configured Codex Home auth snapshots into the codex-lb Accounts database without a login flow.
- [x] Add failing backend tests for backup-only snapshots syncing into the codex-lb Accounts database.
- [x] Add failing API tests showing CodexNeo refresh makes Codex Home accounts appear in the main Accounts tab.
- [x] Implement discovery sync from Codex Home and app-owned Backup into AccountsService.
- [x] Trigger discovery sync from CodexNeo account refresh and after CodexGO use/refresh writes auth.
- [x] Run focused backend tests, OpenSpec validation, Ruff, restart native codex-lb if needed, and update root handover plus implementation list.

## 14. CodexGO Refresh UI And Idempotent Sync Fix

- [x] Add failing backend test proving repeated Codex Home discovery sync does not create duplicate Accounts `__copy` rows.
- [x] Add failing frontend hook test proving CodexGO Use auth and Refresh auth invalidate CodexNeo and Accounts queries.
- [x] Add failing frontend component test for aligned validity-date controls and non-wrapping account table actions.
- [x] Implement idempotent discovery sync that updates existing upstream account identity slots.
- [x] Implement CodexGO action query invalidation for CodexNeo and main Accounts data.
- [x] Implement selected-account toolbar and table layout fixes.
- [x] Run focused backend/frontend tests, OpenSpec validation, Ruff/typecheck/build, rendered browser smoke, restart native codex-lb if needed, and update root handover plus implementation list.

## 15. Audit Bug Fixes

- [x] Add failing backend test proving Export selected includes backup-only account snapshots.
- [x] Add failing backend test proving CodexNeo delete still syncs Accounts when the external remove command deletes live snapshots first.
- [x] Add failing backend test proving CodexNeo delete does not sync/delete Accounts rows if the external remove command fails.
- [x] Add failing backend tests proving real URL-safe base64-encoded Codex auth snapshot filenames are matched to raw registry account keys.
- [x] Implement selected-export lookup across live Codex Home and app-owned Backup.
- [x] Implement staged delete snapshots so Accounts sync runs only after successful external remove while preserving auth claims for matching.
- [x] Implement shared snapshot filename helpers for raw test filenames and encoded real Codex filenames.
- [x] Run focused and broad backend/frontend verification, Ruff, OpenSpec validation, typecheck/build, whitespace check, restart native codex-lb if needed, and update root handover plus implementation list.

## 16. Health Diagnostics

- [x] Add failing backend tests for safe CodexNeo health badges and degraded source handling.
- [x] Add failing frontend test for the CodexNeo health diagnostics panel and copy actions.
- [x] Implement backend diagnostics response without exposing tokens or auth JSON contents.
- [x] Implement CodexNeo page health badge panel with safe copy actions.
- [x] Run focused backend/frontend tests, OpenSpec validation, Ruff/typecheck/build, rendered browser smoke, restart native codex-lb if needed, and update root handover plus implementation list.

## 17. Codex/Backup Location Parity

- [x] Add failing backend tests for Windows-style `Codex all` / `Backup all` visible-table semantics.
- [x] Add failing backend test proving discovery sync does not back up live accounts when `Backup all` is off.
- [x] Implement Codex/Backup bulk state recomputation and remove manual opt-out behavior for Codex/Backup.
- [x] Gate discovery backup creation on the previous visible-table `Backup all` state.
- [x] Run focused backend/frontend tests, OpenSpec validation, Ruff/typecheck/build, rendered browser smoke, restart native codex-lb if needed, and update root handover plus implementation list.

## 18. Account Dedupe And CodexNeo UI Polish

- [x] Add failing backend tests for collapsing duplicate CodexNeo rows that share the same real auth identity across Codex Home and Backup snapshots.
- [x] Add failing backend tests for hiding generated Accounts `__copy` rows from list/routing candidates without deleting historical database rows.
- [x] Add failing backend tests for stronger CodexNeo `Status / Last` fallback when usage windows or Codex presence prove the row is fresh.
- [x] Add failing frontend tests for Select all, CodexGO interval minutes labeling, and Codex Home Accounts refresh feedback.
- [x] Implement non-destructive identity dedupe for CodexNeo and generated Accounts copy rows.
- [x] Implement CodexNeo status source precedence and UI refresh feedback.
- [x] Run focused and broad backend/frontend tests, OpenSpec validation, Ruff/typecheck/build, rendered browser smoke, restart native codex-lb if needed, and update root handover plus implementation list.

## 19. Follow-up Audit Fixes

- [x] Confirm Auth->API Set/Revert restart is intended runtime behavior and leave it unchanged.
- [x] Add failing backend tests for equivalent live/backup auth identity location toggles, generated-copy Accounts consolidation, invalid saved CodexGO interval fallback, and selected account refresh identity resolution.
- [x] Add failing frontend tests proving `Refresh selected` calls the selected refresh mutation.
- [x] Implement equivalent-key live/backup location handling, generated-copy consolidation with usage/history reassignment, invalid interval fallbacks for settings and health diagnostics, and selected usage refresh endpoint/hook wiring.
- [x] Run focused and broad backend/frontend tests, Ruff, OpenSpec validation, TypeScript, and update root handover plus implementation list.

## 20. Delete Selected And Master Sync

- [x] Add failing backend tests proving multi-selected CodexNeo delete calls `codex-auth remove` with one selector at a time and deletes live plus Backup locations after success.
- [x] Add failing backend test proving Accounts-tab delete uses one-selector remove behavior for multiple matching Codex Home keys.
- [x] Add failing backend test for explicit master sync from CodexNeo Codex Home/Backup into Codex IB and from Codex IB back into Codex Home with a token-free master registry.
- [x] Add failing API/frontend tests for `POST /api/codexneo/accounts/sync` and the CodexNeo `Sync` button.
- [x] Run broad backend/frontend verification, Ruff, OpenSpec validation, TypeScript/build, live smoke if needed, restart native codex-lb if needed, and update root handover plus implementation list.

## 21. Codex Registry Schema Compatibility Fallback

- [x] Add failing backend test proving Accounts-page delete falls back to local registry/snapshot deletion when `codex-auth remove` rejects a newer Codex registry schema.
- [x] Add failing backend test proving CodexNeo Delete selected uses the same local fallback for that compatibility failure.
- [x] Implement configured-registry schema pre-detection plus runtime fallback detection only for the registry-schema compatibility error, while keeping other remove failures safe.
- [x] Run focused and broad backend verification, Ruff, OpenSpec validation, restart native codex-lb if needed, and update root handover plus implementation list.

## 22. Backup-only Encoded Snapshot Delete

- [x] Add failing backend test proving backup-only account keys that require encoded snapshot filenames can be deleted on Windows.
- [x] Add failing frontend hook test proving Delete selected failures show an error toast.
- [x] Implement safe snapshot-name candidates so unsafe account keys do not create invalid raw Windows paths.
- [x] Add Delete selected mutation error handling.
- [x] Run focused and broad backend/frontend verification, Ruff, TypeScript, OpenSpec validation, restart native codex-lb if needed, and update root handover plus implementation list.

## 23. Selection Toggle And Auth Config Baseline

- [x] Add failing frontend test proving Select all toggles to Unselect all when all visible rows are selected.
- [x] Add failing backend tests proving Auth->API original baseline creation, Windows-managed config sanitization, plain OpenAI provider preservation, and timestamped backup retention.
- [x] Implement Select all / Unselect all visible-row toggle without changing Codex/Backup location flags.
- [x] Implement protected original config baseline, Windows-compatible managed override removal, and opportunistic CodexNeo backup pruning.
- [x] Run focused and broad backend/frontend verification, Ruff, TypeScript/build, OpenSpec validation, restart native codex-lb if needed, and update root handover plus implementation list.

## 24. Account Table Sorting And Activity Log Retention

- [x] Add failing frontend tests for sortable `#`, Plan, 5h, Weekly, Avail, and Status / Last headers.
- [x] Add failing backend test proving the Activity log file is capped to the latest 1000 entries.
- [x] Implement sortable CodexNeo account table headers without changing account selection or Codex/Backup location state.
- [x] Implement Activity log retention during append so reads stay light.
- [x] Run focused and broad backend/frontend verification, Ruff, TypeScript/build, OpenSpec validation, restart native codex-lb if needed, and update root handover plus implementation list.

## 25. CodexNeo UI Cleanup, API-Key Selector Persistence, And Usage Import

- [x] Add failing frontend tests proving CodexNeo sortable headers do not render visible `SORT`/`ASC`/`DESC` labels.
- [x] Add failing frontend tests proving CodexNeo selected-account validity date controls are no longer rendered.
- [x] Add failing frontend tests proving API-key edit exact account/model searches are committed before save and enforced model values are submitted.
- [x] Implement compact sortable headers, remove selected-account validity date controls, and commit exact selector searches on close/Enter.
- [x] Add an idempotent one-time dashboard usage import script for rough CodexNeo Windows aggregate values.
- [x] Run focused frontend tests, dashboard usage import unit test, OpenSpec validation, TypeScript/build, and restart native codex-lb if needed.

## 26. Hidden Windows Startup Launcher

- [x] Add hidden-window Windows startup BAT/VBS files for the native source checkout.
- [x] Register the current-user Startup VBS shortcut/file so Codex IB starts automatically on Windows login.
- [x] Verify the Startup VBS exists and the launcher prefers the repo `.venv` FastAPI executable with logs under `%LOCALAPPDATA%\CodexIB`.

## 27. Delete-associated Backups And Backup Dedupe

- [x] Add failing backend tests proving Accounts-tab delete removes matching app-owned Backup snapshots when `codex-auth remove` succeeds and when the account exists only in Backup.
- [x] Add failing backend test proving backup creation replaces older app-owned Backup copies for the same real auth identity instead of keeping multiple backup rows.
- [x] Implement equivalent live/backup snapshot cleanup using auth claims rather than exact account-key matches only.
- [x] Ensure app-owned Backup registry rows and snapshot-only files are deleted with the associated account.
- [x] Run focused and broad CodexNeo/Accounts backend verification, Ruff, OpenSpec validation, restart native codex-lb if needed, and update root handover plus implementation list.

## 28. Auto Refresh, Auto Sync, And Switch Compatibility

- [x] Add failing frontend tests for page-scoped Codex Home auto refresh in seconds and automatic sync when the Accounts sync diagnostic reports a mismatch.
- [x] Add failing frontend tests proving CodexNeo action buttons no longer call browser `window.confirm`.
- [x] Add failing backend tests proving Switch and Switch & Restart use a local registry/snapshot fallback when the configured Codex registry schema is newer than the installed `codex-auth` binary supports.
- [x] Implement Codex Home auto refresh controls with safe status feedback and a 5-3600 second interval clamp.
- [x] Implement Auto sync controls that run explicit master sync when CodexNeo and Codex IB counts are mismatched, and make that mismatch a red diagnostics state.
- [x] Implement local switch fallback that updates active Codex Home registry state and root `auth.json`, while preserving intended restart behavior for Switch & Restart.
- [x] Remove CodexNeo browser confirmation prompts and keep backend/toast errors visible.
- [x] Run focused and broad backend/frontend verification, Ruff, TypeScript/build, OpenSpec validation, restart native codex-lb if needed, and update root handover plus implementation list.

## 29. Read/Write Boundary And Quality Cleanup

- [x] Add failing API test proving `GET /api/codexneo/accounts` is read-only and does not run account sync.
- [x] Add failing API test proving CodexNeo location mutations reject invalid locations outside `codex` / `backup`.
- [x] Add failing activity-log test proving disabled streams cannot append even through direct service paths.
- [x] Add regression coverage that read-only Accounts listing hides generated `__copy` rows without deleting them.
- [x] Move CodexNeo account import/sync cleanup to explicit write paths while keeping auto sync routed through `POST /api/codexneo/accounts/sync`.
- [x] Fix backend `ty` diagnostics and frontend CodexNeo page lint diagnostics.
- [x] Run focused and broad backend/frontend verification, Ruff, TypeScript/build, OpenSpec validation, restart native codex-lb if needed, and update root handover plus implementation list.

## 30. Root-only Auth And Manual Auth->API Apply

- [x] Add failing backend test proving top-level Codex Home `auth.json` appears in the CodexNeo account table even before it has a managed registry/snapshot row.
- [x] Add failing backend test proving explicit master sync registers a Codex IB account whose only Codex Home presence is root `auth.json` into managed Codex Home accounts.
- [x] Add failing backend tests proving Auth->API Set and Auth->API Revert do not automatically restart Codex Desktop after verified config writes.
- [x] Implement root-only discovery and registration by loading root `auth.json` as a live CodexNeo row and materializing it into managed Codex Home registry/snapshot storage during explicit sync.
- [x] Keep Codex Desktop restart on the explicit Restart Codex action only.
- [x] Run focused backend verification without restarting the portable app or Codex Desktop.

## 31. Accounts Tab User Setting Persistence

- [x] Add failing backend test proving an operator-paused account remains paused after the same auth snapshot is synced/imported again.
- [x] Preserve user-paused account status while still allowing token/refresh metadata updates during auth sync.
- [x] Patch the portable backend copy without restarting the portable app.
- [x] Run focused Accounts repository/API verification, Ruff, OpenSpec validation, and portable backend syntax check.

## 32. Electron Portable Start With Windows

- [x] Add failing backend, frontend, and Electron helper tests for a persisted `Start with Windows` preference.
- [x] Persist `startWithWindowsEnabled` in CodexNeo settings and expose it through the settings API.
- [x] Add the CodexNeo `Start with Windows` switch and Electron preload bridge.
- [x] Register or unregister the packaged portable EXE at Windows login through Electron `app.setLoginItemSettings`.
- [x] Run focused and broad verification, mirror runtime files into the Electron portable folder without restarting the running app, and update handover plus implementation list.
