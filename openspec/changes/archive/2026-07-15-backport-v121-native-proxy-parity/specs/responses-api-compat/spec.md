## ADDED Requirements

### Requirement: Native multi-agent payloads preserve omitted top-level tools

For native Codex Responses requests, the proxy MUST preserve whether the caller omitted top-level `tools` across direct upstream send, HTTP bridge owner-forward, retry, and replay serialization. A request whose input selects Responses Lite or a catalog model with `multi_agent_version = "v2"` MUST NOT gain a synthesized `tools: []` field solely because the internal request model has a default tools value. The proxy MUST preserve supported Codex compatibility metadata headers in upstream `client_metadata` without relaying their client-supplied header form through bridge-internal WebSocket setup.

#### Scenario: Multi-agent v2 request omits top-level tools upstream

- **WHEN** a native Codex request for a `multi_agent_version = "v2"` model omits top-level `tools`
- **THEN** direct, retried, and owner-forwarded upstream payloads omit top-level `tools`
- **AND** the request retains its ordered `input` and supported compatibility metadata

### Requirement: WebSocket recovery never fabricates an unsafe fresh turn

The proxy MUST replay a WebSocket request without `previous_response_id` only when the replay input is self-contained and no sequenced downstream frame has been exposed for that request. A payload containing function, custom, or apply-patch tool output without its matching call in the same input MUST NOT be treated as self-contained. When a sequenced downstream frame has been exposed, the proxy MUST not reconnect-and-replay the request.

#### Scenario: Tool-output delta is not replayed as a fresh turn

- **WHEN** a WebSocket continuation has `previous_response_id` and carries an output item without its matching call item
- **AND** upstream rejects the anchor before `response.created`
- **THEN** the proxy MUST return the retryable continuity failure
- **AND** it MUST NOT replay the output delta without `previous_response_id`

#### Scenario: Exposed sequence blocks replay

- **WHEN** an upstream response has exposed a sequenced downstream frame for a pending request
- **AND** the upstream connection subsequently closes or returns a retryable pre-created failure
- **THEN** the proxy MUST NOT reconnect-and-replay that request

### Requirement: Downstream WebSocket ingress reaches the response-create size guard

The server MUST accept decompressed incoming Responses WebSocket messages up to a configurable 128 MiB default before applying the existing response-create size guard. When a request remains too large after permitted slimming, every HTTP or WebSocket response surface MUST return a status-400 `payload_too_large` invalid-request error rather than status 413.

#### Scenario: Large response.create is rejected at the application layer

- **WHEN** a client sends a Responses WebSocket frame larger than the historical 16 MiB server default but within the configured ingress budget
- **THEN** the frame reaches the application-level response-create guard
- **AND** an unslimmable request receives a status-400 `payload_too_large` error instead of a WebSocket 1009 close
