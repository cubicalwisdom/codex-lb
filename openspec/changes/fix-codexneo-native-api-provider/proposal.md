## Why

CodexNeo currently defaults its native Codex provider action to the generic OpenAI-compatible `/v1` base URL. Current Codex clients expect the Codex-native model catalog envelope under `/backend-api/codex`; writing `/v1` into `openai_base_url` can therefore make model discovery fail after the GPT-5.6 client update.

## What Changes

- Use the local Codex-native `/backend-api/codex` base URL as the CodexNeo default and UI guidance.
- Migrate only the exact legacy local CodexNeo default `http://127.0.0.1:2455/v1`; preserve operator-supplied and remote URLs unchanged.
- Make the Codex API connectivity test validate the Codex-native `models` response envelope rather than accepting any successful HTTP response.
- Keep source and portable runtime copies synchronized and cover the behavior with focused backend/frontend tests.

## Capabilities

### New Capabilities

- `codexneo-api-provider-compatibility`: Defines native Codex provider URL defaults, legacy-local migration, and model-catalog validation.

### Modified Capabilities

None.

## Impact

Affected areas are the CodexNeo backend settings/provider service, its diagnostics and dashboard URL guidance, focused tests, the checked-in portable runtime copy, and CodexNeo continuity documentation. Generic OpenAI-compatible `/v1` proxy routes and SDK examples remain unchanged.
