## 1. Regression coverage

- [x] Add Electron RED tests for coordinated owned-backend shutdown and immediate relaunch.
- [x] Add CodexNeo RED tests for the header restart control and equal CodexGO action sizing.
- [x] Add Dashboard RED tests for per-account Pause/Resume in card and list modes.

## 2. Implementation

- [x] Add the context-isolated restart IPC bridge and bounded Electron relaunch coordinator.
- [x] Add Restart Codex LB to the CodexNeo header with Electron capability gating.
- [x] Wire Dashboard Pause/Resume through the existing account mutations in both account presentations.
- [x] Make Use auth and Refresh auth equal compact actions.

## 3. Verification and portable delivery

- [x] Run Electron, frontend, backend, lint, typecheck, build, and strict OpenSpec gates.
- [x] Rebuild or mirror verified Electron/static/runtime files and verify hashes.
- [x] Exercise the approved Restart Codex LB control and verify the old shell/backend exit and the replacement app becomes healthy.
- [x] Update implementation tracking and handover with exact evidence.
