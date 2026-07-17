## ADDED Requirements

### Requirement: Anthropic Messages route authenticates Claude Code credentials safely

The system SHALL expose `POST /v1/messages`. The route MUST accept a codex-lb API key in either `x-api-key` or `Authorization: Bearer`, MUST reject conflicting non-empty credentials, and MUST retain the existing local-only protection when API-key authentication is disabled. Existing native Codex and OpenAI-compatible routes MUST retain their current authentication behavior. Authentication, policy, validation, rate-limit, and upstream failures on this route MUST use the Anthropic error envelope.

#### Scenario: Claude Code authenticates with x-api-key

- **WHEN** a client sends a valid codex-lb key only in `x-api-key`
- **THEN** the route authenticates the same principal as the Bearer-compatible proxy route
- **AND** executes the request through the existing API-key policy path

#### Scenario: Conflicting credentials are rejected

- **WHEN** a client sends non-empty `x-api-key` and Bearer credentials with different values
- **THEN** the route returns HTTP 401
- **AND** its body is an Anthropic `authentication_error`

### Requirement: Messages requests translate supported Claude Code turns into Responses

The route MUST require a non-empty model, `max_tokens`, and an ordered messages array. It MUST translate system text, user/assistant text, function tools, assistant `tool_use`, and user `tool_result` blocks into a Responses request without reordering the turn. It MUST translate Anthropic tool choice into the equivalent Responses tool policy and preserve `disable_parallel_tool_use`. Unsupported content block types MUST return HTTP 400 with an Anthropic `invalid_request_error` before upstream execution.

The request model MUST be a codex-lb model identifier unless the authenticated API key has an enforced model or the request selects the local Claude Desktop profile. When a Claude model identifier is supplied with an enforced model, the request MUST execute using the enforced model while response metadata retains the client-visible model identifier.

#### Scenario: Tool turn preserves call identity

- **WHEN** an assistant message contains a `tool_use` block and a following user message contains its `tool_result`
- **THEN** the forwarded Responses input contains a function call and function-call output with the same call id
- **AND** their relative ordering is preserved

#### Scenario: Claude model label uses explicit API-key enforcement

- **WHEN** a client sends a Claude model identifier with an API key that enforces `gpt-5.6-terra`
- **THEN** the forwarded Responses request uses `gpt-5.6-terra`
- **AND** the Anthropic response reports the original Claude model identifier

### Requirement: Claude Desktop model discovery is key-scoped and local-only

For a loopback request whose credential is exactly `claudedesktop`, `GET /v1/models` MUST return only the Anthropic-facing model IDs `claude-opus-4-8` and `claude-sonnet-5`, each owned by `anthropic`. The profile MUST resolve `opus` and `claude-opus-*` requests to `gpt-5.6-sol`, and `sonnet` and `claude-sonnet-*` requests to `gpt-5.6-terra`. A remote request MUST NOT select this profile. Requests without that local credential, including all existing OpenAI-compatible clients, MUST retain the existing registry-backed `/v1/models` behavior and MUST NOT receive synthetic Claude model IDs.

The local `claudedesktop` profile MUST also accept text-only `system` and `developer` items in the Messages `messages` array when emitted by Claude Desktop beta requests. It MUST translate their text into the Responses `instructions` field. All other clients MUST retain the standard Anthropic Messages role restriction to `user` and `assistant`.

For the local `claudedesktop` profile, the adapter MUST translate `output_config.effort` to the upstream Responses `reasoning.effort`. It MUST support `low`, `medium`, `high`, `xhigh`, and `max`; the Desktop UI label **Extra** corresponds to `xhigh`. If Claude Desktop omits `output_config.effort`, the adapter MUST use `high`, matching Claude's documented default. This mapping MUST NOT apply to other clients.

CodexNeo MUST expose a persisted Sonnet fallback-effort control with Low, Medium, High, Extra (`xhigh`), and Max options. When a local `claudedesktop` Sonnet-family request omits `output_config.effort`, the adapter MUST use the selected CodexNeo value instead of the generic `high` fallback. Explicit `output_config.effort` values, Opus-family defaults, and all non-Desktop clients MUST retain their existing behavior.

#### Scenario: Claude Desktop discovers only its mapped Anthropic models

- **WHEN** a loopback client calls `GET /v1/models` with `x-api-key: claudedesktop`
- **THEN** the response lists `claude-opus-4-8` and `claude-sonnet-5` with `owned_by` equal to `anthropic`
- **AND** it does not expose Codex LB model IDs in that response

#### Scenario: Existing OpenAI-compatible discovery remains unchanged

- **WHEN** a client calls `GET /v1/models` without the local `claudedesktop` credential
- **THEN** the response is built from the existing Codex LB model registry
- **AND** it does not include `claude-opus-4-8` or `claude-sonnet-5`

#### Scenario: Claude Desktop routes tiers to their selected Codex LB models

- **WHEN** a local Claude Desktop request with `x-api-key: claudedesktop` uses a Claude Opus-family model
- **THEN** the forwarded Responses request uses `gpt-5.6-sol`
- **AND** the Anthropic response reports the original Claude-facing model ID

- **WHEN** a local Claude Desktop request with `x-api-key: claudedesktop` uses a Claude Sonnet-family model
- **THEN** the forwarded Responses request uses `gpt-5.6-terra`
- **AND** the Anthropic response reports the original Claude-facing model ID

#### Scenario: Claude Desktop beta instructions are accepted without broadening the public facade

- **WHEN** a loopback Claude Desktop request with `x-api-key: claudedesktop` sends a text-only `developer` or `system` message in its Messages array
- **THEN** the adapter translates that text into the Responses `instructions` field and executes the request
- **AND** the same role in a request without the local profile receives an Anthropic invalid-request error

#### Scenario: Claude Desktop effort maps to native reasoning effort

- **WHEN** a loopback Claude Desktop request with `x-api-key: claudedesktop` sends `output_config.effort` set to `low`, `medium`, `high`, `xhigh`, or `max`
- **THEN** the forwarded Responses request contains the same `reasoning.effort`
- **AND** the Desktop **Extra** selection is represented by `xhigh`

- **WHEN** the local Claude Desktop request omits `output_config.effort`
- **THEN** the forwarded Responses request uses `reasoning.effort` equal to `high`

#### Scenario: CodexNeo selects the Sonnet fallback effort

- **WHEN** an owner selects Extra in the CodexNeo Sonnet reasoning control
- **THEN** CodexNeo persists the native effort value `xhigh`
- **AND WHEN** a local Claude Desktop Sonnet-family request omits `output_config.effort`
- **THEN** its forwarded Responses request uses `reasoning.effort` equal to `xhigh`

#### Scenario: Desktop-supplied effort takes precedence over CodexNeo

- **WHEN** CodexNeo selects Max for the Sonnet fallback
- **AND WHEN** a local Claude Desktop Sonnet-family request supplies `output_config.effort` equal to `medium`
- **THEN** its forwarded Responses request uses `reasoning.effort` equal to `medium`

### Requirement: Messages responses preserve Anthropic terminal and streaming contracts

For `stream=false`, the route MUST translate completed Responses text and function calls into an Anthropic `message` object with ordered `text` and `tool_use` blocks, usage, and a terminal stop reason. For `stream=true`, the route MUST emit `message_start`, ordered content-block start/delta/stop events, `message_delta`, and `message_stop` without waiting for the full upstream response. Function arguments MUST be emitted as `input_json_delta` content deltas. If the Responses stream fails or ends without a valid terminal completion, the route MUST emit an Anthropic `error` event and MUST NOT emit successful message termination, except for the narrow local Claude Desktop terminal-loss recovery defined below.

#### Scenario: Text stream is converted incrementally

- **WHEN** the Responses stream emits a created event, text deltas, and a completed event
- **THEN** the Messages stream emits one `message_start`, text content-block events, one `message_delta`, and one `message_stop` in order

#### Scenario: Function stream is converted incrementally

- **WHEN** the Responses stream emits a function-call item and argument deltas
- **THEN** the Messages stream emits a `tool_use` content-block start and matching `input_json_delta` events
- **AND** stops that content block before its terminal message events

#### Scenario: Non-streaming output preserves tool use

- **WHEN** a completed Responses payload contains text followed by a function call
- **THEN** the non-streaming Messages response contains ordered `text` and `tool_use` content blocks
- **AND** has `stop_reason` equal to `tool_use`

### Requirement: Messages token count uses the local compatible estimator

The system SHALL expose `POST /v1/messages/count_tokens`. It MUST accept the same supported input content and authentication conventions as `POST /v1/messages`, without requiring `max_tokens`, and MUST return an object containing a non-negative `input_tokens` integer. The route MUST validate and normalize the message payload before delegating to the existing local Responses token estimator, which MUST use the mapped model tokenizer when known and `o200k_base` otherwise rather than a byte- or character-ratio heuristic. The same tokenizer-compatible estimate MUST protect the mapped context budget. The route MUST return `x-codex-lb-token-count: local-compatible` and MUST NOT create an upstream request. Unsupported or opaque input MUST return an Anthropic `invalid_request_error`.

#### Scenario: Claude Desktop performs a token-count preflight

- **WHEN** the local `claudedesktop` profile posts a valid Messages payload to `/v1/messages/count_tokens`
- **THEN** the response is HTTP 200 with a non-negative `input_tokens` value
- **AND** it contains `x-codex-lb-token-count: local-compatible`

#### Scenario: Tool schemas may define a property named type

- **WHEN** a valid Messages token-count request includes a function tool whose JSON Schema `properties` object contains a property literally named `type`
- **THEN** the local opaque-input scan treats that nested schema value as ordinary JSON metadata
- **AND** the route returns HTTP 200 instead of raising an internal type error

### Requirement: Local Claude Desktop avoids recoverable startup and terminal stream failures

The local `claudedesktop` profile MUST bypass the optional owner-forward HTTP bridge for Messages execution. Before a streaming or non-streaming result is returned, it MAY perform bounded retries for a documented recoverable upstream availability failure. It MUST NOT retry after a streaming response has begun. If a local Claude Desktop text-only stream has emitted non-empty text and then receives a `stream_incomplete` terminal failure, it MUST close the active text blocks and emit an Anthropic `message_delta` with `end_turn` followed by `message_stop`. It MUST retain an error for empty streams and any stream that contains tool use.

#### Scenario: Terminal frame is lost after Claude Desktop text

- **WHEN** a local Claude Desktop text stream emits non-empty text and then receives `stream_incomplete`
- **THEN** the adapter closes the text block and emits `message_stop`
- **AND** it does not retry or duplicate the already emitted text

### Requirement: CodexNeo exposes an explicit Claude Desktop restart action

CodexNeo MUST expose an authenticated **Restart Claude** dashboard action adjacent to its existing desktop restart controls. On Windows, the action MUST request a graceful close of the installed Claude Desktop package, stop only remaining matching package processes, and relaunch the registered Claude Desktop app. The action MUST report success or failure to the caller and MUST NOT execute unless an operator invokes it.

#### Scenario: Operator restarts Claude Desktop

- **WHEN** an authorized operator selects **Restart Claude** in CodexNeo
- **THEN** CodexNeo invokes the Claude Desktop restart action
- **AND** returns the action result without restarting Codex Desktop
