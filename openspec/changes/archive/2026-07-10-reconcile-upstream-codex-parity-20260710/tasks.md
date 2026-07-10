## 1. Contract and RED coverage

- [x] 1.1 Add product-path RED regressions for native image aliases and `/v1/models` Codex negotiation.
- [x] 1.2 Add RED regressions for canonical Lite signaling, accepted same-model incremental continuity, stale-marker stripping, and preserved non-message directives.
- [x] 1.3 Add RED regressions for apply-patch failed outputs, inject-before-prepare accounting, recovery reinjection, replay trimming, and zero-input continuity.
- [x] 1.4 Add RED regressions for exact GPT-5.6 bootstrap metadata, API-key max/ultra support, and dashboard/frontend reasoning options.

## 2. Selective implementation

- [x] 2.1 Implement native image aliases and `/v1/models?client_version` negotiation without replacing the local proxy API module.
- [x] 2.2 Reconcile final body-derived Lite signaling and byte-identical directive preservation while retaining CN-056 behavior.
- [x] 2.3 Reconcile official GPT-5.6 metadata and max/ultra surfaces while retaining CN-057 model fields and CN-059 pricing.
- [x] 2.4 Reconcile final interrupted-output hardening while retaining CN-060 safe full-transcript recovery.

## 3. Verification and review

- [x] 3.1 Independently review every slice against its final merged upstream head and current local behavior.
- [x] 3.2 Run focused backend regressions, affected integration suites, Ruff, scoped `ty`, frontend tests/typecheck/lint/build, and strict OpenSpec validation.
- [x] 3.3 Run combined cross-slice regression gates and inspect the final diff for unrelated changes.

## 4. Portable closeout

- [x] 4.1 Mirror all changed backend modules to both portable Python locations and verify SHA-256 equality and `py_compile` in both runtimes.
- [x] 4.2 Rebuild and mirror frontend static assets when required, then verify production asset hashes.
- [x] 4.3 Update the CodexNeo implementation tracker and handover, sync and archive this change, and do not restart Codex Desktop or Electron automatically.
