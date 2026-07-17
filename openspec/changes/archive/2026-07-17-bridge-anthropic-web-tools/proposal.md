## Why

Claude Desktop advertises built-in WebSearch and WebFetch as Anthropic server tools. Those tool definitions intentionally omit `input_schema`, but the current Messages adapter validates every tool as a client function and returns HTTP 400 before execution. The existing Responses path already executes its native hosted `web_search` tool successfully, so the adapter should bridge the compatible server-tool family instead of rejecting it.

## What Changes

- Recognize supported versioned Anthropic `web_search_*` and `web_fetch_*` server-tool definitions without weakening validation for ordinary client tools.
- Collapse the supported Anthropic web-tool set into one native Responses `web_search` hosted tool and preserve compatible allowed-domain and user-location controls.
- Translate a forced Anthropic web-tool choice to the Responses hosted-tool choice while retaining existing function-tool choice behavior.
- Return explicit Anthropic invalid-request errors for restrictions that cannot be enforced by the mapped upstream rather than silently weakening them.
- Route Claude Desktop's eager `mcp__workspace__web_fetch` compatibility alias through the hosted web tool when the active conversation contains an explicit public HTTP(S) URL, avoiding the Desktop host loop's unbounded raw-page result path.
- Keep that hosted alias resolvable when an existing Claude ToolSearch result refers to the original Workspace name, without reintroducing the alias as a client-executed function.
- Add request, token-count, batch-validation, streaming, and live portable regressions for both built-in web tools.

## Impact

- Changes only the Anthropic Messages facade and its portable mirrors; existing OpenAI-compatible and native Codex routes remain unchanged.
- Uses the existing Responses hosted web-search execution and account/quota path; no external search provider, API key, or new network client is added.
- WebSearch/WebFetch completion text is returned through the existing Anthropic text stream. Structured Anthropic server-tool result cards and citation-block parity remain a separate follow-up.
- Private/local Workspace WebFetch targets and deferred ToolSearch definitions remain client-executed; the adapter does not read Claude's saved oversized-result files or broaden host filesystem access.
- Historical ToolSearch bookkeeping that selects only a Workspace alias replaced by the hosted tool is omitted from the Responses transcript; mixed selections retain their ordinary function definitions while omitting only the hosted alias.
- The unrelated Claude Cowork `VM guest is not connected` failure is outside this change.
