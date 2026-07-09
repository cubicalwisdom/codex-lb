## Context

CodexNeo stores one URL for the native Codex provider action and writes it to the user's top-level Codex `openai_base_url`. The current local default ends in `/v1`, whose `/models` response is the generic OpenAI `object`/`data` envelope. Current Codex clients fetch a native `models` envelope and the proxy already exposes that contract at `/backend-api/codex/models`.

The URL is consumed by settings, diagnostics, provider testing, config writes, the dashboard placeholder, and a checked-in portable runtime copy. Existing users can have the old local default persisted, while custom URLs must remain owner-controlled.

## Goals / Non-Goals

**Goals:**

- Route CodexNeo's local native-Codex provider action through `/backend-api/codex`.
- Upgrade the exact legacy local default without rewriting custom endpoints.
- Fail the connectivity check when a successful HTTP response is not a Codex-native model catalog.
- Keep source, tests, UI guidance, diagnostics, and the portable runtime aligned.

**Non-Goals:**

- Changing `/v1` behavior for OpenAI-compatible SDKs or other clients.
- Rewriting arbitrary localhost, remote, or operator-supplied URLs.
- Restarting Codex Desktop automatically.

## Decisions

1. Define separate native and legacy-local URL constants and centralize Codex-provider normalization in one helper. The helper first performs existing absolute HTTP(S) validation, then maps only the normalized exact legacy URL to the native default. This avoids broad suffix rewriting and preserves custom `/v1` providers.
2. Persist the migration during a normal settings read by copying the original JSON mapping and replacing only `codex_api_base_url`. This ensures the dashboard and later provider actions cannot silently reintroduce the known-invalid local default without discarding settings written by newer or external clients. Diagnostics use the same normalization helper so their display is consistent even before the settings endpoint is read.
3. Validate direct `GET <base>/models` responses as 2xx JSON containing a top-level `models` list. HTTP status alone cannot distinguish the generic `/v1/models` envelope from the Codex-native endpoint, and redirect following must not hide a misconfigured provider URL.
4. Update only CodexNeo-specific UI guidance and fixtures. Generic `/v1` README examples and SDK verification scripts remain correct and unchanged.
5. Copy the verified backend/frontend outputs into the existing portable distribution using the repository's packaging workflow instead of maintaining divergent manual behavior.

## Risks / Trade-offs

- [A custom service intentionally uses the exact legacy local URL] -> The migration is deliberately limited to the historical CodexNeo-owned host, port, and path; operators can configure any other URL unchanged.
- [A server returns non-JSON or a generic model envelope with HTTP 200] -> The test reports a clear compatibility failure and does not write config.
- [A settings read now performs one migration write] -> The write happens only when the exact legacy value is present, atomically replaces only that key, and preserves all other serialized settings values.
- [Portable files drift from source] -> Verification compares relevant source and portable files after packaging/synchronization.

## Migration Plan

1. Ship the new default and normalization helper.
2. On the first settings read, replace and atomically persist only `http://127.0.0.1:2455/v1` with `http://127.0.0.1:2455/backend-api/codex`.
3. Keep config backup/revert behavior unchanged. The operator still restarts Codex manually after setting or reverting the provider.
4. Roll back by restoring the prior application build; existing config backups remain available and no generic proxy routes are changed.

## Open Questions

None.
