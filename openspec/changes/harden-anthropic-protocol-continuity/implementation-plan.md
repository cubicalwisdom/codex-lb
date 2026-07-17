# Anthropic Protocol Continuity Implementation Plan

> **For agentic workers:** Implement each task test-first and record evidence before checking it complete.

**Goal:** Make Claude Desktop tool identity, opaque reasoning continuation, and immediate stream errors reliable through the existing Codex LB Responses transport.

**Architecture:** Build one deterministic request-local identifier map in the Anthropic translator and carry its immutable reverse aliases with `AnthropicMessagesRequest`. Extend the existing response/stream state for reasoning items. Enable bounded semantic startup-error conversion on the existing direct stream path. Use structured sanitized logs for canaries.

**Tech Stack:** Python 3.13, Pydantic Responses models, FastAPI/Starlette SSE, pytest, Ruff, ty, OpenSpec, Windows Electron portable runtime.

## Global constraints

- Work only in the isolated `codex/harden-anthropic-protocol-continuity` worktree created from the exact dirty parity snapshot.
- Do not modify, stage, reset, stash-pop, or clean the active dirty `codexneo-portable-windows` checkout.
- Do not restart Claude Desktop. Restart Codex LB only after tests, hashes, and portable compilation pass.
- Do not add a sidecar, new provider, tool-result multimodality, or unrelated cleanup.
- Never log translated values or encrypted reasoning content.

### Task 1: Establish baseline and identifier RED

**Files:** `tests/unit/test_anthropic_messages.py`, `tests/integration/test_anthropic_messages_api.py`

- [x] Run the complete focused baseline in the isolated snapshot.
- [x] Add fixtures for 64-byte pass-through, >64-byte UTF-8-safe shortening, two equal-prefix long names/IDs, forced choice, historical call/result, and response/stream reverse names.
- [x] Add a log-capture fixture with sentinel identifier values.
- [x] Run selected tests and require failures that show unbounded or inconsistent identifiers.

### Task 2: Implement identifier mapping GREEN

**Files:** `app/core/anthropic/messages.py`, `app/modules/proxy/api.py`

- [x] Add one 64-byte identifier helper using a UTF-8-safe prefix and 16-hex SHA-256 suffix.
- [x] Construct and validate original-to-upstream and upstream-to-original tool-name maps before translating tools/history/choice.
- [x] Map paired historical call IDs deterministically and restore tool names in non-streaming, streaming, and batch output.
- [x] Preserve alias maps when context instructions are relocated or history is compacted.
- [x] Emit length-only identifier telemetry, run the RED selection, and require GREEN.

### Task 3: Add reasoning RED and GREEN

**Files:** `tests/unit/test_anthropic_messages.py`, `tests/integration/test_anthropic_messages_api.py`, `app/core/anthropic/messages.py`, `app/modules/proxy/api.py`

- [x] Add failing non-stream fixtures for summary+encrypted, signature-only, and assistant signature replay.
- [x] Add failing stream fixtures for added/delta/done ordering, final signature replacement, multipart items, and signature-only blocks.
- [x] Add malformed/missing signature and user-thinking rejection fixtures plus sentinel log assertions.
- [x] Set Desktop Responses `reasoning.summary=auto` and include `reasoning.encrypted_content`.
- [x] Add opaque assistant replay and non-stream/stream output conversion without replaying visible thinking text.
- [x] Emit length/count-only reasoning telemetry and require the selected suite GREEN.

### Task 4: Prove and close the startup SSE boundary

**Files:** `tests/integration/test_anthropic_messages_api.py`, `app/modules/proxy/api.py`

- [x] Add a route test whose direct service yields `response.failed` as its first event and observe the pre-fix HTTP 200 failure.
- [x] Add comment-then-error, ordinary first-event, and recoverable-retry fixtures.
- [x] Extend the existing startup probe to skip only bounded comments/keepalives and enable event conversion for the Anthropic direct path.
- [x] Require errors to be mapped before headers while comments/normal events are replayed exactly once.

### Task 5: Full verification and delivery

**Files:** OpenSpec tasks, portable mirrors, `CODEXNEO_IMPLEMENTATION_LIST.md`, `HANDOVER_CODEXNEO_INTEGRATION.md`

- [x] Run the equivalent explicit-venv focused gate, including `tests/unit/test_openai_requests.py` (`229` passed).
- [x] Run Ruff on changed Python/tests and scoped `ty` on production modules.
- [x] Run `openspec validate harden-anthropic-protocol-continuity --type change --strict --no-interactive`, stable spec validation, and `git diff --check`.
- [x] Mirror changed runtime modules to both portable Python roots, compare SHA-256 hashes, and compile with both bundled interpreters.
- [x] Update tracking documents with exact evidence and exclusions.
- [x] Restart Codex LB, verify health/readiness, unchanged Claude model discovery, and live text/tool/reasoning/error canaries without restarting Claude Desktop.
