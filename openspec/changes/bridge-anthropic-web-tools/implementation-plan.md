# Anthropic Web Tools Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Claude Desktop WebSearch and WebFetch requests execute through the existing OpenAI Responses hosted `web_search` tool without weakening ordinary function-tool validation.

**Architecture:** Extend only the Anthropic request translator in `app/core/anthropic/messages.py`. Recognized, documented Anthropic web server-tool definitions become one Responses hosted `web_search` definition; ordinary tools continue through the existing function conversion. The route, token-count, batch, streaming, and portable paths reuse this shared converter.

**Tech Stack:** Python 3.13, FastAPI, Pydantic Responses request models, pytest, Ruff, ty, OpenSpec, Windows Electron portable runtime.

## Global Constraints

- The temporary `claude-code` branch was the isolated implementation line. After the complete Claude adapter was verified and committed as `163b7d0`, the user authorized a fast-forward consolidation into `codexneo-portable-windows`, documentation update, push, and redundant local-branch cleanup on 2026-07-17.
- Keep `main` and every other repository untouched. Only `codexneo-portable-windows` may receive this change, and the temporary branch may be retired only after ancestry and pushed-tip verification.
- Do not restart the active portable runtime until source verification and both portable mirrors are complete.
- Do not restart Claude Desktop; the user will exercise its built-in tools after the adapter is healthy.
- Supported WebSearch types are `web_search_20250305`, `web_search_20260209`, and `web_search_20260318`.
- Supported WebFetch types are `web_fetch_20250910`, `web_fetch_20260209`, `web_fetch_20260309`, and `web_fetch_20260318`.
- Both Anthropic tools map to the single OpenAI Responses `web_search` hosted tool; Responses actions `search`, `open_page`, and `find_in_page` provide the closest upstream behavior.
- `allowed_domains` and compatible `user_location` controls are preserved. `blocked_domains` is omitted only for the authenticated loopback `claudedesktop` profile; every other client remains fail-closed. Conflicting hosted configurations, unknown versions, and mismatched identities fail locally.
- `max_uses`, `allowed_callers`, and `response_inclusion` remain accepted compatibility metadata but are not forwarded.
- Existing function tools still require object `input_schema`.

---

### Task 1: Recognize and convert Anthropic web server tools

**Files:**
- Modify: `tests/unit/test_anthropic_messages.py`
- Modify: `app/core/anthropic/messages.py`

**Interfaces:**
- Consumes: `to_responses_request(payload, api_key=...) -> AnthropicMessagesRequest`
- Produces: `_tools_to_responses(value: JsonValue) -> list[JsonValue]` with hosted-tool recognition and deduplication.

- [x] **Step 1: Write failing converter tests**

Add parameterized coverage that submits every supported version with a minimal Messages body and asserts the forwarded tools are exactly `[{'type': 'web_search'}]`. Add a mixed request containing WebSearch, WebFetch, and a normal `read_file` function and assert one hosted tool plus the unchanged function schema.

```python
@pytest.mark.parametrize(
    ("tool_type", "tool_name"),
    [
        ("web_search_20250305", "web_search"),
        ("web_search_20260209", "web_search"),
        ("web_search_20260318", "web_search"),
        ("web_fetch_20250910", "web_fetch"),
        ("web_fetch_20260209", "web_fetch"),
        ("web_fetch_20260309", "web_fetch"),
        ("web_fetch_20260318", "web_fetch"),
    ],
)
def test_messages_request_maps_supported_web_server_tool(tool_type: str, tool_name: str) -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 1024,
            "tools": [{"type": tool_type, "name": tool_name}],
            "messages": [{"role": "user", "content": "Use the web."}],
        },
        api_key=None,
    )
    assert request.responses.model_dump_for_forwarding()["tools"] == [{"type": "web_search"}]
```

- [x] **Step 2: Run the tests and record RED**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_anthropic_messages.py -k "web_server_tool or web_tools" -q`

Expected: the new cases fail with `Tool definitions require object 'input_schema'.`

- [x] **Step 3: Add the minimal identity and mapping helpers**

Add frozen supported-type maps and a `_web_server_tool_to_responses()` helper. `_tools_to_responses()` must attempt server-tool conversion only when a tool declares a string `type`; otherwise it must retain the existing function path. The helper returns `None` for a client tool and a hosted configuration for a recognized server tool, and raises `ClientPayloadError` for web-prefixed unknown/mismatched identities.

```python
_SUPPORTED_WEB_SERVER_TOOLS: Final[dict[str, frozenset[str]]] = {
    "web_search": frozenset({"web_search_20250305", "web_search_20260209", "web_search_20260318"}),
    "web_fetch": frozenset(
        {"web_fetch_20250910", "web_fetch_20260209", "web_fetch_20260309", "web_fetch_20260318"}
    ),
}
```

Deduplicate identical hosted definitions while retaining the first hosted-tool position relative to ordinary function tools.

- [x] **Step 4: Run converter tests and record GREEN**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_anthropic_messages.py -k "web_server_tool or web_tools or translates_system_tools" -q`

Expected: all selected tests pass.

---

### Task 2: Preserve controls and translate forced tool choice

**Files:**
- Modify: `tests/unit/test_anthropic_messages.py`
- Modify: `app/core/anthropic/messages.py`

**Interfaces:**
- Consumes: recognized server-tool mappings from Task 1.
- Produces: validated hosted tool dictionaries and `_tool_choice_to_responses(value)` support for `web_search` and `web_fetch`.

- [x] **Step 1: Write failing control and choice tests**

Cover:

```python
{
    "type": "web_search_20260318",
    "name": "web_search",
    "allowed_domains": ["python.org", "docs.python.org"],
    "user_location": {
        "type": "approximate",
        "city": "Kolkata",
        "region": "West Bengal",
        "country": "IN",
        "timezone": "Asia/Kolkata",
    },
}
```

Assert this becomes:

```python
{
    "type": "web_search",
    "filters": {"allowed_domains": ["python.org", "docs.python.org"]},
    "user_location": {
        "type": "approximate",
        "city": "Kolkata",
        "region": "West Bengal",
        "country": "IN",
        "timezone": "Asia/Kolkata",
    },
}
```

Also assert forced `web_search` and `web_fetch` choices become `{'type': 'web_search'}`; unknown versions, name/type mismatch, non-string domains, malformed locations, `blocked_domains`, and conflicting duplicate controls raise `ClientPayloadError` with the relevant `tools.N` parameter.

- [x] **Step 2: Run the tests and record RED**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_anthropic_messages.py -k "web_server_tool_controls or web_tool_choice or rejects_web" -q`

Expected: controls are missing, choices still become function choices, or invalid cases are not rejected with the expected parameter.

- [x] **Step 3: Implement strict control normalization**

Add helpers that require `allowed_domains` to be a non-empty array of non-empty strings and validate `user_location` as an object with `type='approximate'`, optional non-empty `city`, `region`, `country`, and `timezone`, rejecting unknown location fields. Reject any present `blocked_domains`. Accept but do not forward `max_uses`, `allowed_callers`, and `response_inclusion`; reject unrecognized server-tool fields so future restrictions are not silently lost.

Update `_tool_choice_to_responses()`:

```python
if choice_type == "tool":
    name = _required_string(value, "name")
    if name in _SUPPORTED_WEB_SERVER_TOOLS:
        return {"type": "web_search"}, False if disable_parallel else None
    return {"type": "function", "name": name}, False if disable_parallel else None
```

- [x] **Step 4: Run the tests and record GREEN**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_anthropic_messages.py -k "web or translates_system_tools" -q`

Expected: all selected tests pass, including unchanged function-tool behavior.

---

### Task 3: Verify Messages, token-count, batch, and streaming paths

**Files:**
- Modify: `tests/integration/test_anthropic_messages_api.py`
- Modify only if a regression exposes shared-path drift: `app/modules/proxy/api.py`

**Interfaces:**
- Consumes: shared translator behavior from Tasks 1 and 2.
- Produces: raw HTTP proof that all Claude-facing validation entry points accept supported web server tools.

- [x] **Step 1: Add route regressions**

Add an authenticated `/v1/messages?beta=true` test with a monkeypatched `_collect_responses` that captures forwarded tools and returns final text. Add `/v1/messages/count_tokens?beta=true` with WebSearch and assert HTTP 200 plus `x-codex-lb-token-count=local-compatible`. Add `/v1/messages/batches?beta=true` with WebFetch and assert HTTP 200, then cancel or otherwise clean up the created local batch.

- [x] **Step 2: Add hosted lifecycle response regressions**

Add non-streaming and SSE fixtures containing `web_search_call` lifecycle items followed by a normal message. Assert the Anthropic response emits final text and terminal usage without leaking a raw Responses event or fabricating `server_tool_use`/citation blocks.

- [x] **Step 3: Run the route and lifecycle tests**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_anthropic_messages.py tests/integration/test_anthropic_messages_api.py -q`

Expected: all tests pass. If they already pass through the shared converter, leave `app/modules/proxy/api.py` unchanged.

---

### Task 4: Static verification and project tracking

**Files:**
- Modify: `openspec/changes/bridge-anthropic-web-tools/tasks.md`
- Modify: `CODEXNEO_IMPLEMENTATION_LIST.md`
- Modify: `HANDOVER_CODEXNEO_INTEGRATION.md`

**Interfaces:**
- Consumes: passing source implementation and test evidence.
- Produces: reproducible project state and exact remaining live-verification boundary.

- [x] **Step 1: Run focused quality gates**

Run:

```powershell
.venv\Scripts\python.exe -m ruff check app/core/anthropic/messages.py tests/unit/test_anthropic_messages.py tests/integration/test_anthropic_messages_api.py
.venv\Scripts\python.exe -m ty check app/core/anthropic/messages.py
openspec validate bridge-anthropic-web-tools --type change --strict --no-interactive
openspec validate --specs --strict --no-interactive
git diff --check
```

Expected: every command exits 0; line-ending warnings in already-dirty files may be reported separately but new whitespace errors are not accepted.

- [x] **Step 2: Update tracking before deployment**

Add the next CN entry describing WebSearch/WebFetch mapping, explicit limitations, test counts, and the still-separate Cowork VM error. Check completed OpenSpec source/test tasks, leaving live portable acceptance unchecked until it succeeds.

---

### Task 5: Mirror and live-verify the portable runtime

**Files:**
- Mirror: `app/core/anthropic/messages.py` to `dist/CodexIB-Electron-Portable/app/core/anthropic/messages.py`
- Mirror: `app/core/anthropic/messages.py` to `dist/CodexIB-Electron-Portable/.venv/Lib/site-packages/app/core/anthropic/messages.py`
- Modify after live evidence: `openspec/changes/bridge-anthropic-web-tools/tasks.md`
- Modify after live evidence: `CODEXNEO_IMPLEMENTATION_LIST.md`
- Modify after live evidence: `HANDOVER_CODEXNEO_INTEGRATION.md`

**Interfaces:**
- Consumes: verified source `messages.py`.
- Produces: identical source/app/site-packages runtime files and a healthy port `2455` service executing the new translator.

- [x] **Step 1: Mirror with PowerShell-native copy and verify hashes**

Copy the single production file to both portable roots using `Copy-Item -LiteralPath`. Compare all three `Get-FileHash -Algorithm SHA256` values and require equality.

- [x] **Step 2: Compile both portable copies**

Run the bundled interpreter with the portable virtual environment on `PYTHONPATH` and compile both mirrored files. Expected: exit 0 with no syntax output.

- [x] **Step 3: Verify zero active requests and restart CodexNeo once**

Read live health/readiness and request state first. Invoke the existing Electron-owned Restart Codex LB action only after both mirrors pass; do not stop Claude Desktop. Verify the listener returns on `127.0.0.1:2455`, `/health` and `/health/ready` return `ok`, and the backend PID changed.

- [x] **Step 4: Run live WebSearch and WebFetch acceptance**

Send authenticated loopback-only `claudedesktop` Messages requests using the official server-tool shapes. WebSearch must return HTTP 200 and an answer grounded in a current search. WebFetch must return HTTP 200 for a supplied HTTPS page and summarize page content. Also send one `blocked_domains` request and require a local HTTP 400 `invalid_request_error` without upstream execution.

## Follow-up: bounded Cowork Workspace WebFetch

Claude Desktop's host loop exposes `mcp__workspace__web_fetch` as a client function. Large pages are downloaded locally and replaced by Claude Code with a saved-file error marker before Codex LB receives the following request. Add route-level RED coverage proving that an authenticated Desktop turn with an explicit public URL replaces this alias with the existing hosted `web_search` tool, while private/local, non-Desktop, and no-URL cases remain ordinary functions. Deduplicate the alias with official web server tools, map a forced alias choice only when replacement occurred, then mirror and live-retry `https://claude.com/docs` after the app-owned CodexNeo restart. The later deferred-tool follow-up extends the same public-only replacement to `defer_loading: true` declarations and preserves their historical ToolSearch aliases through hosted bookkeeping.

- [x] **Step 5: Close tracking with exact evidence**

Record hashes, PIDs, health results, live HTTP statuses, response limitations, and the unchanged separate `VM guest is not connected` issue. Mark all OpenSpec tasks complete only when both live tool calls succeed.

---

### Task 5: Add Desktop-only maximum compatibility for blocked domains

**Files:**
- Modify: `openspec/changes/bridge-anthropic-web-tools/design.md`
- Modify: `openspec/changes/bridge-anthropic-web-tools/specs/anthropic-web-tools/spec.md`
- Modify: `openspec/changes/bridge-anthropic-web-tools/tasks.md`
- Modify: `tests/unit/test_anthropic_messages.py`
- Modify: `tests/integration/test_anthropic_messages_api.py`
- Modify: `app/core/anthropic/messages.py`
- Modify after live verification: `CODEXNEO_IMPLEMENTATION_LIST.md`
- Modify after live verification: `HANDOVER_CODEXNEO_INTEGRATION.md`

**Interfaces:**
- Consumes: `to_responses_request(..., claude_desktop: bool = False) -> AnthropicMessagesRequest` and the route's authenticated loopback Desktop classification.
- Produces: `_tools_to_responses(value: JsonValue, *, claude_desktop: bool) -> list[JsonValue]`, with Desktop-only deny-list omission and unchanged non-Desktop rejection.

- [x] **Step 1: Write the failing converter regression**

Add a test that calls `to_responses_request(..., claude_desktop=True)` with a supported web tool containing `blocked_domains: ["example.com"]` and asserts the forwarded tool is exactly `{"type": "web_search"}`. Keep the existing non-Desktop rejection case unchanged.

```python
def test_claude_desktop_omits_unsupported_blocked_domains() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "claude-sonnet-5",
            "max_tokens": 1024,
            "tools": [
                {
                    "type": "web_search_20260318",
                    "name": "web_search",
                    "blocked_domains": ["example.com"],
                }
            ],
            "messages": [{"role": "user", "content": "Search the web."}],
        },
        api_key=None,
        claude_desktop=True,
    )

    assert request.responses.model_dump_for_forwarding()["tools"] == [{"type": "web_search"}]
```

- [x] **Step 2: Run the converter test and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_anthropic_messages.py::test_claude_desktop_omits_unsupported_blocked_domains -q`

Expected: FAIL with `Anthropic web server-tool 'blocked_domains' cannot be enforced by the mapped upstream.`

- [x] **Step 3: Write the failing route regression**

Replace the Desktop route test that expects HTTP 400 with a monkeypatched `_collect_responses` capture. Submit `x-api-key: claudedesktop`, include a non-empty `blocked_domains`, assert HTTP 200, and assert the forwarded tools are `[{'type': 'web_search'}]`. Add a separate non-Desktop translator assertion that still raises `ClientPayloadError` for the same tool definition.

- [x] **Step 4: Implement the minimal profile-aware conversion**

Pass `claude_desktop` from `to_responses_request()` into `_tools_to_responses()` and then `_web_server_tool_to_responses()`. Reject a present `blocked_domains` only when `claude_desktop` is false.

```python
request_data["tools"] = _tools_to_responses(tools, claude_desktop=claude_desktop)

def _tools_to_responses(value: JsonValue, *, claude_desktop: bool) -> list[JsonValue]:
    ...
    converted_web_tool = _web_server_tool_to_responses(
        tool,
        index=index,
        claude_desktop=claude_desktop,
    )

if "blocked_domains" in tool and not claude_desktop:
    raise ClientPayloadError(...)
```

- [x] **Step 5: Verify GREEN and regressions**

Run the exact new unit and route tests, then the full Anthropic unit/integration suite. Run Ruff, scoped ty, `openspec validate bridge-anthropic-web-tools --type change --strict --no-interactive`, and all stable specs.

- [x] **Step 6: Mirror and activate the portable runtime**

Copy `app/core/anthropic/messages.py` to `dist/CodexIB-Electron-Portable/app/core/anthropic/messages.py` and `dist/CodexIB-Electron-Portable/.venv/Lib/site-packages/app/core/anthropic/messages.py`. Require identical SHA-256 values and successful bundled `py_compile`, drain to zero in-flight work, then invoke only the existing **Restart CodexNeo** action.

- [x] **Step 7: Run bounded live acceptance and close tracking**

Send one small loopback `claudedesktop` `/v1/messages?beta=true` request with a supported WebSearch definition and non-empty `blocked_domains`. Require HTTP 200 and a grounded response or hosted-tool execution evidence. Confirm the equivalent non-Desktop translator regression still returns the local invalid-request error. Update CN-081/CN-083 tracking and handover with the explicit loss of deny-list enforcement; do not claim that Cowork's separate host egress allowlist is bypassed.

## Follow-up: historical ToolSearch reference to hosted Workspace WebFetch

Claude Desktop can replay a prior client ToolSearch result whose `tool_reference` names `mcp__workspace__web_fetch` while advertising that tool in the current request. The public-URL bridge replaces the current definition with hosted `web_search`, so indexing only converted function names falsely rejects the historical reference as unavailable. Add route-level RED coverage for the exact transcript. Resolve the name through the existing hosted-alias registry, but do not put `web_search` or a synthetic Workspace function into `tool_search_output.tools`. Suppress a historical ToolSearch call/output pair when it selected only hosted aliases; when it selected a hosted alias and ordinary functions, retain the pair with only the ordinary functions. Keep unknown-reference rejection and non-Desktop replay unchanged, then mirror, app-restart, and live-retest the exact request. The deferred-tool follow-up applies the same invariant to eligible public `defer_loading: true` declarations while preserving private/local and mixed-target client execution.
