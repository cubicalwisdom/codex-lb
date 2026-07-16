## Why

Claude Desktop's client-side `ToolSearch` returns a standard Anthropic `tool_result` whose content is an array of `tool_reference` blocks. The current Messages translator accepts only text blocks inside `tool_result`, so one valid ToolSearch result makes the whole conversation history fail on every later turn with HTTP 400 `Only text tool_result blocks are supported.` WebFetch now reaches the requested site successfully, but the following ToolSearch result prevents Claude from continuing.

## What Changes

- Accept documented Anthropic `tool_reference` content without weakening validation for unrelated structured result types.
- Replay a complete Claude `ToolSearch` call and reference-only result as native Responses `tool_search_call` and `tool_search_output` items, including the referenced tool definitions already present in the request.
- Preserve documented `tool_reference` content from other client tools as deterministic compact JSON inside the matching `function_call_output` instead of dropping it or moving it into a user/system message.
- Keep existing string and text-only `tool_result` conversion unchanged.
- Add converter and HTTP-route regressions using the exact historical conversation shape that poisoned `/consolidate-memory`, `/setup-cowork`, and `/schedule` retries.

## Impact

- Changes only the Anthropic Messages request translator, tests, OpenSpec records, portable mirrors, and existing CodexNeo tracking files.
- Existing OpenAI-compatible, native Codex, ordinary function-tool, hosted web-tool, token-count, and batch routes continue through their current paths.
- No other repository is modified, and no external dependency is added.
- This change does not complete the separately tracked PDF/plain/CSV transport or add top-level deferred-tool optimization.
