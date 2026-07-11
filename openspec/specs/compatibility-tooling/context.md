# Codex parity smoke runner

## Purpose and scope

`codex_parity_smoke` is the fast first feedback loop for native Codex/proxy wire compatibility. It covers curated Responses Lite, compact, HTTP bridge, native WebSocket, and negotiated model-catalog semantics. It does not replace affected suites or release gates.

## Decisions and constraints

- Membership lives on tests as a semantic pytest marker rather than in a duplicated node-id manifest.
- `make test-codex-parity-smoke` uses the repository pytest safety options and strict marker validation.
- A structural workflow contract keeps the Make target standalone: it must be `.PHONY`, have no direct, duplicate, or multi-target prerequisites, and contain exactly the approved frozen-sync and marker-only pytest recipe.
- On Windows without GNU Make, run `uv run pytest -q -ra -o faulthandler_timeout=300 -o faulthandler_exit_on_timeout=true --timeout=180 --timeout-method=thread --durations=20 --strict-markers -m codex_parity_smoke` directly.
- Existing `ci-fast`, `ci`, required checks, and release verification remain authoritative.
- Git-diff selection and non-Codex families are intentionally deferred to a later repository-wide change-aware runner.

## Failure modes

Pytest exits nonzero when a selected regression fails or when no marked tests are collected. An empty selection is therefore a failed compatibility check, not a success. The structural workflow test also fails if another Make declaration, including a multi-target rule, attaches a prerequisite or changes the approved recipe.

## Example

After changing Responses Lite serialization, run the smoke command for early feedback. Before committing the behavior change, still run the complete affected proxy/Responses/bridge files and required static/OpenSpec gates.
