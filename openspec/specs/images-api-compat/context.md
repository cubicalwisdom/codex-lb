# Images API Compatibility Context

## Purpose and Decisions

Native Codex image aliases reuse the existing OpenAI-compatible image pipeline so authentication, validation, routing, and error envelopes stay consistent.

- `POST /backend-api/codex/images/generations` delegates to the existing generation handler and remains hidden from the public OpenAPI schema.
- `POST /backend-api/codex/images/edits` accepts the native JSON `images[].image_url` data-URL form, decodes it into the existing edit request shape, and delegates to the same edit handler.
- `/v1/images/edits` keeps its existing multipart contract.
- Upstream image-route observability prerequisites from PR #1160 are intentionally not imported in this portable reconciliation; this is a route/protocol parity change only.

For example, a native Codex JSON edit and an equivalent `/v1/images/edits` multipart edit reach the same local validation and upstream execution path after transport-specific decoding.
