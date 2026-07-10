## ADDED Requirements

### Requirement: Native Responses Lite signaling is derived and continuity-aware

The proxy MUST derive the upstream Responses Lite signal from normalized input containing `additional_tools`, not from an inbound internal header or metadata marker. It MUST strip stale or untrusted markers and synthesize the transport-specific HTTP or WebSocket signal after alias normalization and API-key enforcement. A marker-only incremental WebSocket frame MAY retain the marker only when its `previous_response_id` equals the downstream-visible response id recorded by the most recently accepted Lite request for the same effective model. A missing or different anchor MUST have the marker stripped without clearing the earlier trusted continuity.

A transparent replay that suppresses a new `response.created` MUST keep continuity on the original downstream-visible id, not the hidden replay id. A fresh full-resend replay that clears `previous_response_id` MUST drop the marker unless the replay body itself still contains `additional_tools`; acceptance of a marker-stripped replay MUST NOT establish Lite continuity. An accepted Lite prewarm MAY establish continuity. HTTP-bridge trim, owner-forward, and retry paths MUST preserve an internally derived canonical marker even when the forwarded input delta no longer contains the stored Lite prefix.

#### Scenario: Marker-only incremental request follows an accepted Lite prewarm

- **GIVEN** a native full Lite request for an effective model reached `response.created`
- **WHEN** the same connection sends an incremental request for that model with the Lite metadata marker, the accepted response id as `previous_response_id`, and no repeated `additional_tools` item
- **THEN** the proxy forwards the canonical Lite WebSocket metadata
- **AND** a missing/different anchor or effective-model change strips the marker without clearing the trusted accepted anchor

#### Scenario: Untrusted marker cannot enable Lite

- **GIVEN** a request is not Lite-shaped and has no accepted same-model Lite continuity
- **WHEN** it supplies the internal Lite header or WebSocket metadata key
- **THEN** the proxy removes that signal before upstream forwarding

#### Scenario: Suppressed-created replay keeps the visible Lite anchor

- **GIVEN** a Lite request already exposed `response.created` downstream
- **WHEN** a transparent replay suppresses its new created event and rewrites events to the original visible response id
- **THEN** a same-model marker-only frame referencing the visible id remains trusted
- **AND** a frame referencing the hidden replay id has its marker stripped

#### Scenario: Fresh replay reclassifies the Lite marker from its body

- **GIVEN** a trusted incremental frame is replayed without `previous_response_id`
- **WHEN** the replay body has no `additional_tools` item
- **THEN** the replay omits the reserved marker and does not create a new trusted Lite anchor
- **BUT WHEN** the replay body retains `additional_tools`
- **THEN** it keeps the canonical marker and may establish new continuity after acceptance

#### Scenario: Bridge input trimming preserves internally derived Lite metadata

- **GIVEN** an HTTP bridge request derived Lite mode from a stored `additional_tools` prefix
- **WHEN** trim, owner-forward, or retry handling forwards only a later input delta
- **THEN** the forwarded WebSocket request still carries the internally derived Lite metadata

### Requirement: Non-message instruction-role directives remain byte-identical

The proxy MUST preserve any typed system/developer input item whose type is neither absent nor `message`. Preservation MUST apply through instruction normalization, input sanitization, omitted-instructions defaulting, serialization, and compact trimming. Preserved directives MUST bypass sanitizer removal of fields including `reasoning_content`, `reasoning_details`, `tool_calls`, and `function_call`, and MUST act as compact-trim anchors.

#### Scenario: Opaque developer directive survives every normalization stage

- **GIVEN** a Responses request contains a typed developer directive with opaque `reasoning_content`, `reasoning_details`, `tool_calls`, and `function_call` fields
- **WHEN** the proxy validates, sanitizes, compacts, and serializes the request
- **THEN** the directive remains in `input` byte-for-byte and in order
- **AND** omitted top-level `instructions` defaults to an accepted empty value

### Requirement: Interrupted tool outputs are typed and recovery-safe

The proxy MUST retain pending `function_call`, `custom_tool_call`, and `apply_patch_call` identities with their required output types across direct WebSocket and HTTP bridge continuations. Missing apply-patch outputs MUST use `apply_patch_call_output` with `status: failed`. HTTP bridge injection MUST occur before request preparation so size enforcement, fingerprints, stored context, and API-key usage budgeting observe the forwarded payload. Recovery and replay trimming MUST preserve typed outputs, including normal zero-input completed turns. A synthetic prewarm completion with zero output tokens MUST NOT replace the real continuity anchor. The existing one-shot safe full-transcript recovery for hidden orphan errors MUST remain available.

On owner-forward failure before any downstream bytes, local recovery MUST inject synthetic interrupted outputs only when the rebound local session retains pending tool-call state for the anchored response id. If recovery rebinds a fresh local session with no pending tool-call state, the proxy MUST resubmit the anchored request unchanged and MUST NOT fabricate tool outputs. If upstream then rejects the request with a missing-tool-output error, the proxy MUST mask the raw 400 and call id as a retryable continuity failure. Persisting pending call ids in the durable bridge store is outside this change.

#### Scenario: HTTP bridge prepares a typed interrupted output

- **GIVEN** a completed response has an unresolved apply-patch call
- **WHEN** the next anchored HTTP bridge request omits its output
- **THEN** one failed apply-patch output is injected before request preparation
- **AND** size, usage budget, fingerprint, stored context, retry payload, and replay trimming reflect that injected item

#### Scenario: Hidden orphan falls back to a safe transcript

- **GIVEN** upstream reports a missing tool output before `response.created` and the call id is not locally reconstructable
- **AND** request preparation retained a transcript that is complete without the rejected anchor
- **WHEN** the proxy attempts recovery
- **THEN** it replays that transcript once without `previous_response_id`
- **AND** unsafe short continuations remain fail-closed

#### Scenario: Owner-forward failover recovery without local pending state is a bounded gap

- **GIVEN** an anchored follow-up was forwarded to a remote owner and the relay fails before yielding bytes
- **AND** pending call metadata exists only in the remote owner's memory because the durable store does not persist call ids
- **WHEN** local recovery rebinds a fresh session with no pending tool-call state
- **THEN** the anchored request is resubmitted unmodified, without fabricated tool outputs
- **AND** any upstream missing-tool-output rejection is masked as a retryable continuity failure rather than exposing the raw 400 or call id

#### Scenario: Synthetic prewarm does not replace real continuity

- **GIVEN** a bridge session has a real completed-response anchor
- **WHEN** a synthetic request with `request_kind: prewarm` completes with zero output tokens
- **THEN** the prewarm does not replace the real session or durable anchor
- **AND** a normal zero-input completed turn may still update continuity and pending-call state

### Requirement: Missing-tool-output classification covers all tool call variants

The proxy MUST classify an upstream `invalid_request_error` with `param: input` whose message starts with `No tool output found for function call call_`, `No tool output found for custom tool call call_`, or `No tool output found for apply patch call call_` as a missing-tool-output continuity error. Existing masking and retry recovery MUST engage instead of forwarding the raw upstream 400.

#### Scenario: Custom tool call variant is masked on the HTTP bridge

- **WHEN** upstream returns `invalid_request_error` with `param: input` and `No tool output found for custom tool call call_x`
- **AND** the pending bridge request carries `previous_response_id`
- **THEN** the proxy rewrites the error to a retryable continuity failure
- **AND** the raw upstream message and call id are not exposed downstream

### Requirement: Ultra reasoning effort is aliased to max on the upstream wire

The proxy MUST forward an outbound Responses payload whose client-requested or API-key-enforced `reasoning.effort` resolves to `ultra` as `reasoning.effort: max`. Client catalog and persisted API-key configuration MUST retain `ultra`. Direct `max` and `xhigh` values MUST be forwarded unchanged. Automation dispatch paths are outside this selective reconciliation.

#### Scenario: Client-requested ultra forwards as max

- **WHEN** a client sends a Responses request for Sol with `reasoning: {"effort": "ultra"}`
- **THEN** the forwarded upstream payload uses `reasoning.effort: max`

#### Scenario: Enforced ultra forwards as max

- **GIVEN** an API key is configured with `enforcedReasoningEffort: ultra`
- **WHEN** a Responses request is proxied with that key
- **THEN** the forwarded upstream payload uses `reasoning.effort: max`
- **AND** the stored API-key policy remains `ultra`

#### Scenario: Max and xhigh remain unchanged

- **WHEN** a client sends `reasoning.effort: max` or `reasoning.effort: xhigh`
- **THEN** the forwarded upstream payload keeps the same value

## MODIFIED Requirements

### Requirement: Cursor GPT-5 model aliases normalize to canonical slugs

For Responses proxy traffic, the service MUST recognize Cursor-style GPT-5 model aliases formed by appending known suffix tokens (`minimal`, `low`, `medium`, `high`, `xhigh`, `extra`, `fast`, `priority`, `reasoning`, `thinking`) to supported GPT-5 family slugs, including `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna`. The resolver MUST match longer qualified canonical slugs before shorter family prefixes. Unknown suffix tokens MUST leave the requested model unchanged. `max` and `ultra` MUST NOT be treated as suffix tokens, and qualified canonical bases such as `gpt-5.1-codex-max` MUST be matched before shorter bases.

#### Scenario: Qualified mini model alias normalizes reasoning

- **WHEN** a client sends `model: gpt-5.4-mini-high`
- **THEN** the forwarded request uses `model: gpt-5.4-mini`
- **AND** it uses `reasoning.effort: high`

#### Scenario: Qualified codex model alias normalizes service tier

- **WHEN** a client sends `model: gpt-5.3-codex-fast`
- **THEN** the forwarded request uses `model: gpt-5.3-codex`
- **AND** it uses `service_tier: priority`

#### Scenario: GPT-5.6 personality alias normalizes reasoning and service tier

- **WHEN** a client sends `model: gpt-5.6-sol-extra-high-fast`
- **THEN** the forwarded request uses `model: gpt-5.6-sol`
- **AND** it uses `reasoning.effort: high`
- **AND** it uses `service_tier: priority`

#### Scenario: Max-qualified canonical base keeps its identity

- **WHEN** a client sends `model: gpt-5.1-codex-max-fast`
- **THEN** the forwarded request uses `model: gpt-5.1-codex-max`
- **AND** it uses `service_tier: priority`

#### Scenario: GPT-5.6 max and ultra labels are not rewritten

- **WHEN** a client sends `model: gpt-5.6-sol-max` or `model: gpt-5.6-sol-ultra`
- **THEN** the model label remains unchanged
