## Context

The current converter translates every assistant `tool_use` to a Responses `function_call` and every user `tool_result` to `function_call_output`. `_tool_result_output()` joins text blocks and rejects every other nested block. A live Claude Desktop session produced `[{"type":"tool_reference","tool_name":"..."}]` after its `ToolSearch` call; that record remains in full conversation history, so unrelated later slash commands re-trigger the same local 400 before upstream execution.

Anthropic documents `tool_reference` as the client-side ToolSearch result format. Current compatible gateways use three approaches: older adapters keep only text and lose the reference; OpenClaude renders the reference as text while retaining the tool result; and `caozhiyuan/copilot-api` maps complete pairs to native Responses `tool_search_call`/`tool_search_output` items. A live loopback probe against this project's GPT-5.6/Codex upstream accepted a replayed native pair and completed with HTTP 200.

## Goals

- Recover existing Claude Desktop conversations containing historical `tool_reference` results.
- Preserve tool-call/result pairing and the selected tool definitions.
- Use the native Responses lifecycle where the Anthropic history provides an unambiguous complete ToolSearch pair.
- Retain a safe, deterministic fallback for documented references outside that exact lifecycle.
- Preserve all existing text-result behavior.

## Non-Goals

- Convert the top-level Claude ToolSearch definition into a Responses deferred-tool catalog.
- Remove ordinary tool definitions from the upstream request for token optimization.
- Add support for image, document, or search-result blocks nested inside `tool_result`; those require their own transport acceptance work.
- Change hosted WebSearch/WebFetch execution or the separately pending document transport.

## Decisions

### Pre-scan complete ToolSearch pairs

Before translating messages, the adapter pre-scans assistant `tool_use` blocks and matching user `tool_result` blocks. A pair is eligible for native mapping only when the assistant tool name is exactly `ToolSearch`, the result content is a non-empty array containing only well-formed `tool_reference` objects, and every referenced name resolves to an ordinary converted function tool supplied in the same top-level `tools` array.

The pre-scan is necessary because the assistant call must be typed consistently with its later output. Incomplete calls, string results, mixed text/reference results, and other tool names remain ordinary function call/output pairs.

### Native complete-pair mapping

An eligible assistant call becomes:

```json
{"type":"tool_search_call","call_id":"...","arguments":{},"execution":"client","status":"completed"}
```

Its matching result becomes:

```json
{"type":"tool_search_output","call_id":"...","tools":[...],"execution":"client","status":"completed"}
```

The `tools` array contains the converted Responses function definitions named by the references, in reference order with duplicate names removed. `is_error: true` produces `status: "incomplete"`. An unknown reference fails locally with an Anthropic `invalid_request_error` instead of fabricating a definition.

### Deterministic fallback

A `tool_reference` in a non-ToolSearch or mixed structured result remains inside the matching `function_call_output`. The complete ordered content array is serialized as compact canonical JSON with sorted object keys. This preserves the reference and adjacent text without injecting untrusted tool content into instructions or a separate user message.

Unrelated nested content types retain the current explicit rejection. String results and arrays containing only text blocks retain the current output exactly.

### Compatibility boundary

The top-level tool list is unchanged: Claude client tools, including `ToolSearch`, continue to be advertised as ordinary Responses functions. Native items are used only to replay an already completed, unambiguous historical pair. This keeps current tool generation stable while using the upstream's verified native replay support.

## Verification

- RED/GREEN unit coverage for the exact ToolSearch/reference pair, multiple references, unknown references, deterministic fallback, and unchanged text results.
- HTTP-route coverage proving a Claude Desktop request with the poisoned historical sequence reaches the collection path and returns HTTP 200.
- Focused and full Anthropic suites, Ruff, scoped ty, strict change/spec validation, and whitespace checks.
- Identical source and both portable `messages.py` copies by SHA-256 plus bundled compilation.
- One controlled Codex LB restart after drain/health checks, followed by retry of the same Claude conversation and fresh WebFetch/WebSearch/ToolSearch acceptance.
