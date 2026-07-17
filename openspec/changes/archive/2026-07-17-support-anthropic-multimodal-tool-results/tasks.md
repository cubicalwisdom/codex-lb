## 1. Contract and RED coverage

- [x] 1.1 Record official Anthropic/OpenAI contracts, GitHub comparison, trust boundary, transport decisions, and non-goals.
- [x] 1.2 Add normative requirements for ordered image, document, and search-result tool output plus unchanged legacy behavior.
- [x] 1.3 Add failing converter, request-model, HTTP-route, and historical-slimming regressions.

## 2. Implementation

- [x] 2.1 Convert nested image/document/search-result blocks while retaining call pairing and order.
- [x] 2.2 Accept bounded inline text document sources and preserve all existing attachment limits.
- [x] 2.3 Preserve native output arrays through Responses validation and slim old inline result images during capacity recovery.
- [x] 2.4 Keep text-only and ToolSearch reference behavior unchanged and fail closed for unrelated block types.

## 3. Verification and portable delivery

- [x] 3.1 Run focused RED/GREEN and full relevant unit/integration suites.
- [x] 3.2 Run Ruff, scoped ty, strict change/spec validation, compilation, and `git diff --check`.
- [x] 3.3 Mirror changed runtime sources into both portable Python roots and verify matching SHA-256 hashes.
- [x] 3.4 Update `CODEXNEO_IMPLEMENTATION_LIST.md` and `HANDOVER_CODEXNEO_INTEGRATION.md` with exact evidence and residual limits.
- [x] 3.5 Drain active work, restart only Codex LB once, verify port 2455 health/readiness, and record acceptance results.
