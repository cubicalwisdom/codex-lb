## Context

The portable Windows branch already contains local Responses lifecycle, cache-write pricing, native provider, and continuation work through CN-060. Six merged upstream PRs close additional Codex 0.144.1 / GPT-5.6 gaps, but wholesale cherry-picks would overwrite local behavior. The implementation therefore reconciles the final upstream contracts at the existing local extension points and mirrors the result into both portable Python roots.

## Goals / Non-Goals

**Goals:**

- Preserve native image, model-catalog, Responses Lite, directive, GPT-5.6, and interrupted-tool behavior across direct HTTP, HTTP bridge, and WebSocket paths.
- Keep live model metadata authoritative while providing an exact degraded-startup GPT-5.6 fallback.
- Preserve local CN-057 through CN-060 behavior and verify source, built frontend, and both portable runtimes together.
- Isolate account-import integration tests from the user's real Codex Home.

**Non-Goals:**

- Import unrelated upstream observability, automation, pricing, long-context, Flex, or API Priority work.
- Persist pending tool-call ids in the durable multi-instance bridge store.
- Restart Codex Desktop or the Electron shell automatically.

## Decisions

### Reconcile behavior instead of cherry-picking files

Each merged PR is ported at the smallest existing local boundary. This retains the local lifecycle/resource routes, pricing/cache-write accounting, provider routing, and CN-060 safe full-transcript recovery. Replacing upstream modules wholesale was rejected because the portable branch has substantial independent code in the same files.

### Derive Lite signaling from normalized protocol input

`additional_tools` is authoritative. Inbound reserved headers/metadata are removed and the canonical transport marker is synthesized only after model aliasing and API-key enforcement. Marker-only continuation requires the accepted downstream-visible Lite response id; replay, trim, owner-forward, and retry paths carry or reclassify the internally derived state.

### Preserve typed directives and interrupted outputs before accounting

Non-message system/developer directives bypass instruction lifting and sanitizer removal and remain compact-trim anchors. Interrupted function, custom, and apply-patch outputs are typed by their originating call. HTTP bridge injection happens before preparation so request size, fingerprints, stored input, and usage budgets describe the bytes sent upstream.

### Bound owner-forward recovery when pending state is remote-only

After a remote-owner relay fails without yielding, local recovery uses pending call state only if the rebound local session has it. A fresh local session resubmits the anchored request unchanged and masks any resulting missing-output rejection. Persisting call ids in the durable bridge was rejected for this reconciliation because it changes the shared-state schema and ownership protocol.

### Keep client-plane metadata separate from wire aliases

Sol and Terra advertise and persist `ultra`, while outbound policy rewrites it to upstream `max`; direct `max` and `xhigh` remain unchanged. `max` and `ultra` are not model-suffix tokens. The fallback catalog mirrors Codex rust-v0.144.1 metadata except for the intentionally omitted large `base_instructions` and personality-templated `model_messages`, which arrive through live refresh.

### Sandbox Codex Home side effects in integration tests

The application test fixture overrides the CodexNeo account-sync dependency with temporary Codex Home and backup roots plus a disabled command runner. Database isolation alone was insufficient because account imports also write native auth snapshots. This keeps future broad test runs from creating fixture accounts in the real user profile.

## Risks / Trade-offs

- **Remote-only pending call metadata cannot be reconstructed after ownership failure** -> resubmit unchanged and mask raw missing-output details as retryable continuity failure.
- **Fallback metadata can age** -> live refreshed catalog remains authoritative and unknown live fields remain lossless.
- **Selective reconciliation can miss a transport boundary** -> use product-path HTTP, bridge, WebSocket, model, image, API-key, and frontend regressions plus independent review.
- **Portable source can drift from the repo** -> mirror the exact changed Python set and built static tree, then verify SHA-256 equality and compile with both portable interpreters.

## Migration Plan

1. Apply source and frontend changes without modifying portable data, auth, or settings.
2. Run focused and combined backend/frontend verification with temporary Codex Home isolation.
3. Mirror changed Python files into portable `app` and portable site-packages, and mirror the exact built static tree.
4. Verify hashes and `py_compile` in both portable runtimes.
5. Sync and archive OpenSpec, update the tracker/handover, and leave runtime activation to the next safe backend or user-managed portable restart.

Rollback is file-level: restore the affected source/static files and both portable mirrors together. No new database schema belongs specifically to this six-PR reconciliation; the two pending migrations are retained from the already-verified CN-058/CN-059 work.

## Open Questions

None for this pass. Durable persistence of pending tool-call ids and automation-specific `ultra` dispatch remain explicit future-parity items.
