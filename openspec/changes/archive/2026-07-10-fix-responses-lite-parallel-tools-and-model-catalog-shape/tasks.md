# Tasks

## 1. Reproduce and specify

- [x] 1.1 Inspect the failing Codex task and live request logs; record the exact upstream error and affected transport.
- [x] 1.2 Trace Responses Lite body detection, HTTP header synthesis, WebSocket metadata synthesis, and catalog construction to their final wire boundaries.
- [x] 1.3 Add normative deltas for Lite parallel-tool normalization and the dual-shape catalog.

## 2. Test-first regressions

- [x] 2.1 Add direct HTTP and core WebSocket regressions that send `parallel_tool_calls=true` with `additional_tools` and expect the upstream wire value `false`.
- [x] 2.2 Add HTTP-bridge and native WebSocket regressions for the same full Lite request, plus trusted marker-only continuation coverage.
- [x] 2.3 Change compact request regressions to require an explicit `parallel_tool_calls=false` wire value.
- [x] 2.4 Strengthen model catalog regressions for `models`, `object`, deterministic `data`, supported-in-API-false compatibility, and API-key filtering.
- [x] 2.5 Run the focused tests before implementation and record the expected failures.

## 3. Minimal implementation

- [x] 3.1 Add one wire-mapping normalizer for Lite `parallel_tool_calls=false` and apply it at core and bridge/WebSocket boundaries.
- [x] 3.2 Make compact serialization emit `parallel_tool_calls=false` while retaining tool-field stripping.
- [x] 3.3 Add the dual-shape `CodexModelsResponse`, shared model-list item converter, deterministic native timestamps, and filtered `data` population.
- [x] 3.4 Run the focused tests to green and run adjacent proxy/catalog regressions.

## 4. Verification and portable runtime

- [x] 4.1 Run scoped Ruff and ty checks plus strict change and stable OpenSpec validation.
- [x] 4.2 Run the affected Responses, HTTP-bridge, WebSocket, catalog, compatibility, and e2e regression suites with isolated Codex Home fixtures.
- [x] 4.3 Obtain an independent code review and address any concrete finding.
- [x] 4.4 Mirror every changed production Python file into both portable roots and verify SHA-256 equality plus portable compile/import checks.
- [x] 4.5 Verify the running Electron-owned backend remains healthy and account-clean, confirm it still exposes the pre-fix catalog/error history, and document that a full Codex-LB restart is required to load the mirrored fix without breaking tray lifecycle ownership.

## 5. Documentation and commit

- [x] 5.1 Sync the verified requirements/context into the stable OpenSpec capabilities.
- [x] 5.2 Update `CODEXNEO_IMPLEMENTATION_LIST.md` and `HANDOVER_CODEXNEO_INTEGRATION.md` with root cause, behavior, verification, and remaining limitations.
- [x] 5.3 Archive this OpenSpec change after verification.
- [x] 5.4 Review and stage the intended accumulated work, then create one Conventional Commit without pushing.
