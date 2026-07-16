## 1. Contract and persistence

- [x] 1.1 Add normative requirements for attachment, cache, context, batch, and overload behavior.
- [x] 1.2 Add durable batch models, repository/service, and a single-head migration.
- [x] 1.3 Add a bounded batch runtime manager with orderly startup/shutdown handling.

## 2. Messages expansion

- [x] 2.1 Translate supported image content blocks and reject invalid attachment sources before upstream execution.
- [ ] 2.2 Implement an end-to-end PDF/plain/CSV document path that completes through the ChatGPT-backed Responses transport; the current inline `input_file` shape fails live-provider acceptance.
- [x] 2.3 Normalize cache controls into deterministic prompt-cache affinity and accurate response usage fields.
- [x] 2.4 Validate context-management, enforce the provider-safe context budget, and reuse upstream compact artifacts internally.
- [x] 2.5 Add bounded pre-stream capacity/upstream recovery and sanitized outcome telemetry.
- [x] 2.6 Allow only the authenticated loopback `claudedesktop` profile to compact near-limit history when `context_management.edits` is omitted, while preserving all existing safety failures.
- [x] 2.7 Preserve over-limit Claude Desktop system instructions as bounded compactable input instead of forwarding an invalid Responses `instructions` field.

## 3. Batches API

- [x] 3.1 Add create, retrieve, list, cancel, delete, and JSONL-results routes with Anthropic error envelopes.
- [x] 3.2 Execute batch requests through the existing Responses collection path and persist terminal results.
- [x] 3.3 Recover safe queued/in-progress batch work at startup and cancel cleanly at shutdown.

## 4. Verification and portable closeout

- [x] 4.1 Add unit and integration regressions for attachments, cache affinity, context limits, recovery, and batch lifecycle.
- [x] 4.2 Run focused tests, Ruff, ty, strict OpenSpec validation, migration checks, and frontend checks where affected.
- [x] 4.3 Mirror verified runtime files into the Electron portable package, then perform one controlled backend restart and live smoke verification.
- [x] 4.4 Update handover and implementation tracking with the staged endpoint and remaining protocol exclusions.
- [x] 4.5 Add regression coverage for Desktop automatic compaction, non-Desktop opt-in enforcement, uncompactionable single-turn input, and compact-transport failure.
- [x] 4.6 Run live acceptance for images, cache affinity, batch success/cancel/delete/JSONL, validation errors, tool use, streaming, token counting, model isolation, and Sonnet fallback effort.
- [ ] 4.7 Complete live PDF/plain/CSV acceptance after the document transport is replaced.
- [x] 4.8 Add RED/GREEN route coverage for the exact 1,048,576-character instruction boundary, mirror the portable runtime, restart CodexNeo, and retry the affected Desktop conversation.
