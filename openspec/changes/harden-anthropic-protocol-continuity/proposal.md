## Why

The Claude Desktop Messages facade now covers text, tools, web tools, attachments, batches, and local compaction, but three protocol edges can still break otherwise valid long-running conversations. Anthropic tool identifiers can exceed the mapped Responses limits, opaque reasoning state is not replayed, and a direct Claude Desktop stream can commit HTTP 200 before translating an immediately returned Responses error.

## What Changes

- Map over-limit Anthropic tool names and tool-use IDs to deterministic Responses-safe identifiers, use the same mapping everywhere in the request, and restore original tool names in Anthropic output.
- Request, translate, and replay upstream encrypted reasoning state through Anthropic thinking signatures without inventing or logging private reasoning.
- Inspect the first semantic Responses stream event before committing the Anthropic stream and convert an immediate error into the normal Anthropic HTTP error/retry path.
- Add protocol fixtures and sanitized translation telemetry for identifier mapping, reasoning continuity, and startup-stream outcomes.

## Capabilities

### New Capabilities

- `anthropic-protocol-continuity`: Defines identifier, reasoning-state, pre-header streaming, and translation-observability guarantees for the Anthropic Messages facade.

## Impact

- Changes only the Anthropic Messages boundary and its focused tests, OpenSpec records, tracking notes, and portable mirrors.
- Reuses the existing Responses execution, retry, error, and SSE layers; no sidecar or second upstream client is introduced.
- Does not change model routing, account selection, context budgets, batch persistence, or non-Anthropic endpoints.
