## Why

Native Codex WebSocket continuations already remember unfinished ordinary `function_call` items and synthesize a matching output when an interrupted turn continues without one. GPT-5.6 Responses Lite emits `custom_tool_call` items instead, so those calls are not tracked, their `custom_tool_call_output` type is not remembered, and the next `previous_response_id` request can be rejected with `No tool output found for custom tool call call_*`.

## What Changes

- Track terminal ordinary, custom, and apply-patch tool calls together with the output item type each call requires.
- On a continuation of the just-completed response, inject only missing outputs and use the matching output type.
- Recognize both ordinary and custom missing-tool-output upstream error wording.
- If upstream rejects a stale continuation before creating a response, retry once from the already-prepared safe full transcript without `previous_response_id`; keep short/delta-only continuations fail-closed.
- Preserve existing output items and never execute or replay a tool inside the proxy.

## Non-goals

- Do not change tool declarations, MCP behavior, model metadata, pricing, account routing, or tool execution.
- Do not execute or retry side-effecting tools automatically; the one-shot request replay only re-sends recorded input that is complete without the rejected anchor.
- Do not restart Codex Desktop or Electron.

## Impact

- Code: WebSocket/HTTP-bridge tool-call event tracking and native continuity state.
- Tests: focused proxy continuity regressions only.
- Spec: `responses-api-compat`.
