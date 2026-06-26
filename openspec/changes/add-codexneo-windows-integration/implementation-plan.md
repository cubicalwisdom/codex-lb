# Implementation Plan

## Scope

Implement the CodexNeo tab inside the native Codex IB / codex-lb app. The tab manages the real Windows Codex home at `%USERPROFILE%\.codex`, while storing codex-lb UI settings under codex-lb's configured data directory.

## Approach

1. Add backend tests first.
   - Settings persistence returns URLs and masked token state, never plaintext buyer token.
   - Provider config set writes a managed `model_provider = "openai"` and `openai_base_url` block to `config.toml`.
   - Revert removes the managed provider override.
   - CodexGO use/refresh posts to normalized provider endpoints and atomically replaces `auth.json` only after validating the returned auth shape.
   - Scheduler skips when disabled or tokenless and refreshes when enabled.

2. Implement backend module.
   - Add `app/modules/codexneo` with schemas, service, API router, and scheduler.
   - Persist settings in JSON under `get_settings().data_dir / "codexneo-settings.json"`.
   - Encrypt buyer tokens with `TokenEncryptor`.
   - Use existing dashboard auth dependencies for read/write access.

3. Implement frontend.
   - Add `frontend/src/features/codexneo` client, hooks, tests, and page.
   - Keep controls dense and operational: URL inputs, refresh interval, checkbox, and action buttons.
   - Disable mutating controls for read-only guest users.

4. Wire and verify.
   - Include the router and scheduler from `app/main.py`.
   - Add route and nav item.
   - Run OpenSpec validation, focused backend/frontend tests, frontend build, and browser smoke verification.

## Ambiguity Handling

- Restarting the Codex desktop app after Set/Revert is not assumed. The first implementation writes and verifies files; any restart control should be added only after the exact desired restart behavior is confirmed.
- The API test is implemented as a non-mutating connectivity check against the configured Codex API base URL, avoiding token-consuming chat completions unless explicitly requested later.
