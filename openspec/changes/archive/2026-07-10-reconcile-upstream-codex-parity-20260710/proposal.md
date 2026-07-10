## Why

Six merged upstream changes from 2026-07-10 close native Codex compatibility gaps that remain partially or wholly absent from the portable Windows branch. The branch already contains CN-056 through CN-060 plus local lifecycle and pricing work, so the upstream behavior must be reconciled selectively instead of cherry-picked wholesale.

## What Changes

- Replace inbound-marker trust with canonical, body-derived Responses Lite signaling and preserve accepted same-model incremental continuity.
- Preserve future non-message system/developer directives byte-identically through normalization, sanitization, default-instruction handling, and compact trimming.
- Complete typed interrupted-output handling for function, custom, and apply-patch calls across WebSocket and HTTP bridge recovery paths while retaining CN-060 safe full-transcript recovery.
- Serve upstream-verified GPT-5.6 Sol/Terra/Luna bootstrap metadata, max/ultra UI and API-key support, and the `ultra` to `max` wire alias without changing CN-059 pricing.
- Add native Codex image generation/edit aliases and Codex catalog negotiation on `/v1/models?client_version=...`.

## Non-goals

- Do not import unrelated upstream subsystems, automations, image-route observability prerequisites, pricing tables, or draft PRs.
- Do not remove CN-057 `model_messages` preservation, CN-058 lifecycle resources, CN-059 pricing/cache-write support, or CN-060 one-shot safe full-transcript recovery.
- Do not restart Codex Desktop or the Electron shell automatically.

## Impact

- Capabilities: `responses-api-compat`, `model-catalog-compat`, `images-api-compat`, `api-keys`, and `frontend-architecture`.
- Runtime: source plus both active portable Python mirrors; frontend static assets when the reasoning controls change.
- Verification: RED/GREEN product-path regressions, focused integration suites, independent review, combined backend/frontend checks, and portable hash/compile verification.
