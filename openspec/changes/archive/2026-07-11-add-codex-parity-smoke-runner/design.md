# Design

## Context

The existing `ci-fast` target is intentionally broad: it runs lint, type checking, frontend coverage, the complete unit slice, and packaging. The recent Codex parity verification groups additionally covered hundreds of proxy, Responses, compact, catalog, HTTP-bridge, and WebSocket tests. Those gates found real regressions and must remain intact, but they are too slow to be the first feedback loop for each narrow wire-contract edit.

The approved first phase is deliberately limited to proxy/Codex API compatibility. It does not attempt to infer arbitrary repository dependencies from a Git diff.

## Goals

- Provide one stable command that exercises the highest-signal Codex parity contracts in roughly the time required by those tests themselves.
- Select tests by semantic marker rather than by duplicated node-id manifest.
- Fail visibly if the marker selection becomes empty or a marked regression fails.
- Preserve all current full-suite, CI, and release gates.
- Leave a clean extension point for a later general change-aware runner.

## Non-goals

- Replacing `ci-fast`, `ci`, any GitHub required check, or any release verification.
- Automatically inspecting Git changes or selecting non-Codex test families.
- Removing, skipping, rewriting, or weakening existing tests.
- Running frontend, packaging, migration, Docker, Helm, or portable-runtime work from the focused target.
- Changing application behavior or restarting Codex Desktop, Electron, or the backend.

## Considered approaches

### 1. Semantic pytest marker and Make target (selected)

Register `codex_parity_smoke`, decorate the selected tests, and invoke pytest with `-m codex_parity_smoke`. The marker stays attached when functions move or node ids change, pytest rejects unknown markers under strict-marker use, and the same semantic group can later be selected by a broader change-aware dispatcher.

### 2. Text manifest of exact node ids

A manifest gives deterministic selection but duplicates function names and silently becomes stale on renames. It also creates a second inventory that must be synchronized with test files. This was rejected in favor of marker ownership at each test.

### 3. Immediate path-to-test change inference

A script could inspect Git changes and map production paths directly to test commands. That is the intended later direction, but doing it now would require repository-wide dependency policy before the proxy/Codex slice is proven. It is outside this change.

## Initial semantic selection

The marker covers 16 functions and 18 collected cases across seven existing files:

- `tests/unit/test_proxy_utils.py`
  - `test_stream_responses_derives_http_lite_signal_from_body`
  - `test_stream_responses_websocket_derives_lite_marker_from_body`
  - `test_websocket_lite_acceptance_allows_only_linked_same_model_incremental_marker`
  - `test_websocket_lite_incremental_marker_requires_accepted_response_linkage` (two parameter cases)
  - `test_prepare_websocket_response_create_request_captures_client_full_resend_anchor_replay`
  - `test_compact_responses_derives_http_lite_signal_from_body`
- `tests/unit/test_openai_requests.py`
  - `test_v1_compact_strips_tool_fields`
- `tests/integration/test_proxy_compact.py`
  - `test_proxy_compact_strips_tool_fields_before_upstream`
- `tests/integration/test_proxy_responses.py`
  - `test_proxy_responses_compaction_trigger_streams_single_compaction_item` (two parameter cases)
- `tests/integration/test_http_responses_bridge.py`
  - `test_backend_responses_http_bridge_reuses_upstream_websocket_and_preserves_previous_response_id`
- `tests/integration/test_proxy_websocket_responses.py`
  - `test_backend_responses_websocket_proxies_upstream_and_persists_log`
- `tests/integration/test_v1_models.py`
  - `test_v1_models_with_client_version_returns_codex_catalog`
  - `test_v1_models_with_empty_client_version_keeps_openai_shape`
  - `test_v1_models_codex_negotiation_preserves_api_key_filtering`
  - `test_backend_codex_models_rewrites_visibility_when_opted_in`
  - `test_model_sets_are_consistent_across_api_endpoints`

This selection covers Lite trust and wire normalization, HTTP/WebSocket transport signaling, compact stripping and compaction identity, bridge continuation, WebSocket persistence, and native/negotiated catalog shape and filtering. New tests join the fast lane by adding the marker; no central node-id list is edited.

## Command contract

`make test-codex-parity-smoke` will synchronize frozen development dependencies and run pytest with the shared `PYTEST_ARGS`, strict marker validation, and `-m codex_parity_smoke`. It will not depend on `frontend-build` or any broad test target. The Make help output will identify it as the focused Codex API parity loop.

Pytest returns nonzero when a selected test fails and also when no tests are collected, so an accidentally empty selection cannot report success. Marker registration prevents unknown-marker warnings and keeps collection compatible with strict marker checks.

## Full-gate boundary

The focused runner is an early feedback command, not completion evidence by itself. A proxy/Codex behavior change still runs its full affected suites and the repository's required static/OpenSpec checks before final commit or release. Existing Make targets and CI workflows are not rewired to the smoke target in this phase.

## Verification strategy

1. Before adding the marker, run collection for `codex_parity_smoke` and confirm it fails because the selection is empty.
2. Register and apply the marker, then collect the selection and confirm exactly 16 functions / 18 cases from the intended files.
3. Run `make test-codex-parity-smoke` and confirm all 18 cases pass.
4. Run each selected node directly to prove the marker target and explicit inventory execute the same cases.
5. Run the relevant full affected test files once, plus Ruff, strict OpenSpec validation, and `git diff --check`, before closeout.
6. Independently review the exact implementation diff for accidental skipped tests, changed test bodies, or altered full-gate dependencies.

## Future extension

A later change may add a repository-wide dispatcher that maps changed path families to semantic markers or existing Make targets. This marker becomes one selectable family, but no Git-diff interpretation or fallback policy is defined here.
