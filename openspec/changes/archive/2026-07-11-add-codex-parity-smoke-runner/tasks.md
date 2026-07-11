# Tasks

## 1. Contract and red evidence

- [x] 1.1 Validate this change strictly and confirm the exact 16-node / 18-case inventory still exists.
- [x] 1.2 Run marker-only collection before implementation and record the expected empty-selection failure.

## 2. Focused runner implementation

- [x] 2.1 Register the `codex_parity_smoke` pytest marker.
- [x] 2.2 Mark the agreed 16 test nodes without changing their bodies, parameters, or ordinary full-suite behavior.
- [x] 2.3 Add and document `make test-codex-parity-smoke` without changing `ci-fast`, `ci`, or existing required targets.

## 3. Verification and closeout

- [x] 3.1 Confirm marker collection selects exactly 16 nodes / 18 cases and no unintended tests.
- [x] 3.2 Run the focused Make target and the direct explicit-node selection to green.
- [x] 3.3 Run the relevant full affected test files, Ruff, strict OpenSpec validation, and `git diff --check`.
- [x] 3.4 Complete an independent exact-diff review and address every Critical or Important finding.
- [x] 3.5 Sync/archive the OpenSpec change, update the implementation list and handover, and commit without pushing.
