# Add a focused Codex parity smoke runner

## Why

Recent Codex API compatibility work required repeatedly running several broad test files. Those gates remain valuable before a behavior commit or release, but they make the normal red/green loop take minutes even when the changed contract is confined to Responses Lite, compaction, HTTP/WebSocket bridging, or the negotiated Codex model catalog.

The repository needs a small, explicit fast lane that gives developers early feedback without weakening or replacing any existing test, CI, or release requirement.

## What Changes

- Register a semantic `codex_parity_smoke` pytest marker.
- Apply it to the agreed 16 high-signal test functions, which currently collect as 18 cases.
- Add a documented `make test-codex-parity-smoke` target that runs only that marked selection with the repository's standard pytest safety options.
- Keep every existing test and the current `ci-fast`, `ci`, affected-suite, and release gates unchanged.
- Treat the focused target as an iteration aid only; full affected suites remain required before final behavior commits and releases.
- Establish the marker as the extension point for a later repository-wide change-aware selector without implementing path-to-test inference in this change.

## Capabilities

### Modified Capabilities

- `compatibility-tooling`: add a focused semantic smoke selection for native Codex/OpenAI wire-parity work.

## Impact

- **Configuration**: `pyproject.toml` marker registration.
- **Developer workflow**: `Makefile` help and one new target.
- **Tests**: marker-only metadata on selected existing tests; no test body or production behavior changes.
- **Runtime/portable app**: no production files, packaged assets, database, API, or restart changes.
