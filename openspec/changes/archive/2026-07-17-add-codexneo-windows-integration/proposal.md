# Add CodexNeo Windows Integration

## Why

Operators using the native Windows Codex IB install need CodexNeo-style controls inside the codex-lb dashboard. Today the auth switch/test/revert and CodexGO refresh workflows live in separate helper apps, which makes the native setup harder to operate and easier to misconfigure.

## What Changes

- Add a dashboard `CodexNeo` tab/route near the existing dashboard APIs/settings navigation.
- Add backend endpoints for Codex API URL settings, API connectivity test, provider config set, provider config revert, CodexGO auth use, and CodexGO auth refresh.
- Add an encrypted local buyer-token setting and auto-refresh scheduler for CodexGO auth.
- Write host Codex files under the real Windows Codex home, with backups and atomic replacement.
- Add CodexNeo health diagnostics adapted for the Codex IB web app, including safe status badges for local paths, sync counts, activity-log settings, CodexGO configuration, and OpenAI bridge configuration.

## Impact

- Dashboard users gain a Windows host integration surface for CodexNeo operations.
- Admin/write access is required for mutating actions.
- Guest/read-only users can view non-secret status/settings but cannot trigger writes.
- The app gains a local background scheduler that refreshes auth only when explicitly enabled and configured.
