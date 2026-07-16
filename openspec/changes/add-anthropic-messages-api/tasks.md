## 1. Contract and authentication

- [x] 1.1 Add Anthropic error-format support and an `x-api-key`/Bearer compatibility dependency without changing existing route authentication.
- [x] 1.2 Add request conversion for supported Messages system/text/tool/tool-result payloads and explicit model-resolution rules.

## 2. Messages facade

- [x] 2.1 Add `POST /v1/messages` on an Anthropic-specific router and connect it to the existing Responses execution path.
- [x] 2.2 Translate completed Responses output into Anthropic Message objects and translate OpenAI-style failures into Anthropic errors.
- [x] 2.3 Translate normalized Responses SSE into ordered Anthropic Messages SSE events.

## 3. Verification and portable delivery

- [x] 3.1 Add focused request, output, stream, authentication, and route integration regressions.
- [x] 3.2 Run focused tests, static checks, and strict OpenSpec validation.
- [x] 3.3 Test the facade through an isolated source runtime without restarting the running portable application.
- [x] 3.4 Mirror verified runtime modules into both portable Python roots and verify hashes/compilation.
- [x] 3.5 Run a real Claude Code client smoke test when a compatible CLI is installed and configured.

## 4. Claude Desktop key-scoped discovery

- [x] 4.1 Add the local-only `claudedesktop` credential profile and the mapped Anthropic model catalog without changing the shared model registry.
- [x] 4.2 Route Claude Desktop Opus-family requests to Sol and Sonnet-family requests to Terra while preserving the original response model ID.
- [x] 4.3 Add regressions for key-scoped discovery, local-only selection, and the unchanged ordinary `/v1/models` contract.
- [x] 4.4 Run focused tests, strict OpenSpec validation, and an isolated runtime smoke without restarting the portable application.
- [x] 4.5 Refresh the advertised Claude Desktop IDs to the current Opus 4.8 and Sonnet 5 catalog entries while retaining the existing Sol/Terra routes.
- [x] 4.6 Translate text-only `system` and `developer` instruction messages emitted by Claude Desktop beta requests, while retaining standard Anthropic role validation for every other client.
- [x] 4.7 Map Claude Desktop `output_config.effort` values to the corresponding upstream Responses reasoning effort, including the documented high default.
- [x] 4.8 Add a persisted CodexNeo Sonnet reasoning selector and use it only as the fallback for Desktop Sonnet-family requests that omit `output_config.effort`.
- [x] 4.9 Add focused backend, API, and CodexNeo UI regressions; verify the portable backend and packaged frontend without restarting Codex Desktop.
- [x] 4.10 Add the Claude Messages token-count route and narrow Desktop startup/terminal-stream resilience coverage.
- [x] 4.11 Add the explicit CodexNeo **Restart Claude** dashboard action with package-scoped restart coverage.
