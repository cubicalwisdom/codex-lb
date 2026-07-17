## Context

The Anthropic request converter currently has one tool path: every entry must contain `name` and object `input_schema`, then it becomes a Responses function tool. Anthropic server tools use a discriminated versioned `type` such as `web_search_20250305` or `web_fetch_20250910` and do not contain `input_schema`. A live request with the official WebSearch shape reproduces the reported 400. A direct live Responses request with `tools: [{"type":"web_search"}]` completes on the current Terra route and returns a `web_search_call` followed by message text.

## Goals

- Make Claude Desktop built-in WebSearch and WebFetch execute through the already-working Responses hosted web-search capability.
- Preserve strict object-schema validation for user-defined/client function tools.
- Preserve enforceable domain and location controls.
- Keep the change local to request translation and tool-choice normalization.

## Non-Goals

- Execute searches through Tavily, Brave, Bing, or another adapter-owned provider.
- Depend on Claude Cowork's VM guest to execute web tools.
- Emulate Anthropic WebSearch billing, `max_uses`, programmatic callers, response-inclusion controls, or structured server-tool result/citation blocks.
- Repair the separate Cowork VM lifecycle failure.

## Decisions

### Supported server-tool identities

The converter recognizes only documented server-tool versions whose `name` and `type` agree. Supported WebSearch types are `web_search_20250305`, `web_search_20260209`, and `web_search_20260318`; supported WebFetch types are `web_fetch_20250910`, `web_fetch_20260209`, `web_fetch_20260309`, and `web_fetch_20260318`. A mismatched name/type, an unknown version, or an unknown server-tool family fails locally. This prevents an arbitrary or future-incompatible type string from bypassing client-function schema validation.

### Hosted-tool mapping

One or both recognized Anthropic web tools map to a single Responses `{"type":"web_search"}` entry. Deduplication avoids forwarding duplicate hosted tools when Desktop advertises both. The Anthropic capabilities remain distinct: WebSearch discovers relevant URLs, while WebFetch reads a specific URL or PDF. Responses exposes those behaviors as actions of one hosted tool: `search` is the WebSearch equivalent, while `open_page` and `find_in_page` are the closest WebFetch equivalents. The model chooses the required action from the prompt and available URL context. Duplicate web tools are deduplicated only when their enforceable hosted-tool configuration is identical; conflicting allowed-domain or location controls fail locally instead of choosing or weakening either policy.

`allowed_domains` maps to `filters.allowed_domains`. `user_location` maps to the corresponding Responses location object. The mapped tool has no equivalent for Anthropic `blocked_domains`. Ordinary API clients therefore continue to fail locally rather than silently broadening access. The authenticated loopback-only `claudedesktop` profile deliberately chooses maximum application compatibility: it accepts and omits `blocked_domains`, including non-empty lists, so Claude Desktop's built-in WebSearch can execute. That profile-specific omission is an explicit security trade-off and the upstream search is not guaranteed to honor Claude's deny-list. Anthropic controls without a hosted Responses equivalent—including `max_uses`, `allowed_callers`, `response_inclusion`, WebFetch `citations`, `max_content_tokens`, and `use_cache`—are accepted as compatibility metadata but are not forwarded. Generic tool-definition controls such as `cache_control`, `strict`, and `defer_loading` are likewise not forwarded. These differences are documented because the mapped upstream cannot exactly enforce Anthropic's cost bounds, cache behavior, dynamic-caller selection, or structured-result inclusion.

### Claude Desktop Workspace WebFetch alias

Cowork host-loop sessions replace Claude Code's `WebFetch` builtin with the eager MCP client tool `mcp__workspace__web_fetch`. That client tool downloads the full page locally. When a page is larger than Claude Code's tool-result ceiling, Claude saves the body to a local `tool-results` file and sends only an `Error: result (...) exceeds maximum allowed tokens` marker to the Messages endpoint. Codex LB cannot recover the original result from that request without reading a caller-named host path, which would add an unsafe filesystem capability and would be too late to enforce a content bound.

For the authenticated loopback-only `claudedesktop` profile, an eager Workspace WebFetch definition is therefore treated as a compatibility alias for the Responses hosted `web_search` tool only when the current conversation contains an explicit public HTTP(S) URL. The hosted model can use `open_page` or `find_in_page` and return bounded answer text without sending the raw page through Claude's client-tool result channel. If an official Anthropic web server tool is also present, its enforceable hosted controls win and the alias is deduplicated into that same hosted tool.

The alias is not replaced for non-Desktop callers, URLs classified as loopback/private/local, conversations with no explicit public URL, or conversations whose latest actual human prompt mixes public and local targets. Those cases retain the original client-function definition, preserving Workspace access and ToolSearch replay. For the authenticated loopback Desktop profile, an eligible public-only alias is replaced whether it is eager or marked `defer_loading: true`; historical ToolSearch references remain resolvable through hosted-alias bookkeeping. This bridge deliberately does not open Claude's saved result files, truncate arbitrary client-tool output, resolve hostnames, or pretend that OpenAI exposes an exact numeric equivalent of Anthropic `max_content_tokens`.

Claude can retain an earlier client-executed ToolSearch result whose `tool_reference` names `mcp__workspace__web_fetch` even when the current request advertises the same tool eagerly. If the current request replaces that eager definition with hosted `web_search`, validation must resolve the original name through the same alias registry used by forced choice. The alias must not be serialized into `tool_search_output.tools`: OpenAI client tool search loads functions, namespaces, or MCP servers, while the hosted web tool is declared at the request level. When a historical ToolSearch result selected only replaced hosted aliases, the adapter omits that call/output bookkeeping pair. When the result selected hosted aliases plus ordinary functions, it preserves the pair with only the ordinary function definitions. Unknown references still fail locally.

### Cowork gateway references

`decolua/9router` and `quangdang46/openproxy` confirm that Claude Desktop/Cowork third-party inference is an established public gateway pattern, not a Codex LB-only design. Both configure Cowork's inference gateway fields and explicitly recognize `WebSearch`, `WebFetch`, and `mcp__workspace__web_fetch`. Their replacement-MCP path strips the built-in aliases when Exa or Tavily tools are present. Codex LB instead maps an eligible public fetch to the already-available OpenAI hosted `web_search` tool, so it must retain a hosted-alias registry for forced choice and historical ToolSearch validation rather than depend on a replacement MCP server.

`raine/claude-code-proxy` remains the strongest reference for the ChatGPT Codex Responses transport and hosted web-search behavior, while `Jakevin/CC-Adapter` is a direct reference for routing Anthropic Messages to both native OpenAI and Codex OAuth providers. These projects establish the surrounding protocol pattern even where their exact Workspace-alias lifecycle differs.

### Tool choice

Anthropic `auto`, `any`, and `none` keep their existing Responses equivalents. A forced `tool` choice whose name is `web_search` or `web_fetch` becomes the hosted Responses web-search choice. Other named choices remain function choices and still require a matching client tool.

### Responses

The Responses hosted tool executes inside the model turn. Existing non-streaming and SSE translation continues to emit final Anthropic text and terminal usage. `web_search_call` lifecycle items are ignored in this first compatibility slice, matching the current handling of non-message hosted-tool items. Structured Claude search cards and citation blocks can be added independently without blocking functional search.

### Error handling

Malformed server-tool fields, mismatched name/type, unsupported deny-list restrictions from non-Desktop callers, and unknown server-tool types return Anthropic `invalid_request_error` before upstream execution. The loopback-only Desktop profile omits deny-list restrictions as described above. Ordinary tools without object `input_schema` continue to return the existing validation error.

## Verification

- RED/GREEN unit coverage for WebSearch, WebFetch, deduplication, mixed function/server tools, forced choice, compatible controls, Desktop-only deny-list omission, and non-Desktop fail-closed restrictions.
- Route coverage proving `/v1/messages`, `/v1/messages/count_tokens`, and Message Batch validation accept the supported server tools.
- Existing Anthropic and OpenAI web-search regressions remain green.
- Mirror changed production files to both portable Python roots, verify hashes/compile, restart CodexNeo with the existing app-owned action, and run live Claude-facing WebSearch and WebFetch prompts.
