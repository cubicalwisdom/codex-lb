## Why

Claude Code can target a custom API base URL, but codex-lb currently exposes only native Codex and OpenAI-compatible request shapes. A first-class Anthropic Messages facade lets Claude Code use the existing local account routing, quota enforcement, and Responses transport without a separate proxy process.

## What Changes

- Add `POST /v1/messages` and `POST /v1/messages/count_tokens`, Anthropic-compatible facades over codex-lb's canonical Responses execution path and local token estimator.
- Add a Claude Desktop discovery profile: a local request using the dedicated `claudedesktop` credential receives Anthropic-facing model identifiers from `GET /v1/models`, while every other client retains the existing Codex LB catalog.
- Add a CodexNeo-only Sonnet reasoning control for Claude Desktop, because the Desktop GUI does not expose its effort selector when `claude-sonnet-5` is selected.
- Add an explicit **Restart Claude** action to CodexNeo for the Windows Claude Desktop package.
- Accept Claude Code's `x-api-key` authentication convention as well as the existing Bearer convention, without changing authentication behavior on existing routes.
- Translate supported text, system, function-tool, tool-use, and tool-result request content into Responses input, and translate terminal and streaming Responses output back into Anthropic Messages objects/events.
- Return Anthropic-shaped errors on the new route while preserving existing codex-lb rate-limit and account-policy behavior.

## Capabilities

### New Capabilities

- `anthropic-messages-compat`: Defines the public Anthropic Messages contract, authentication, request translation, response translation, and stream behavior for Claude Code clients.

### Modified Capabilities

- None.

## Impact

- Adds a `/v1/messages` route and narrow Anthropic request/response conversion modules.
- Reuses the existing Responses service, API-key enforcement, rate limits, local token estimator, and portable runtime packaging process.
- Adds no external dependency, account-routing policy, or automatic Claude Code configuration change. The persisted CodexNeo Sonnet setting is local-only and does not alter the portable endpoint's model catalog or reasoning behavior for other applications.
