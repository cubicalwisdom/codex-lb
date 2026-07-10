# Responses API Compatibility Context

## Purpose and Scope

This capability implements OpenAI-compatible behavior for `POST /v1/responses`, including request validation, streaming events, non-streaming aggregation, and OpenAI-style error envelopes. The scope is limited to what the ChatGPT upstream can provide; unsupported features are explicitly rejected.

See `openspec/specs/responses-api-compat/spec.md` for normative requirements.

## Rationale and Decisions

- **Responses as canonical wire format:** Internally we treat Responses as the source of truth to avoid divergent streaming semantics.
- **Strict validation:** Required fields and mutually exclusive fields are enforced up front to match official client expectations.
- **Cursor alias compatibility:** Cursor UI model labels may append recognized reasoning or speed suffixes to GPT-5 slugs, including Sol/Terra/Luna; those are normalized to canonical upstream fields before forwarding. `max` and `ultra` are reasoning values, not model-suffix tokens.
- **Responses Lite input envelope:** Codex GPT-5.6 Responses Lite sends custom tool declarations as `additional_tools` followed by a developer instruction message inside `input`. The body is authoritative, so request normalization preserves the complete ordered envelope and derives the reserved transport marker after model/API-key policy. Marker-only reuse requires the most recently accepted downstream-visible Lite response id for the same effective model. Every selected Lite wire payload forces `parallel_tool_calls=false`, including owner-forward, reconnect, fresh full-resend, and replay bodies; a non-Lite payload keeps the client's value.
- **Future protocol directives:** Typed non-message system/developer objects stay in `input` byte-identically, bypass message sanitization, and remain compact-trim anchors. Only typeless or `type: message` instruction messages are hoisted.
- **Interrupted tool continuity:** Function, custom, and apply-patch calls retain their required output type. Missing outputs are synthesized before bridge preparation so size, fingerprint, stored-context, and budget accounting match the forwarded payload. Remote-owner failover can recover from local pending state; when call ids exist only in remote memory, the local retry remains unchanged and any rejection is masked as retryable continuity loss.
- **GPT-5.6 ultra is client-plane metadata:** Sol and Terra may advertise and persist `ultra`, but outbound Responses policy sends upstream `max`. Direct `max` and `xhigh` remain unchanged.
- **No truncation support:** Requests that include `truncation` are rejected because upstream does not support it.
- **Compact as a separate contract:** Standalone compact is treated as a canonical opaque context-window contract, not as a variant of buffered normal `/responses`. Compact serialization removes full-response `tools` and `tool_choice`, but explicitly sends `parallel_tool_calls=false` because the upstream Responses Lite compact validator rejects the older missing-field shape.

## Constraints

- Upstream limitations determine available modalities, tool output, and overflow handling.
- Public `/v1` routes support locally persisted stored/background Responses and Conversations; the private native route remains constrained to the upstream-native request contract.
- `include` values must be on the documented allowlist.
- `truncation` is rejected.
- `previous_response_id` is forwarded when `conversation` is absent, but the `conversation + previous_response_id` conflict remains rejected.
- HTTP `/v1/responses` and HTTP `/backend-api/codex/responses` now use a server-side upstream websocket session bridge by default so repeated compatible requests can keep upstream response/session continuity without forcing clients onto the public websocket route.
- Codex-affinity HTTP bridge sessions can optionally use a conservative first-request prewarm (`generate=false`), but that behavior now stays behind an explicit flag so production defaults do not pay an extra upstream request unless operators opt in.
- When operators configure a multi-instance bridge ring, deterministic owner enforcement now applies only to hard continuity keys such as `x-codex-turn-state` and explicit session headers. Prompt-cache-derived bridge keys remain stable for local reuse, but in gateway-safe mode a non-owner replica may tolerate that locality miss and create or reuse a local session instead of failing with `bridge_instance_mismatch`.
- Codex-facing websocket routes now advertise `x-codex-turn-state` during websocket accept and honor client-provided turn-state on reconnect so routing can stay sticky at turn granularity even when the public websocket reconnects.
- HTTP responses routes now also return `x-codex-turn-state` headers so clients that persist response headers can promote later HTTP requests from prompt-cache affinity to stronger Codex-session continuity.
- `/v1/responses/compact` keeps a final-JSON contract and preserves the raw upstream `/codex/responses/compact` payload shape as the canonical next context window instead of rewriting it through buffered `/codex/responses` streaming.
- Compact transport failures fail closed with respect to semantics: no surrogate `/codex/responses` fallback and no local compact-window reconstruction.
- Compact transport may use bounded same-contract retries only for safe pre-body transport failures and `401 -> refresh -> retry`.
- `/v1/responses/compact` is supported only when the upstream implements it.
- `prompt_cache_key` affinity on OpenAI-style routes is intentionally bounded by a dashboard-managed freshness window, unlike durable backend `session_id` or dashboard sticky-thread routing.
- Codex-native direct websocket `/backend-api/codex/responses` treats upstream `previous_response_id` as an ephemeral anchor. If that anchor goes stale, the proxy must mask raw `previous_response_not_found` details and emit a sanitized `codex_previous_response_stale` classifier so compatible Codex clients can soft-reset and retry without `previous_response_id`.
- The Responses Lite marker is native Codex transport metadata. Direct and fallback HTTP/compact requests emit `x-openai-internal-codex-responses-lite: true`; HTTP-bridge and native WebSocket requests encode the equivalent marker in `response.create.client_metadata`, and upstream WebSocket handshakes omit the HTTP-only header. Non-native clients cannot opt in by supplying the header. Fresh full-resend replay drops marker-only trust unless its own body still contains `additional_tools`; transparent suppressed-created replay keeps continuity on the downstream-visible response id. Final request-frame serializers reapply the Lite `parallel_tool_calls=false` invariant so recovery cannot restore a client's incompatible `true` value.

## Fast Mode and Service Tiers

codex-lb accepts the OpenAI/Codex `service_tier` field on Responses and Chat
Completions compatible routes. The legacy `fast` spelling is accepted as an
alias and is forwarded upstream as the canonical `priority` tier.

Fast Mode is request-level intent, not a local speed guarantee. The upstream
Codex backend decides the actual tier for each completed response. codex-lb
therefore records three separate values in request logs:

- `requestedServiceTier`: what the client or API key asked for, after alias
  normalization.
- `actualServiceTier`: what upstream reported in the completed response, when
  upstream included it.
- `serviceTier`: the effective billable tier. This uses `actualServiceTier`
  when present and falls back to `requestedServiceTier` only when upstream omits
  the actual tier.

If a request is sent with `service_tier: "fast"` or `service_tier: "priority"`
and the completed row shows `requestedServiceTier: "priority"` but
`actualServiceTier: "default"`, codex-lb forwarded the priority request and
upstream chose the default tier. That can happen even when websocket transport
is active.

For OpenCode or Codex-compatible clients, enable Fast Mode by sending a
Responses request with:

```json
{
  "service_tier": "priority"
}
```

Clients that expose Fast Mode as `fast` may keep using that spelling; codex-lb
normalizes it to `priority` before forwarding.

API keys can also force the tier for traffic that uses that key. Set the key's
enforced service tier to `priority` or `fast`; both values are stored and
returned as `priority`.

To verify a completed Fast Mode request:

1. `Transport` should be `WS` if you are verifying the websocket Codex path.
2. `requestedServiceTier` should be `priority` when the client requested Fast
   Mode or the API key enforced it.
3. `actualServiceTier` is the upstream result. `default` means upstream did not
   grant priority for that response.

This distinction matters for quota and cost accounting: codex-lb prices the
request from the effective billable `serviceTier`, not from the requested tier
when upstream reports a different actual tier.

## Stored Responses and Conversations

The public `/v1` surface locally implements the OpenAI resource lifecycle that
the ChatGPT-backed Codex upstream does not expose. `store=true` persists a
terminal synchronous or streamed response, while `background=true` creates a
durable queued record and runs the existing Codex-LB execution path in an
application-owned task. The response can then be retrieved, cancelled while
active, deleted after it is terminal, and inspected through its input-items
list.

Resources are scoped to the downstream Codex-LB API key. Knowing an id from a
different key does not allow retrieval, deletion, cancellation, input-item
listing, or continuation through that local record. When API-key enforcement
is disabled, resources share the explicit local-anonymous scope.

Conversations are also local durable resources. Existing ordered conversation
items are expanded before new input for the private upstream request. A
successful response then appends its new input and output items to the local
conversation. The local `conv_*` id is not forwarded to ChatGPT as though it
were an upstream conversation resource.

Background tasks do not survive a process restart. Startup recovery converts
stranded `queued` or `in_progress` records to a retrievable failed response
with `background_worker_restarted`. Graceful shutdown cancels and awaits owned
tasks before database and HTTP-client teardown. In a multi-replica deployment,
cancellation must reach the instance that owns the active task; the portable
single-instance deployment does this naturally.

`POST /v1/responses/input_tokens` uses a deterministic local tokenizer for
visible text/tool JSON and identifies the result with
`x-codex-lb-token-count: local-compatible`. It is a context-sizing aid, not an
upstream billing claim. File/image references and unresolved upstream
`previous_response_id` context return an explicit 400 because exact local
counting would be false precision.

Current limitations remain explicit:

- `background=true` uses polling and therefore requires `stream=false`.
- stored-response retrieval with `stream=true` is not replayed as SSE.
- sampling, output-token-limit, safety identifier, user, and prompt-cache
  retention controls that the private upstream cannot honor still return
  `unsupported_parameter`.
- hosted tool availability remains model/upstream dependent even when the
  request schema accepts the tool declaration.

Example background flow:

```text
POST /v1/responses {"model":"gpt-5.6-sol","input":"work","background":true}
-> {"id":"resp_local...","status":"queued","background":true}
GET /v1/responses/resp_local...
-> {"id":"resp_local...","status":"completed",...}
```

## Include Allowlist (Reference)

- `code_interpreter_call.outputs`
- `computer_call_output.output.image_url`
- `file_search_call.results`
- `message.input_image.image_url`
- `message.output_text.logprobs`
- `reasoning.encrypted_content`
- `web_search_call.action.sources`

## Failure Modes

- **Stream ends without terminal event:** Emit `response.failed` with `stream_incomplete`.
- **Upstream error / no accounts:** Non-streaming responses return an OpenAI error envelope with 5xx status.
- **Compact upstream transport/client failure:** Retry only inside `/codex/responses/compact` when the failure is safely retryable; otherwise return an explicit upstream error without surrogate fallback.
- **HTTP bridge session closes or expires:** The next compatible HTTP `/v1/responses` or `/backend-api/codex/responses` request recreates a fresh upstream websocket bridge session; continuity is guaranteed only within the lifetime of one active bridged session.
- **Multi-instance routing without bridge owner policy:** if operators do not configure a bridge ring or front-door affinity, continuity can still fragment across replicas. With a configured bridge ring, hard continuity keys still fail closed on the wrong replica, while gateway-safe prompt-cache requests may accept locality misses instead of failing.
- **Codex websocket reconnects:** Reconnect continuity now depends on the client replaying the accepted `x-codex-turn-state`; generated turn-state is emitted on accept for backend Codex routes and echoed back when the client already supplies one.
- **Codex websocket stale previous-response anchors:** Direct backend Codex websocket stale-anchor failures are surfaced as `response.failed` / `codex_previous_response_stale` without the raw upstream code or missing `resp_...` id; OpenAI-compatible `/v1/responses` websocket clients continue to receive generic `stream_incomplete` masking.
- **Websocket handshake forbidden/not-found:** Auto transport now fails loud on `403` / `404` instead of silently hiding the websocket regression behind HTTP fallback.
- **Invalid request payloads:** Return 4xx with `invalid_request_error`.

## Error Envelope Mapping (Reference)

- 401 → `invalid_api_key`
- 403 → `insufficient_permissions`
- 404 → `not_found`
- 429 → `rate_limit_exceeded`
- 5xx → `server_error`

## Examples

Non-streaming request/response:

```json
// request
{ "model": "gpt-5.1", "input": "hi" }
```

```json
// response
{ "id": "resp_123", "object": "response", "status": "completed", "output": [] }
```

Cursor-style model alias request:

```json
{ "model": "gpt-5.4-mini-high", "input": "hi" }
```

This forwards upstream as `model: "gpt-5.4-mini"` with `reasoning.effort: "high"`.

## Operational Notes

- Pre-release: run unit/integration tests and optional OpenAI client compatibility tests.
- Smoke tests: stream a response, validate non-stream responses, and verify error envelopes.
- Post-deploy: monitor `no_accounts`, `upstream_unavailable`, compact retry attempts, and compact failure phases, especially on direct compact requests.
- Post-deploy: monitor HTTP bridge reuse/create/evict/reconnect counts and any `previous_response_not_found` or queue-saturation errors on `/v1/responses` and `/backend-api/codex/responses`.
- Post-deploy: monitor `capacity_exhausted_active_sessions`, Codex-session bridge reuse/evict counts, websocket handshake 403/404 rates after the narrower auto-fallback policy, and backend Codex HTTP vs websocket cache-ratio gaps.
- When tracing compact incidents, confirm that request logs and upstream logs show direct `/codex/responses/compact` usage without surrogate `/codex/responses` fallback.
- Post-deploy: monitor `no_accounts`, `stream_incomplete`, and `upstream_unavailable`.
- Post-deploy: monitor `codex_previous_response_stale` on `/backend-api/codex/responses`; recurring spikes mean clients are still relying on stale upstream anchors and should perform the documented full-context retry without `previous_response_id`.
- Websocket/Codex CLI tier verification runbook: `openspec/specs/responses-api-compat/ops.md`
