## Context

Claude Desktop sends Anthropic Messages content, while Codex LB executes OpenAI Responses requests. The two protocols impose different identifier and reasoning-continuity contracts. Responses accepts function names and call IDs up to 64 characters, and stateless reasoning continuation requires the upstream `encrypted_content` item to be returned and replayed. The current adapter forwards identifiers unchanged, drops Responses reasoning output, rejects assistant thinking input, and converts first-event SSE errors only on the optional HTTP-bridge path.

CLIProxyAPI provides useful reference patterns for 64-character call IDs, request-wide tool-name aliases, `reasoning.encrypted_content`, and Anthropic thinking/signature events. Codex LB needs stricter deterministic collision handling and must retain its existing validation, routing, and pre-stream retry ownership.

## Goals

- Keep every forwarded function name and call ID within the Responses 64-character limit without mismatching definitions, forced choices, calls, or outputs.
- Preserve original Claude-visible tool names even when the upstream uses a shortened alias.
- Round-trip only upstream-supplied reasoning summaries and opaque encrypted state.
- Return or retry an immediate upstream stream error before Anthropic response headers are committed.
- Provide regression canaries and useful logs without recording prompts, arguments, URLs, tool names, call IDs, signatures, or encrypted reasoning.

## Non-Goals

- Validate or decode the cryptographic contents of upstream reasoning state.
- Expose hidden chain-of-thought, synthesize signatures, or replay visible thinking text as model input.
- Add multimodal tool-result output, change web egress policy, add providers/models, or replace Codex LB with CLIProxyAPI.
- Buffer a normal response beyond the first semantic stream event.

## Decisions

### Deterministic request-local identifier map

Identifiers of 64 UTF-8 bytes or fewer remain byte-for-byte unchanged. Longer identifiers use a UTF-8-safe prefix plus `_` and the first 16 hexadecimal characters of SHA-256, producing at most 64 bytes. The hash is derived from the complete original value, so equal inputs are stable and distinct long values with the same prefix do not collapse under ordinary operation.

Tool names are mapped once before message history, tool definitions, and forced tool choice are translated. The original-to-upstream map is used for function definitions, `tool_choice`, and historical assistant calls. Its reverse map restores the original name in non-streaming and streaming Anthropic `tool_use` blocks. Hosted web aliases retain their existing special handling. Tool-use IDs use the same deterministic shortening independently for `function_call` and matching `function_call_output`; their Claude-visible response IDs remain whatever the upstream supplies because a new upstream call has no prior Anthropic ID to restore.

If two distinct original tool names ever produce the same mapped value, conversion fails locally instead of selecting an ambiguous tool. Duplicate definitions with the same original name also remain invalid rather than silently overwriting the reverse map.

### Opaque reasoning continuity

Claude Desktop requests opt into `reasoning.encrypted_content` output and automatic reasoning summaries through the existing Responses controls. A completed Responses reasoning item becomes an Anthropic `thinking` block only when it contains a non-empty upstream summary and/or non-empty encrypted content. Summary text becomes the visible `thinking` field; encrypted content becomes `signature`. Neither field is fabricated.

Streaming reasoning uses a thinking content block. Summary deltas become `thinking_delta`; the final upstream encrypted value becomes one `signature_delta` before the block closes. A signature-only item is still emitted so the next request can preserve state. Multiple reasoning items remain distinct ordered blocks.

On the next request, only an assistant `thinking` block with a non-empty signature is replayed as a Responses reasoning input item with `type=reasoning`, `encrypted_content=<signature>`, `summary=[]`, and `content=null`. Visible `thinking` text is not replayed as hidden reasoning. User thinking blocks, missing/empty signatures, or malformed fields fail locally with an Anthropic `invalid_request_error` rather than being dropped or forwarded ambiguously.

### First semantic stream event

The existing `_probe_stream_startup_error` remains the single low-level reader. The Anthropic direct path enables event-error conversion so a first `error` or `response.failed` event becomes a normal `Response` before the Anthropic `StreamingResponse` is constructed. Claude Desktop's existing bounded startup retry then sees recoverable 502/503 failures. Comments and normal first events are replayed unchanged, and no content-bearing event is consumed twice.

### Sanitized translation telemetry

Structured logs record only event name, direction, outcome, item kind, counts, and character/byte lengths. They never include identifier values, tool names, arguments, prompts, URLs, summary text, signatures, encrypted content, or credentials. Tests capture logs with sentinel secrets and assert those values are absent.

## Risks / Trade-offs

- A future Responses identifier limit differs from 64 bytes: the limit is isolated as one constant and protected by fixtures.
- Upstream reasoning event order varies: stream state accepts encrypted content from added or done items, emits the final value once, and closes pending reasoning at the next block or terminal event.
- A first event is a comment before an error: the low-level probe currently examines one item, so the Anthropic boundary must treat comment/keepalive frames as non-semantic and continue within a small bounded event count.
- Restoring original tool names requires request context: the parsed Messages request carries immutable alias maps through context relocation/compaction and batch execution.

## Verification

- RED/GREEN unit fixtures for 64-byte boundaries, common-prefix collisions, consistent tool choice/history mapping, reverse response names, opaque reasoning input/output, malformed thinking, and streaming reasoning ordering.
- Route regressions for first-event error, comment-then-error, retry eligibility, ordinary stream replay, and sanitized logs.
- Complete Anthropic unit/integration suite, Ruff, scoped ty, strict change/spec validation, diff checks, portable hash/compile checks, and one controlled Codex LB restart only after the user-facing runtime files are verified. Claude Desktop is not restarted.
