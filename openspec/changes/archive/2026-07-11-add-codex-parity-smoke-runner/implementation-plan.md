# Codex Parity Smoke Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fast, semantic pytest lane for the 16 approved Codex/proxy parity functions (18 collected cases) without weakening any existing test or completion gate.

**Architecture:** Pytest owns membership through a registered `codex_parity_smoke` marker attached directly to existing test functions. A small structural unit test locks the marker registration and Make recipe, while `test-codex-parity-smoke` invokes pytest with the repository safety options and strict marker validation. Full affected files and existing CI/release targets remain authoritative.

**Tech Stack:** Python 3.13, pytest, `tomllib`, GNU Make syntax, OpenSpec, Ruff.

## Global Constraints

- Work only in `H:\Opencode IDE\codex-ib\codex-lb-codex-parity-worktree` on `codexneo-portable-windows`; do not modify the shared `main` checkout.
- The initial lane is limited to proxy/Codex API parity. Git-diff inference and repository-wide selection remain a later change.
- Mark exactly the approved 16 existing test functions, currently producing 18 cases; do not change their bodies, parameters, fixtures, assertions, or ordinary suite membership.
- Do not remove, skip, narrow, or rewire `test-unit`, `test-integration-core`, `test-integration-bridge`, `test-e2e`, `ci-fast`, `ci`, GitHub required checks, or release gates.
- The focused target must use `$(PYTEST_ARGS)`, `--strict-markers`, and `-m codex_parity_smoke`; it must not depend on frontend, packaging, migration, Docker, Helm, portable, or live-upstream work.
- `make.exe` is unavailable on this Windows host. Do not install it. Prove the recipe structurally and execute its exact pytest command directly; report the unavailable executable as an environment limitation.
- No production source, API, database, packaged asset, portable runtime, backend, Electron, or Codex Desktop change/restart is authorized or required.
- Use OpenSpec as the documentation source of truth. Do not add feature documentation under `docs/` or edit `CHANGELOG.md`.
- Commit locally with Conventional Commits. Do not push.

---

### Task 1: Semantic marker and focused Make entry point

**Files:**

- Create: `tests/unit/test_codex_parity_smoke_workflow.py`
- Modify: `pyproject.toml:91-101`
- Modify: `Makefile:10-25`
- Modify: `Makefile:45-75`
- Modify: `tests/unit/test_proxy_utils.py`
- Modify: `tests/unit/test_openai_requests.py`
- Modify: `tests/integration/test_proxy_compact.py`
- Modify: `tests/integration/test_proxy_responses.py`
- Modify: `tests/integration/test_http_responses_bridge.py`
- Modify: `tests/integration/test_proxy_websocket_responses.py`
- Modify: `tests/integration/test_v1_models.py`
- Modify: `openspec/changes/add-codex-parity-smoke-runner/tasks.md`

**Interfaces:**

- Consumes: existing `PYTEST_ARGS`, pytest marker configuration, and the 16 approved test functions listed in `design.md`.
- Produces: registered marker `codex_parity_smoke`, Make target `test-codex-parity-smoke`, and a structural workflow regression.

- [ ] **Step 1: Establish the clean baseline for the selected tests**

Run the exact current inventory before changing metadata:

```powershell
$nodes = @(
  'tests/unit/test_proxy_utils.py::test_stream_responses_derives_http_lite_signal_from_body',
  'tests/unit/test_proxy_utils.py::test_stream_responses_websocket_derives_lite_marker_from_body',
  'tests/unit/test_proxy_utils.py::test_websocket_lite_acceptance_allows_only_linked_same_model_incremental_marker',
  'tests/unit/test_proxy_utils.py::test_websocket_lite_incremental_marker_requires_accepted_response_linkage',
  'tests/unit/test_proxy_utils.py::test_prepare_websocket_response_create_request_captures_client_full_resend_anchor_replay',
  'tests/unit/test_proxy_utils.py::test_compact_responses_derives_http_lite_signal_from_body',
  'tests/unit/test_openai_requests.py::test_v1_compact_strips_tool_fields',
  'tests/integration/test_proxy_compact.py::test_proxy_compact_strips_tool_fields_before_upstream',
  'tests/integration/test_proxy_responses.py::test_proxy_responses_compaction_trigger_streams_single_compaction_item',
  'tests/integration/test_http_responses_bridge.py::test_backend_responses_http_bridge_reuses_upstream_websocket_and_preserves_previous_response_id',
  'tests/integration/test_proxy_websocket_responses.py::test_backend_responses_websocket_proxies_upstream_and_persists_log',
  'tests/integration/test_v1_models.py::test_v1_models_with_client_version_returns_codex_catalog',
  'tests/integration/test_v1_models.py::test_v1_models_with_empty_client_version_keeps_openai_shape',
  'tests/integration/test_v1_models.py::test_v1_models_codex_negotiation_preserves_api_key_filtering',
  'tests/integration/test_v1_models.py::test_backend_codex_models_rewrites_visibility_when_opted_in',
  'tests/integration/test_v1_models.py::test_model_sets_are_consistent_across_api_endpoints'
)
uv sync --dev --frozen
uv run pytest -q -ra --timeout=180 --timeout-method=thread $nodes
```

Expected: `18 passed` and no real Codex account-store writes.

- [ ] **Step 2: Record marker-selection RED evidence**

```powershell
uv run pytest -q --strict-markers -m codex_parity_smoke --collect-only
```

Expected: exit code `5` with no selected tests because the marker is not registered or applied yet.

- [ ] **Step 3: Add the failing workflow-contract test**

Create `tests/unit/test_codex_parity_smoke_workflow.py`:

```python
from __future__ import annotations

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _make_target_body(makefile: str, target: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(target)}:[^\n]*\n(?P<body>(?:\t[^\n]*(?:\n|$))+)",
        makefile,
    )
    assert match is not None, f"missing Make target: {target}"
    return match.group("body")


def test_codex_parity_smoke_workflow_contract() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    markers = pyproject["tool"]["pytest"]["ini_options"]["markers"]
    assert any(marker.startswith("codex_parity_smoke:") for marker in markers)

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "make test-codex-parity-smoke" in makefile
    body = _make_target_body(makefile, "test-codex-parity-smoke")
    assert "uv sync --dev --frozen" in body
    assert "$(PYTEST_ARGS)" in body
    assert "--strict-markers" in body
    assert "-m codex_parity_smoke" in body
    assert not any(
        broad_target in body
        for broad_target in (
            "frontend-build",
            "test-unit",
            "test-integration-core",
            "test-integration-bridge",
            "test-e2e",
            "package",
        )
    )
```

- [ ] **Step 4: Run the workflow contract and confirm RED**

```powershell
uv run pytest tests/unit/test_codex_parity_smoke_workflow.py -q
```

Expected: FAIL because `codex_parity_smoke` and `test-codex-parity-smoke` do not exist.

- [ ] **Step 5: Register the marker**

Add this exact entry to `[tool.pytest.ini_options].markers` in `pyproject.toml`:

```toml
"codex_parity_smoke: curated fast semantic checks for native Codex/proxy compatibility",
```

- [ ] **Step 6: Add the Make help and target**

Add this help line without changing the existing targets:

```make
	  '  make test-codex-parity-smoke focused native Codex/proxy parity tests' \
```

Add this target before the existing broad pytest slices:

```make
.PHONY: test-codex-parity-smoke
test-codex-parity-smoke:
	uv sync --dev --frozen
	PYTHONFAULTHANDLER=1 uv run pytest $(PYTEST_ARGS) --strict-markers -m codex_parity_smoke
```

- [ ] **Step 7: Mark the approved functions without altering test behavior**

Add `@pytest.mark.codex_parity_smoke` immediately above the existing decorators or function definition for exactly these functions:

```text
tests/unit/test_proxy_utils.py:
  test_stream_responses_derives_http_lite_signal_from_body
  test_stream_responses_websocket_derives_lite_marker_from_body
  test_websocket_lite_acceptance_allows_only_linked_same_model_incremental_marker
  test_websocket_lite_incremental_marker_requires_accepted_response_linkage
  test_prepare_websocket_response_create_request_captures_client_full_resend_anchor_replay
  test_compact_responses_derives_http_lite_signal_from_body
tests/unit/test_openai_requests.py:
  test_v1_compact_strips_tool_fields
tests/integration/test_proxy_compact.py:
  test_proxy_compact_strips_tool_fields_before_upstream
tests/integration/test_proxy_responses.py:
  test_proxy_responses_compaction_trigger_streams_single_compaction_item
tests/integration/test_http_responses_bridge.py:
  test_backend_responses_http_bridge_reuses_upstream_websocket_and_preserves_previous_response_id
tests/integration/test_proxy_websocket_responses.py:
  test_backend_responses_websocket_proxies_upstream_and_persists_log
tests/integration/test_v1_models.py:
  test_v1_models_with_client_version_returns_codex_catalog
  test_v1_models_with_empty_client_version_keeps_openai_shape
  test_v1_models_codex_negotiation_preserves_api_key_filtering
  test_backend_codex_models_rewrites_visibility_when_opted_in
  test_model_sets_are_consistent_across_api_endpoints
```

For an async test, place `@pytest.mark.codex_parity_smoke` immediately above its existing `@pytest.mark.asyncio`; do not move or rewrite the function body.

- [ ] **Step 8: Run GREEN contract, collection, and focused behavior checks**

```powershell
uv run pytest tests/unit/test_codex_parity_smoke_workflow.py -q
uv run pytest -q --strict-markers -m codex_parity_smoke --collect-only
uv run pytest -q -ra -o faulthandler_timeout=300 -o faulthandler_exit_on_timeout=true --timeout=180 --timeout-method=thread --durations=20 --strict-markers -m codex_parity_smoke
```

Expected: workflow contract passes; collection reports exactly 18 cases from the 16 approved functions; focused execution reports `18 passed`.

- [ ] **Step 9: Record Task 1 evidence and commit**

Check Tasks 1.1-2.3 in `tasks.md`, stage only Task 1 files, run `git diff --cached --check`, and commit:

```powershell
git commit -m "test(proxy): add Codex parity smoke runner"
```

### Task 2: Full verification, stable documentation, and archive

**Files:**

- Modify: `openspec/changes/add-codex-parity-smoke-runner/tasks.md`
- Modify: `openspec/specs/compatibility-tooling/spec.md`
- Create: `openspec/specs/compatibility-tooling/context.md`
- Modify: `CODEXNEO_IMPLEMENTATION_LIST.md`
- Modify: `HANDOVER_CODEXNEO_INTEGRATION.md`
- Move by archive: `openspec/changes/add-codex-parity-smoke-runner/` to `openspec/changes/archive/2026-07-11-add-codex-parity-smoke-runner/`

**Interfaces:**

- Consumes: Task 1 marker, Make recipe, collection output, and test evidence.
- Produces: stable compatibility-tooling contract/context, CN-066 tracking, archived completed OpenSpec, and final local commit.

- [ ] **Step 1: Re-run the exact Make recipe directly on Windows**

Because `make.exe` is unavailable, run the recipe's pytest command directly:

```powershell
uv sync --dev --frozen
$env:PYTHONFAULTHANDLER='1'
uv run pytest -q -ra -o faulthandler_timeout=300 -o faulthandler_exit_on_timeout=true --timeout=180 --timeout-method=thread --durations=20 --strict-markers -m codex_parity_smoke
```

Expected: `18 passed`. Do not claim that GNU Make itself ran locally.

- [ ] **Step 2: Prove direct-node equivalence**

Run the exact explicit inventory and confirm `18 passed`:

```powershell
$nodes = @(
  'tests/unit/test_proxy_utils.py::test_stream_responses_derives_http_lite_signal_from_body',
  'tests/unit/test_proxy_utils.py::test_stream_responses_websocket_derives_lite_marker_from_body',
  'tests/unit/test_proxy_utils.py::test_websocket_lite_acceptance_allows_only_linked_same_model_incremental_marker',
  'tests/unit/test_proxy_utils.py::test_websocket_lite_incremental_marker_requires_accepted_response_linkage',
  'tests/unit/test_proxy_utils.py::test_prepare_websocket_response_create_request_captures_client_full_resend_anchor_replay',
  'tests/unit/test_proxy_utils.py::test_compact_responses_derives_http_lite_signal_from_body',
  'tests/unit/test_openai_requests.py::test_v1_compact_strips_tool_fields',
  'tests/integration/test_proxy_compact.py::test_proxy_compact_strips_tool_fields_before_upstream',
  'tests/integration/test_proxy_responses.py::test_proxy_responses_compaction_trigger_streams_single_compaction_item',
  'tests/integration/test_http_responses_bridge.py::test_backend_responses_http_bridge_reuses_upstream_websocket_and_preserves_previous_response_id',
  'tests/integration/test_proxy_websocket_responses.py::test_backend_responses_websocket_proxies_upstream_and_persists_log',
  'tests/integration/test_v1_models.py::test_v1_models_with_client_version_returns_codex_catalog',
  'tests/integration/test_v1_models.py::test_v1_models_with_empty_client_version_keeps_openai_shape',
  'tests/integration/test_v1_models.py::test_v1_models_codex_negotiation_preserves_api_key_filtering',
  'tests/integration/test_v1_models.py::test_backend_codex_models_rewrites_visibility_when_opted_in',
  'tests/integration/test_v1_models.py::test_model_sets_are_consistent_across_api_endpoints'
)
uv run pytest -q -ra --timeout=180 --timeout-method=thread $nodes
```

Compare its collected node ids with the marker collection; the sets must match exactly.

- [ ] **Step 3: Run the full affected files in three independent groups**

Run these commands concurrently when tool orchestration permits, then wait for all three results:

```powershell
uv run pytest -q -ra --timeout=180 --timeout-method=thread tests/unit/test_proxy_utils.py tests/unit/test_openai_requests.py
```

```powershell
uv run pytest -q -ra --timeout=180 --timeout-method=thread tests/integration/test_proxy_compact.py tests/integration/test_proxy_responses.py tests/integration/test_v1_models.py
```

```powershell
uv run pytest -q -ra --timeout=180 --timeout-method=thread tests/integration/test_http_responses_bridge.py tests/integration/test_proxy_websocket_responses.py
```

Expected: all groups pass. If parallel execution reveals environmental interference, rerun only the affected group sequentially before diagnosing code.

- [ ] **Step 4: Run static and specification checks**

```powershell
uv run ruff check tests/unit/test_codex_parity_smoke_workflow.py tests/unit/test_proxy_utils.py tests/unit/test_openai_requests.py tests/integration/test_proxy_compact.py tests/integration/test_proxy_responses.py tests/integration/test_http_responses_bridge.py tests/integration/test_proxy_websocket_responses.py tests/integration/test_v1_models.py
uv run ruff format --check tests/unit/test_codex_parity_smoke_workflow.py tests/unit/test_proxy_utils.py tests/unit/test_openai_requests.py tests/integration/test_proxy_compact.py tests/integration/test_proxy_responses.py tests/integration/test_http_responses_bridge.py tests/integration/test_proxy_websocket_responses.py tests/integration/test_v1_models.py
openspec validate add-codex-parity-smoke-runner --strict
openspec validate --specs
git diff --check
```

Expected: Ruff lint, OpenSpec validation, and the diff check exit zero. If the full-file Ruff format command proposes changes in a legacy test file, compare that file's complete proposed formatter transformation with base commit `e88fbf3`. Accept only transformations already present at that base, require the newly created workflow-contract file to format-check at zero, and record each proven baseline exception. Do not reformat unrelated legacy lines merely to make this metadata-only change green.

- [ ] **Step 5: Sync stable OpenSpec requirements and context**

Append the completed normative requirement from the change delta to `openspec/specs/compatibility-tooling/spec.md` without freezing the current case count. Create `openspec/specs/compatibility-tooling/context.md` containing:

```markdown
# Codex parity smoke runner

## Purpose and scope

`codex_parity_smoke` is the fast first feedback loop for native Codex/proxy wire compatibility. It covers curated Responses Lite, compact, HTTP bridge, native WebSocket, and negotiated model-catalog semantics. It does not replace affected suites or release gates.

## Decisions and constraints

- Membership lives on tests as a semantic pytest marker rather than in a duplicated node-id manifest.
- `make test-codex-parity-smoke` uses the repository pytest safety options and strict marker validation.
- On Windows without GNU Make, run `uv run pytest -q -ra -o faulthandler_timeout=300 -o faulthandler_exit_on_timeout=true --timeout=180 --timeout-method=thread --durations=20 --strict-markers -m codex_parity_smoke` directly.
- Existing `ci-fast`, `ci`, required checks, and release verification remain authoritative.
- Git-diff selection and non-Codex families are intentionally deferred to a later repository-wide change-aware runner.

## Failure modes

Pytest exits nonzero when a selected regression fails or when no marked tests are collected. An empty selection is therefore a failed compatibility check, not a success.

## Example

After changing Responses Lite serialization, run the smoke command for early feedback. Before committing the behavior change, still run the complete affected proxy/Responses/bridge files and required static/OpenSpec gates.
```

- [ ] **Step 6: Update root tracking**

Add CN-066 to `CODEXNEO_IMPLEMENTATION_LIST.md` and append matching handover notes. Record the semantic scope, 16 functions / 18 cases, direct Windows command, unchanged full gates, actual timings/results, independent review result, and the fact that no runtime restart or portable mirror was needed.

- [ ] **Step 7: Complete and archive the OpenSpec**

Check Tasks 3.1-3.5 only after their evidence exists, validate again, then archive without automatic spec sync because Step 5 synchronized it manually:

```powershell
openspec archive add-codex-parity-smoke-runner --skip-specs --yes
openspec validate --specs
git diff --check
```

Expected: the change moves to `openspec/changes/archive/2026-07-11-add-codex-parity-smoke-runner`, all stable specs validate, and no active folder remains.

- [ ] **Step 8: Commit closeout without pushing**

Stage only the stable spec/context, archived change, implementation list, and handover. Inspect the complete staged diff and run `git diff --cached --check`, then commit:

```powershell
git commit -m "docs(codexneo): close out parity smoke runner"
```

Expected: worktree clean, local branch contains the design, implementation, and closeout commits, and no remote state changes.
