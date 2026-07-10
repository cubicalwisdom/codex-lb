## ADDED Requirements

### Requirement: Responses Lite disables parallel tool calls on the upstream wire

Whenever the proxy selects Responses Lite from a normalized `additional_tools` input item or a trusted linked WebSocket continuation marker, every upstream full Responses wire payload MUST contain `parallel_tool_calls: false`. This rule MUST apply to direct HTTP, direct WebSocket, HTTP-to-WebSocket bridge, owner-forward, retry, and replay paths. Non-Lite full Responses requests MUST retain their requested `parallel_tool_calls` value. Compact requests MUST remove `tools` and `tool_choice` but MUST explicitly send `parallel_tool_calls: false`.

#### Scenario: Full Lite request overrides an incompatible client value

- **GIVEN** a Codex Responses request contains `additional_tools` and `parallel_tool_calls: true`
- **WHEN** codex-lb forwards it over HTTP or WebSocket
- **THEN** the appropriate Lite header or metadata marker is present
- **AND** the upstream wire payload contains `parallel_tool_calls: false`

#### Scenario: Trusted Lite continuation remains compatible

- **GIVEN** an accepted Lite WebSocket request established a downstream-visible response id
- **WHEN** a linked same-model continuation carries the trusted Lite marker and requests `parallel_tool_calls: true` without repeating `additional_tools`
- **THEN** the marker remains present
- **AND** the upstream wire payload contains `parallel_tool_calls: false`

#### Scenario: Non-Lite full Responses behavior remains unchanged

- **GIVEN** a request does not select Responses Lite
- **WHEN** it is forwarded
- **THEN** codex-lb does not rewrite its `parallel_tool_calls` value under this rule

#### Scenario: Compact payload supplies the required false value

- **GIVEN** a request targets `/backend-api/codex/responses/compact` or `/v1/responses/compact`
- **WHEN** codex-lb serializes the upstream compact payload
- **THEN** it removes `tools` and `tool_choice`
- **AND** it sends `parallel_tool_calls: false`
