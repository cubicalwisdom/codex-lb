# Anthropic Structured Tool Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover Claude Desktop conversations containing `tool_reference` results while preserving ordinary tool behavior and using native Responses replay for complete ToolSearch pairs.

**Architecture:** Precompute eligible ToolSearch call/result pairs from the full Anthropic history and converted function catalog. Thread that immutable context through the existing assistant/user converters; native pairs become `tool_search_call`/`tool_search_output`, while other valid references use a canonical JSON `function_call_output` fallback.

**Tech Stack:** Python 3.13, Pydantic Responses request models, FastAPI, pytest, Ruff, ty, OpenSpec, Windows Electron portable runtime.

## Global Constraints

- Preserve all current dirty parity work and remain on branch `claude-code`.
- Do not stage, commit, push, merge, or modify another repository.
- Change only the Anthropic translator, its tests/OpenSpec records, both portable mirrors, and required tracking files.
- Keep top-level tool conversion and existing string/text-result behavior unchanged.
- Restart only Codex LB after source tests and portable hash/compile verification; do not restart Claude Desktop without fresh explicit permission.

---

### Task 1: Prove the compatibility gap

**Files:**
- Modify: `tests/unit/test_anthropic_messages.py`
- Modify: `tests/integration/test_anthropic_messages_api.py`

**Interfaces:**
- Consumes: `to_responses_request(payload, api_key=..., claude_desktop=True)` and `/v1/messages?beta=true`.
- Produces: failing regressions specifying native pair and fallback output shapes.

- [ ] **Step 1: Add the exact converter regression**

Construct a request containing converted `ToolSearch` and deferred workspace function definitions, an assistant `ToolSearch` call, a matching reference-only result, and a later user command. Assert the forwarded input contains `tool_search_call`, `tool_search_output`, then the later user message.

- [ ] **Step 2: Add validation and fallback regressions**

Assert multiple references preserve first-reference order and deduplicate names; an unresolved native reference raises `ClientPayloadError`; an ordinary tool returning a reference produces compact canonical JSON; and the existing text-only test remains unchanged.

- [ ] **Step 3: Add the HTTP-route regression**

Monkeypatch `_collect_responses`, submit the poisoned history with the `claudedesktop` key, and assert HTTP 200 plus captured native input items.

- [ ] **Step 4: Run RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_anthropic_messages.py -k "tool_reference or tool_search_history" -q
.venv\Scripts\python.exe -m pytest tests/integration/test_anthropic_messages_api.py -k "tool_reference_history" -q
```

Expected: tests fail with `Only text tool_result blocks are supported.` or mismatched expected native items.

### Task 2: Implement native replay and safe fallback

**Files:**
- Modify: `app/core/anthropic/messages.py`

**Interfaces:**
- Produces: `_tool_search_history(...) -> Mapping[str, list[JsonValue]]` and context-aware `_assistant_input()` / `_user_content()` behavior.

- [ ] **Step 1: Precompute eligible pairs**

Build a converted function map by name, scan assistant calls and matching reference-only results, validate every name, and retain ordered deduplicated definitions per call ID.

- [ ] **Step 2: Translate both sides consistently**

Emit `tool_search_call` only for eligible call IDs and `tool_search_output` only for their results. Preserve call IDs, client execution, completion status, structured arguments, and selected definitions.

- [ ] **Step 3: Add canonical fallback**

Keep string/text-array output unchanged. When text/reference content is not an eligible native pair, validate references and serialize the whole ordered array with `ensure_ascii=False`, `sort_keys=True`, and compact separators. Continue rejecting unrelated structured types.

- [ ] **Step 4: Run GREEN**

Run the two focused commands from Task 1 and require all selected tests to pass.

### Task 3: Verify unchanged protocol surfaces

**Files:**
- Modify checkboxes only after evidence: `openspec/changes/support-anthropic-structured-tool-results/tasks.md`

**Interfaces:**
- Consumes: implemented translator and regressions.
- Produces: static and behavioral verification evidence.

- [ ] **Step 1: Run the Anthropic suites**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_anthropic_messages.py tests/integration/test_anthropic_messages_api.py -q
```

- [ ] **Step 2: Run quality and spec gates**

```powershell
.venv\Scripts\python.exe -m ruff check app/core/anthropic/messages.py tests/unit/test_anthropic_messages.py tests/integration/test_anthropic_messages_api.py
.venv\Scripts\python.exe -m ty check app/core/anthropic/messages.py
openspec validate support-anthropic-structured-tool-results --type change --strict --no-interactive
openspec validate --specs --strict --no-interactive
git diff --check
```

Expected: every command exits 0, with any pre-existing unrelated dirty-tree warning reported separately.

### Task 4: Deliver to the active portable runtime

**Files:**
- Mirror: `app/core/anthropic/messages.py`
- Mirror: `dist/CodexIB-Electron-Portable/app/core/anthropic/messages.py`
- Mirror: `dist/CodexIB-Electron-Portable/.venv/Lib/site-packages/app/core/anthropic/messages.py`
- Modify: `CODEXNEO_IMPLEMENTATION_LIST.md`
- Modify: `HANDOVER_CODEXNEO_INTEGRATION.md`
- Modify: `openspec/changes/support-anthropic-structured-tool-results/tasks.md`

**Interfaces:**
- Produces: identical active runtime files, healthy port 2455 service, live Claude acceptance, and durable handover evidence.

- [ ] **Step 1: Mirror and verify**

Use PowerShell `Copy-Item -LiteralPath`, require all three SHA-256 hashes to match, and compile both portable copies with the bundled interpreter.

- [ ] **Step 2: Restart Codex LB once**

Check active request state, wait for drain, invoke the existing app-owned Codex LB restart path, and verify `/health` and `/health/ready` on `127.0.0.1:2455` with a changed backend PID.

- [ ] **Step 3: Run live acceptance**

Retry the existing poisoned conversation first. Then verify fresh WebFetch reaches an HTTPS page, WebSearch returns results, ToolSearch loads and calls a referenced tool, and one ordinary tool call still succeeds.

- [ ] **Step 4: Close tracking**

Record test counts, hashes, PIDs, downtime window, live outcomes, GitHub comparison, and remaining document/nested-multimodal exclusions in the two existing tracking files and check tasks only when evidence exists.
