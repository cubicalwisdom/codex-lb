## Why

The portable branch has already backported the core GPT-5.6 and Responses Lite work, but it lacks several v1.21 wire-level compatibility guards. In particular, multi-agent-v2 turns can still receive synthesized top-level tools, outbound native calls lack the complete Codex fingerprint, and owner forwarding relays untrusted headers unchanged.

## What Changes

- Preserve native multi-agent-v2 and Responses Lite payloads without synthesizing top-level `tools` on upstream, replay, or owner-forward paths.
- Normalize outbound HTTP and WebSocket traffic from OpenAI-compatible callers to the canonical Codex CLI fingerprint while preserving native Codex callers and enforcing the selected account identity.
- Harden WebSocket retry/reconnect behavior for tool-output deltas, replay sequencing, reconnect affinity, and oversized `response.create` frames.
- Filter unsafe and spoofable inbound headers before a request is forwarded to an HTTP bridge owner.
- Add focused regressions for every compatibility and forwarding contract in this change.

## Capabilities

### New Capabilities

- `internal-bridge-forwarding`: Defines the trust boundary for internal HTTP bridge forwarding headers.

### Modified Capabilities

- `responses-api-compat`: Native Codex multi-agent and retry/replay payloads retain their upstream-compatible shape.
- `outbound-http-clients`: Native Codex upstream requests use a complete, canonical client fingerprint and installation identity.

## Impact

- Affects native Responses request normalization, direct WebSocket traffic, HTTP bridge forwarding, and outbound HTTP/WebSocket client headers.
- Adds no dashboard behavior, account-policy controls, database migrations, or external dependencies.
- Requires source and portable-runtime parity checks; Codex Desktop itself is not restarted by this change.
