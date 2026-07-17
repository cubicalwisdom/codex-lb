# anthropic-protocol-continuity Specification

## Purpose
TBD - created by archiving change harden-anthropic-protocol-continuity. Update Purpose after archive.
## Requirements
### Requirement: Messages preserves tool identity across the mapped protocol

The Anthropic Messages facade MUST keep every forwarded Responses function name and call ID within 64 UTF-8 bytes. It MUST preserve identifiers already within that limit and MUST map longer identifiers deterministically with a digest of the complete original value. The same tool-name mapping MUST be used for definitions, forced tool choice, historical assistant tool use, and Claude-visible reverse response translation. The same call-ID mapping MUST be used for a historical `function_call` and its matching `function_call_output`. Ambiguous or duplicate mappings MUST fail before upstream execution.

#### Scenario: Long paired tool identifiers remain consistent

- **WHEN** an assistant tool call and its later result use the same identifier longer than 64 UTF-8 bytes
- **THEN** the forwarded `function_call` and `function_call_output` use the same deterministic identifier of at most 64 bytes
- **AND** another long identifier with the same prefix maps to a different value

#### Scenario: A forced long tool retains its Claude-visible name

- **WHEN** a request defines and forces a tool whose name exceeds 64 UTF-8 bytes
- **THEN** the forwarded definition, forced choice, and historical call use one Responses-safe alias
- **AND** a returned call using that alias is exposed to Claude with the original tool name

### Requirement: Messages round-trips opaque reasoning state

For the Claude Desktop profile, the facade MUST request upstream encrypted reasoning output. It MUST translate upstream-supplied reasoning summaries and encrypted content into ordered Anthropic thinking text and signature fields without fabricating either value. It MUST replay a non-empty signature from an assistant thinking block as a Responses reasoning input item while excluding the visible thinking text from replay. It MUST reject missing, empty, malformed, or user-authored thinking state before upstream execution.

#### Scenario: Encrypted reasoning continues across turns

- **WHEN** an upstream response includes a reasoning summary and non-empty `encrypted_content`
- **THEN** the Anthropic response contains a thinking block with the supplied summary and signature
- **AND** a later assistant-history replay sends the signature as opaque Responses reasoning input without replaying the visible summary text

#### Scenario: A streaming signature is emitted before block closure

- **WHEN** a streamed reasoning item provides summary deltas and a final encrypted value
- **THEN** the facade emits a thinking block, ordered `thinking_delta` events, one `signature_delta`, and then `content_block_stop`

### Requirement: Immediate stream failures remain pre-header errors

The Anthropic Messages facade MUST inspect a bounded sequence of initial comment/keepalive frames and the first semantic Responses SSE event before committing an Anthropic stream. If that semantic event is `error` or `response.failed`, the facade MUST convert it through the existing Anthropic HTTP error and eligible Claude Desktop startup-retry path. It MUST replay comments and normal events exactly once and MUST NOT buffer later content-bearing events.

#### Scenario: A keepalive precedes an upstream failure

- **WHEN** the direct upstream stream emits a comment followed immediately by `response.failed`
- **THEN** Claude receives the mapped Anthropic HTTP error or a successful bounded pre-stream retry
- **AND** it does not first receive HTTP 200 with an in-stream terminal error

### Requirement: Protocol telemetry excludes translated content

Protocol-hardening telemetry MUST contain only event names, direction, outcome, item kind, counts, and lengths. It MUST NOT contain prompts, tool names, tool or call identifiers, arguments, URLs, summaries, signatures, encrypted reasoning, API keys, or credentials.

#### Scenario: Sentinel secrets do not enter logs

- **WHEN** a request exercises identifier mapping and reasoning replay with unique sentinel values
- **THEN** telemetry records the applicable mapping/replay outcomes and lengths
- **AND** none of the sentinel values appears in captured logs
