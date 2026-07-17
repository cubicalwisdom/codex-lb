## Context

The active Anthropic facade translates Messages requests into codex-lb Responses requests at the public boundary. The Responses execution path already owns account selection, file-account pinning, cache affinity, upstream retries, usage settlement, and SSE normalization. New features must remain adapters over that path rather than create a second provider client.

## Goals

- Support base64/URL images and locally extract base64 document/PDF blocks without silently discarding a user attachment.
- Treat Anthropic `cache_control` as an affinity hint, not as a claim that Anthropic cache billing semantics were reproduced.
- Provide a durable local batch resource whose requests are independently validated and executed through the same non-streaming Messages path.
- Preserve official compaction blocks and prevent an oversized message request from reaching a 272k upstream model window.
- Convert local account-capacity pressure into bounded wait/retry behavior before returning an Anthropic rate-limit error.

## Non-Goals

- Emulate Anthropic-hosted Files storage, document citations, server tools, batch pricing, or exact Anthropic cache billing.
- Raise `proxy_account_response_create_limit` as part of this feature. Capacity policy remains an operator setting.
- Modify existing OpenAI, Codex, or non-local Claude Desktop discovery contracts.

## Decisions

### Attachments

Images are converted to Responses `input_image` parts with either a validated data URL or an HTTPS URL. UTF-8 text/CSV documents and text-bearing PDFs are decoded locally into bounded, labelled `input_text` parts so the private ChatGPT-backed transport never receives its rejected inline `input_file` shape. PDF extraction preserves page labels, rejects encrypted or image-only/scanned documents, and checks page count, page content-stream size, and total extracted character limits before forwarding. URL documents remain fail-closed because synchronous request normalization cannot fetch them without adding an SSRF-sensitive network client; callers must provide base64. The facade does not emulate OCR or document citations.

### Cache controls

The facade accepts top-level and supported block-level `cache_control` values. It removes Anthropic-only cache fields before forwarding and derives a deterministic `prompt_cache_key` from the client model, normalized stable prefix, tools, instructions, and cache-control boundaries. This preserves codex-lb's upstream/account cache affinity. The response usage reports only upstream-supplied cached/cache-write tokens; the facade does not manufacture Anthropic cache billing fields.

### Context management

The facade validates the shape of `context_management.edits` and uses it as explicit permission for local automatic compaction. The already-authenticated, loopback-only `claudedesktop` profile is also treated as permission to compact when Claude Desktop omits that optional field; this exception is evaluated from the trusted request profile rather than a caller-controlled model name. Before execution the facade makes a conservative serialized-input estimate and reserves the caller's requested output below the mapped provider budget. A near-limit request without either explicit permission or the local Desktop profile fails locally with an Anthropic context-limit error. A permitted request compacts historic turns through the existing upstream Responses compact transport, retains the returned encrypted artifact as native Responses input, and preserves the newest user turn. If Claude Desktop's translated top-level system instructions exceed the upstream Responses `instructions` field's 1,048,576-character limit, the facade first moves them into bounded system input blocks so the compact transport can consume them; it never truncates the system prompt or forwards the over-limit field. The public response carries `x-codex-lb-context-compacted: true`, and the runtime records a sanitized automatic-compaction event; no Anthropic text summary or cache billing is invented. A request with no historic prefix remains an explicit error because there is nothing safe to compact, except that an oversized Desktop system prompt itself becomes a compactable protected prefix.

### Batches

Batches are persisted in SQLite/Postgres with request parameters, terminal result/error, cancellation state, API-key scope, timestamps, and request counts. A bounded runtime manager executes queued batch requests through the canonical non-streaming Responses collection path. Results are returned as JSONL and may be unordered. Startup requeues incomplete records only when their persisted request is safe to resume; canceled and terminal records are never resumed.

### Reliability

The Anthropic facade performs bounded pre-stream retry for selected local Desktop capacity/transient failures. It never retries after client-visible stream bytes or repeats tool calls. Retry and capacity outcomes are recorded with sanitized failure classification.
