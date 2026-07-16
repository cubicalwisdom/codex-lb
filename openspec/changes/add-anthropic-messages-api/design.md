## Context

codex-lb's canonical execution format is the OpenAI Responses request and SSE stream. The portable application already owns account selection, model policy, usage settlement, HTTP bridge continuity, and upstream error handling there. Claude Code instead calls the Anthropic Messages API and normally authenticates with `x-api-key`, so a separate inbound facade is required.

The facade must not create another upstream client, duplicate selection logic, or weaken the existing Bearer-only routes. The requested Anthropic model might be a Claude model alias; codex-lb must not silently select an account model for that alias.

## Goals / Non-Goals

**Goals:**

- Provide `POST /v1/messages` for Claude Code text-and-tools turns in streaming and non-streaming modes.
- Provide `POST /v1/messages/count_tokens` as a compatible local input-token estimate for Claude Desktop discovery and preflight calls.
- Reuse the existing Responses path with public-route cache affinity, account policy, API-key limits, and HTTP bridge behavior.
- Preserve system text, ordered conversation messages, function tool definitions, assistant tool use, and user tool results.
- Return Anthropic error and SSE event shapes while retaining codex-lb security and rate-limit headers.
- Allow an Anthropic model label only when the selected codex-lb API key explicitly enforces its upstream model, or when a local Claude Desktop request presents the dedicated `claudedesktop` credential; otherwise require a codex-lb model identifier.
- Keep Claude Desktop discovery separate from the shared OpenAI-compatible catalog so existing portable clients do not see or select synthetic Claude model IDs.
- Let CodexNeo supply the Sonnet fallback effort because Claude Desktop exposes its effort picker for Opus but not for Sonnet when using a custom endpoint.

**Non-Goals:**

- Do not emulate every Anthropic API feature, implement prompt caching, upload/document/audio blocks, batch APIs, or automatic Claude Code configuration writes.
- Do not select or configure a default upstream model on the user's behalf.
- Do not change native Codex, OpenAI-compatible, account-routing, or portable Electron restart behavior.

## Decisions

- **Use a separate `/v1` router with Anthropic-specific dependencies.** This permits `x-api-key` and Anthropic error envelopes without altering the existing OpenAI router's global Bearer/OpenAI-error contract.
- **Translate at the public boundary.** An Anthropic request becomes a `ResponsesRequest`; all model enforcement, reservation, upstream streaming, and settlement remain in `_stream_responses` / `_collect_responses`.
- **Make model choice explicit.** A caller can send an actual codex-lb model identifier. A Claude model label is accepted only when an authenticated API key has `enforced_model`; that policy is the explicit owner-selected mapping. This avoids guessing a model from the current account catalog.
- **Use a local Claude Desktop profile rather than mutating the registry.** A loopback request whose credential is exactly `claudedesktop` receives a two-model Anthropic catalog. `opus` and `claude-opus-*` resolve to `gpt-5.6-sol`; `sonnet` and `claude-sonnet-*` resolve to `gpt-5.6-terra`. All other `/v1/models` callers continue through the unmodified registry-backed response. The profile selector is never accepted for remote requests.
- **Persist the Sonnet fallback in CodexNeo settings.** The CodexNeo page provides Low, Medium, High, Extra (`xhigh`), and Max. The adapter uses this value only for local `claudedesktop` Sonnet-family requests that omit `output_config.effort`; an explicitly supplied effort and all Opus behavior remain unchanged.
- **Count tokens locally.** The count route validates and normalizes the supported Messages payload, then delegates to the established Responses local estimator. It returns `input_tokens` with the same local-compatible marker as the Responses token-count route; it never creates an upstream request.
- **Make the Desktop transport resilient without changing other callers.** The literal local `claudedesktop` profile bypasses the optional owner-forward HTTP bridge, performs bounded retries only before any stream bytes are returned, and may synthesize a terminal text-only response after a `stream_incomplete` error. Tool-use and empty streams remain explicit failures so no action or output is invented.
- **Restart Claude only on explicit operator action.** CodexNeo invokes a Windows-specific package-scoped restart command from the authenticated dashboard action. It requests a graceful close first, stops only remaining Claude package processes, and relaunches the installed Claude Desktop app.
- **Stream from normalized Responses SSE.** The adapter consumes codex-lb's public Responses events and emits the Anthropic event sequence (`message_start`, content-block events, `message_delta`, `message_stop`). It does not buffer an active response to synthesize a stream.
- **Accept both authentication headers only when they agree.** Claude Code may send `x-api-key` and `Authorization: Bearer` together. Either is accepted; conflicting values are rejected before key lookup.

## Reference Implementations

The compatibility design is not unique. Public projects fall into distinct reference tiers:

- **Claude Desktop/Cowork third-party inference:** `decolua/9router` and `quangdang46/openproxy` are the closest overall references. Both contain dedicated Cowork settings code that writes `inferenceGatewayBaseUrl`, `inferenceGatewayApiKey`, and `inferenceModels`, expose an Anthropic `/v1/messages` surface, and route to subscription or API-key providers. Their Cowork-specific configuration and private-tool handling make them the primary application-compatibility references for this change.
- **ChatGPT Codex Responses transport:** `raine/claude-code-proxy` and `Jakevin/CC-Adapter` are the primary direct references for translating Anthropic Messages into the ChatGPT Codex Responses backend. The latter also supports native OpenAI and arbitrary OpenAI-compatible API keys.
- **Generic Claude-to-OpenAI translation:** `m0n0x41d/anthropic-proxy-rs` explicitly claims Claude Desktop support, while `shantoislamdev/claude-adapter`, `1rgs/claude-code-proxy`, and `fuergaosi233/claude-code-proxy` primarily target the Claude Code CLI. They are useful schema and streaming references but do not by themselves prove full Cowork compatibility.
- **Reverse direction:** `RichardAtCT/claude-code-openai-wrapper` and `schmarta/claude-code-openai-server` expose Claude as an OpenAI-compatible backend. They solve the opposite flow and are not implementation references for this facade.

Codex LB combines the first two tiers: Claude Desktop/Cowork-facing compatibility plus the existing multi-account ChatGPT Codex transport. Reference behavior is adopted only when it preserves this repository's authentication, model-policy, safety, and portable-runtime contracts.

## Risks / Trade-offs

- **Claude Code sends an unsupported block or future parameter** -> reject the block with an Anthropic `invalid_request_error` rather than silently dropping conversation content.
- **The ChatGPT/Codex upstream cannot honor Anthropic output controls exactly** -> accept the required `max_tokens` field but derive terminal stop reasons from actual Responses terminal state; do not claim an unsupported exact token cap.
- **Responses events can be partial or malformed** -> produce an Anthropic `error` event or non-streaming `api_error`, never fabricate tool arguments or terminal success.
- **Portable source/mirror drift** -> verify source and both portable Python roots after focused tests, with activation deferred to the user's normal portable restart.
- **Synthetic model IDs leak into other clients** -> generate the Anthropic list only after the local `claudedesktop` profile has been selected; do not add those IDs to the upstream model registry or dashboard catalog.
- **Claude Desktop hides Sonnet effort controls** -> persist an owner-selected Sonnet fallback in the local CodexNeo settings file, rather than mislabeling Sonnet as Opus or changing its Sol/Terra routing.
- **Claude Desktop probes token count or loses a terminal frame** -> answer the local count probe without upstream capacity and preserve already-delivered text through a narrow, no-tool terminal recovery; do not retry after data has been sent.

## Migration Plan

1. Add the normative compatibility spec and request/response converter tests.
2. Add the isolated facade and auth dependency; run focused unit and route integration tests against a mocked Responses upstream.
3. Validate the OpenSpec change, run repository checks, and test an isolated source runtime.
4. Mirror verified Python modules into both portable runtime roots. Do not restart the portable Electron application or alter Claude Code configuration automatically.
