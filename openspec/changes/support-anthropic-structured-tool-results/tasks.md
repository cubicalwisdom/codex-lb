## 1. Contract and evidence

- [x] 1.1 Record the historical conversation failure, GitHub comparison, native upstream probe, compatibility boundary, and explicit non-goals.
- [x] 1.2 Add normative requirements for native complete-pair replay, deterministic fallback, validation, and unchanged text behavior.

## 2. RED/GREEN implementation

- [x] 2.1 Add failing converter regressions for a complete ToolSearch pair, multiple/unknown references, fallback preservation, and unchanged text output.
- [x] 2.2 Add a failing `/v1/messages?beta=true` regression using the exact poisoned historical sequence.
- [x] 2.3 Implement the smallest pair pre-scan and request translation changes that make the regressions pass.
- [x] 2.4 Run focused converter and route tests and keep ordinary function/web-tool behavior green.

## 3. Verification and portable delivery

- [x] 3.1 Run the full Anthropic unit/integration suite, Ruff, scoped ty, strict OpenSpec validation, and `git diff --check`.
- [x] 3.2 Mirror `messages.py` into both portable Python roots, require matching SHA-256 values, and compile both copies.
- [x] 3.3 Drain active work, restart only Codex LB through the existing app-owned path, and verify port 2455 health/readiness with minimal downtime.
- [ ] 3.4 Retry the existing poisoned Claude conversation, then run fresh WebFetch, WebSearch, ToolSearch, and ordinary tool-call acceptance. The poisoned `/schedule` retry now passes the former converter failure and reaches Claude's `AskUserQuestion` permission step; a fresh all-tool sweep remains pending because Claude Desktop exited before it could be completed and was not restarted.
- [x] 3.5 Update `CODEXNEO_IMPLEMENTATION_LIST.md` and `HANDOVER_CODEXNEO_INTEGRATION.md` with exact evidence and remaining exclusions.
