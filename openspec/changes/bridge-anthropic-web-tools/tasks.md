## 1. Contract

- [x] 1.1 Record the WebSearch/WebFetch server-tool compatibility contract, supported controls, explicit limitations, and VM-error boundary.
- [x] 1.2 Add normative requirements for server-tool identity, native hosted-tool mapping, forced choice, and fail-closed restrictions.

## 2. RED/GREEN implementation

- [x] 2.1 Add failing converter tests for WebSearch, WebFetch, deduplication, mixed client/server tools, and forced choice.
- [x] 2.2 Add failing route tests for Messages, token counting, and batch validation using server tools.
- [x] 2.3 Implement the smallest request/choice translation change that makes the regressions pass.
- [x] 2.4 Add explicit invalid-request coverage for mismatched identities, unknown server tools, and unsupported blocked-domain restrictions.

## 3. Verification and portable delivery

- [x] 3.1 Run focused Anthropic/OpenAI web-search tests, Ruff, scoped ty, and strict OpenSpec validation.
- [x] 3.2 Mirror changed runtime files into both portable Python roots and verify hashes plus embedded compilation.
- [x] 3.3 Restart CodexNeo through its existing app-owned action and verify health with minimal downtime.
- [x] 3.4 Run live Claude-facing WebSearch and WebFetch acceptance; record any structured-result/citation limitations.
- [x] 3.5 Update implementation tracking and handover with exact live evidence and the separate VM guest failure boundary.

## 4. Maximum-compatibility follow-up

- [x] 4.1 Add RED converter and route regressions proving only the authenticated loopback Claude Desktop profile omits `blocked_domains`.
- [x] 4.2 Thread the existing `claude_desktop` request classification through web-tool conversion and retain non-Desktop fail-closed behavior.
- [x] 4.3 Run focused and full Anthropic regressions, Ruff, scoped ty, and strict OpenSpec validation.
- [x] 4.4 Mirror `messages.py` into both portable roots, restart CodexNeo with minimal downtime, and run a small live blocked-domain WebSearch probe.
- [x] 4.5 Update implementation tracking and handover with the explicit deny-list compatibility trade-off and live result.

## 5. Oversized Cowork WebFetch follow-up

- [x] 5.1 Capture the exact Claude transcript and host log proving the Workspace MCP tool downloaded 520,961 bytes and Claude Code replaced the 519,714-character result before the next Messages request.
- [x] 5.2 Compare Anthropic's `max_content_tokens` guidance, OpenAI hosted `open_page` behavior, and similar router alias-deduplication patterns.
- [x] 5.3 Add RED converter and route regressions for public-URL alias replacement, official-tool deduplication, forced choice, and unchanged private/non-Desktop/deferred behavior.
- [x] 5.4 Implement the smallest Desktop-only eager-alias bridge without reading Claude result files or weakening ordinary function validation.
- [x] 5.5 Run focused/full Anthropic verification, strict OpenSpec validation, portable hash/compile checks, app-owned restart, and live retry of the exact `https://claude.com/docs` prompt.
- [x] 5.6 Update implementation tracking and handover with exact evidence and remaining private/local-result limitations.

## 6. Historical ToolSearch alias follow-up

- [x] 6.1 Reproduce the Claude Desktop HTTP 400 where a prior `tool_reference` names `mcp__workspace__web_fetch` after the current eager definition was replaced by hosted `web_search`.
- [x] 6.2 Add RED converter and route regressions for hosted-only history, mixed hosted/function history, unknown references, and unchanged deferred behavior.
- [x] 6.3 Resolve ToolSearch references through the same hosted-alias registry as forced choice, omit hosted aliases from client tool-search output, and suppress empty hosted-only bookkeeping pairs.
- [x] 6.4 Run focused/full Anthropic verification, Ruff, scoped ty, strict OpenSpec validation, portable hash/compile checks, and the app-owned minimal-downtime restart.
- [x] 6.5 Retest the exact historical ToolSearch plus public WebFetch request live, then update implementation tracking and handover with the reference-project comparison and final evidence.

## 7. Trustworthy hosted-result translation

- [x] 7.1 Add RED non-streaming and streaming regressions for exact opaque web results, citation preservation, and insufficient-data text fallback.
- [x] 7.2 Translate only complete upstream server-result/citation shapes and preserve the existing text lifecycle otherwise.
- [x] 7.3 Run focused/full Anthropic verification, Ruff, scoped ty, strict OpenSpec validation, and portable source hash/compile checks without restarting the active runtime.

## 8. Deferred Workspace WebFetch egress follow-up

- [x] 8.1 Reproduce Claude Desktop retaining `mcp__workspace__web_fetch` as a deferred client tool for a public URL, which leaves execution subject to Cowork's local egress allowlist.
- [x] 8.2 Route both eager and deferred public Workspace WebFetch aliases through the hosted Responses web tool while preserving client execution for loopback/private/local targets.
- [x] 8.3 Add unit and route-level regressions for deferred public routing, historical ToolSearch replay, deferred private/local preservation, historical-public/current-local precedence, and mixed public/local targets.
- [x] 8.4 Run the full verification ladder, mirror the portable runtime, restart CodexNeo, and complete fresh Claude Desktop WebFetch/WebSearch/ToolSearch acceptance without restarting Claude automatically. Record the separate Claude Auto-mode policy boundary when Cowork omits WebFetch from ToolSearch and executes the Workspace alias client-side.
