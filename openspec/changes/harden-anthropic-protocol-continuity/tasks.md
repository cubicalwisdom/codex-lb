## 1. Identifier continuity

- [x] 1.1 Add RED fixtures for 64-byte boundaries, deterministic common-prefix collisions, request-wide tool-name consistency, paired call IDs, and reverse output names.
- [x] 1.2 Implement UTF-8-safe deterministic identifier mapping and thread immutable tool aliases through request, response, stream, context, and batch paths.
- [x] 1.3 Add sanitized identifier-mapping telemetry and leakage regressions.

## 2. Reasoning continuity

- [x] 2.1 Add RED fixtures for non-streaming and streaming Responses reasoning output, signature-only output, multipart ordering, and assistant replay.
- [x] 2.2 Request encrypted reasoning output and translate only upstream summaries/signatures into Anthropic thinking blocks.
- [x] 2.3 Replay valid assistant signatures as opaque Responses reasoning items and reject malformed or user-authored thinking blocks.
- [x] 2.4 Add sanitized reasoning telemetry and leakage regressions.

## 3. Pre-header stream errors

- [x] 3.1 Add a RED route regression for a direct first-event Responses error and a comment-then-error sequence.
- [x] 3.2 Reuse the existing startup probe to convert the first semantic error before Anthropic headers and preserve normal/comment event replay.
- [x] 3.3 Verify recoverable Desktop startup retry still occurs only before client-visible bytes.

## 4. Verification and portable delivery

- [x] 4.1 Run the complete Anthropic unit/integration suite, Ruff, scoped ty, strict OpenSpec validation, and `git diff --check`.
- [x] 4.2 Mirror verified runtime modules into both Electron portable Python roots and require identical SHA-256 hashes plus successful bundled-runtime compilation.
- [x] 4.3 Update `CODEXNEO_IMPLEMENTATION_LIST.md` and `HANDOVER_CODEXNEO_INTEGRATION.md` with evidence and remaining exclusions.
- [x] 4.4 Restart Codex LB once through the existing owner-controlled action, verify readiness/model discovery/live protocol canaries, and do not restart Claude Desktop.
