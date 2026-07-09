## ADDED Requirements

### Requirement: Responses Lite embedded tool declarations remain intact

For native Codex Responses requests, the proxy MUST preserve the complete ordered `input` envelope whenever an item has `type: "additional_tools"`. The proxy MUST NOT treat that protocol item or the following developer instruction message as top-level textual instructions, remove either item, convert tool definitions into prompt text, or synthesize an ordinary top-level `tools` field. System/developer normalization for non-Lite input MUST continue to behave as documented.

When a native Codex client requests Lite, upstream HTTP and compact transports MUST send `x-openai-internal-codex-responses-lite: true`. Upstream WebSocket transports MUST put `ws_request_header_x_openai_internal_codex_responses_lite: "true"` in `response.create.client_metadata` and MUST omit the HTTP-only marker from the WebSocket handshake. The proxy MUST NOT honor or synthesize the marker for a non-native client.

#### Scenario: Request validation preserves the embedded tool bundle and ordering

- **GIVEN** a full or compact Responses input array contains an `additional_tools` developer-role item followed by ordinary messages and a matched `custom_tool_call` / `custom_tool_call_output` pair
- **WHEN** the proxy validates and serializes the request
- **THEN** the complete input array, including the following developer instruction message, remains unchanged
- **AND** every item's relative position is preserved
- **AND** no top-level `tools` field is synthesized from the embedded bundle

#### Scenario: Native Codex HTTP forwarding retains Responses Lite metadata

- **GIVEN** a native Codex HTTP Responses request contains an `additional_tools` input item and `x-openai-internal-codex-responses-lite: true`
- **WHEN** the proxy forwards the request upstream over HTTP or the HTTP Responses bridge
- **THEN** the forwarded input still contains the complete embedded tool item
- **AND** a direct or fallback upstream HTTP request contains the marker value `true`
- **AND** an HTTP-to-WebSocket bridge encodes the marker in `response.create.client_metadata`

#### Scenario: Native Codex WebSocket forwarding retains Responses Lite metadata

- **GIVEN** a native Codex WebSocket `response.create` request contains an `additional_tools` input item, a later matched `custom_tool_call` / `custom_tool_call_output` pair, and the Responses Lite marker header
- **WHEN** the proxy opens the upstream WebSocket and forwards the request
- **THEN** the upstream handshake omits `x-openai-internal-codex-responses-lite`
- **AND** the forwarded `response.create.client_metadata` contains `ws_request_header_x_openai_internal_codex_responses_lite: "true"`
- **AND** the forwarded input preserves the embedded tool declaration, developer instruction, and custom tool output in their original relative order

#### Scenario: Non-native clients cannot enable the internal Lite transport

- **GIVEN** a non-native OpenAI-compatible client sends `x-openai-internal-codex-responses-lite: true`
- **WHEN** the proxy filters and forwards the request
- **THEN** the internal header is absent upstream
- **AND** the proxy does not synthesize the WebSocket Lite metadata key
