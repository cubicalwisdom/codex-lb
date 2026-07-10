## Context

GPT-5.6 Responses Lite carries its executable tool bundle as an ordered `additional_tools` input item rather than a top-level `tools` field. Existing instruction lifting treated adjacent developer content as ordinary prompt instructions and could remove the protocol envelope.

## Goals / Non-Goals

**Goals:** preserve the complete Lite input order and translate the reserved marker correctly for HTTP, compact, HTTP-to-WebSocket bridge, and native WebSocket transports.

**Non-Goals:** synthesize top-level tools, disable Responses Lite, alter GPT-5.6 metadata/pricing, or restart Codex Desktop automatically.

## Decisions

- Treat the ordered `additional_tools` envelope as protocol data and bypass instruction lifting for the complete Lite input.
- Use the reserved HTTP header only for upstream HTTP/compact requests. Encode the equivalent value in each WebSocket `response.create.client_metadata` and omit the HTTP-only marker from the WebSocket handshake.
- Keep non-native clients from enabling the internal contract by supplying the reserved marker alone.
- Mirror verified source/static output into the active portable runtime and verify hashes before activation.

## Risks / Trade-offs

- **Transport-specific marker drift** -> cover request normalization, direct HTTP, bridge, and native WebSocket product paths.
- **Future compaction removes the Lite prefix** -> retain the protocol envelope as an anchor and keep the authoritative requirement in the Responses compatibility spec.

## Migration Plan

Deploy the normalization and transport changes together, mirror the portable runtime, validate all affected paths, and roll back the same file set together if needed.

## Open Questions

None. Later body-derived trust and anchored incremental-continuity hardening is tracked by the superseding upstream reconciliation change.
