## ADDED Requirements

### Requirement: Upstream Responses egress uses a canonical Codex fingerprint

When an OpenAI-compatible client is forwarded to the upstream Codex Responses API, the proxy MUST replace SDK-specific user-agent and client fingerprint headers with the current Codex CLI fingerprint before upstream HTTP or WebSocket egress. Native Codex callers MUST preserve their valid native fingerprint. The selected account identifier MUST replace any caller-supplied account identity value.

#### Scenario: OpenAI-compatible WebSocket caller is normalized before egress

- **WHEN** an OpenAI-compatible client opens a Responses WebSocket with an SDK user agent and client headers
- **THEN** upstream receives the canonical Codex CLI user agent rather than the SDK fingerprint
- **AND** upstream receives the selected account identity rather than a caller-supplied account value
