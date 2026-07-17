## ADDED Requirements

### Requirement: Messages accepts supported attachments without loss

The Anthropic Messages facade MUST translate supported user image blocks using base64 or HTTPS sources into Responses image input items. It MUST decode supported base64 plain-text, CSV, and text-bearing PDF document blocks locally and insert bounded, labelled text in the same user-message position; it MUST NOT forward those documents through an upstream file shape that the mapped ChatGPT transport rejects. Invalid media types, invalid base64 payloads, encrypted PDFs, scanned/image-only PDFs without extractable text, oversized inline or extracted payloads, URL document sources, and unsupported source types MUST return an Anthropic `invalid_request_error` before upstream execution. Existing text, tool-use, and tool-result ordering MUST remain unchanged, and PDF page boundaries MUST remain visible in the extracted text.

#### Scenario: A base64 image reaches the Responses input

- **WHEN** a valid Anthropic user image block uses a base64 PNG source
- **THEN** the forwarded Responses input contains an `input_image` data URL part in the same user message position
- **AND** the Anthropic response retains the caller-visible model name

#### Scenario: A text-bearing PDF is extracted locally

- **WHEN** a valid base64 PDF document contains extractable text on one or more pages
- **THEN** the forwarded Responses input contains labelled text with the document title and page boundaries in the same user-message position
- **AND** it does not contain an `input_file` item

#### Scenario: A scanned PDF fails explicitly

- **WHEN** a base64 PDF contains no extractable text
- **THEN** the facade returns an Anthropic `invalid_request_error` before upstream execution
- **AND** it does not silently discard the document or invent OCR output

### Requirement: Cache-control preserves affinity without false billing

The facade MUST accept supported top-level and block-level Anthropic `cache_control` declarations. It MUST remove Anthropic-only cache fields before forwarding and derive a deterministic Responses `prompt_cache_key` from the normalized cacheable prefix. It MUST expose cached/cache-write usage only when those values are supplied by the upstream result.

#### Scenario: Identical cacheable prefixes share affinity

- **WHEN** two otherwise compatible requests contain the same normalized cacheable prefix and cache-control boundaries
- **THEN** both forwarded Responses requests use the same `prompt_cache_key`

### Requirement: Context management protects the provider window

The facade MUST validate `context_management.edits` as an explicit automatic-compaction opt-in. The authenticated loopback-only `claudedesktop` profile MUST also authorize automatic near-limit compaction when the field is omitted; model names or remote requests MUST NOT select this exception. Before execution the facade MUST conservatively estimate normalized serialized input and reserve the requested output below the mapped provider-safe budget. A near-limit request without either explicit opt-in or the local Desktop profile MUST return an Anthropic `invalid_request_error` with an explicit context-limit message before upstream execution. For a permitted near-limit request with historical turns, the facade MUST compact only the historic prefix through the existing Responses compact transport, retain the upstream encrypted artifact internally, and preserve the newest user turn. When authenticated local Claude Desktop system instructions exceed the upstream `instructions` field limit, the facade MUST preserve the full prompt in bounded system input blocks that can enter the compact prefix; it MUST NOT truncate the prompt or forward an over-limit `instructions` value. It MUST return `x-codex-lb-context-compacted: true` when that compact path was used. A near-limit request without a historic prefix MUST fail before compact or normal upstream execution unless the protected oversized system prompt supplies the compactable prefix.

#### Scenario: Opted-in near-limit context is compacted before execution

- **WHEN** normalized input plus requested output exceeds the mapped provider-safe budget and `context_management.edits` is supplied
- **THEN** the facade compacts the historic transcript before executing the newest user turn
- **AND** the response carries the context-compacted marker

#### Scenario: Local Claude Desktop compacts without an explicit edit

- **WHEN** the authenticated loopback `claudedesktop` profile sends a near-limit transcript with historical turns and omits `context_management.edits`
- **THEN** the facade compacts the historic transcript before executing the newest user turn
- **AND** the response carries the context-compacted marker

#### Scenario: Oversized Desktop system instructions remain compactable

- **WHEN** authenticated local Claude Desktop sends system instructions longer than the upstream Responses `instructions` field limit
- **THEN** the facade moves the complete prompt into bounded system input blocks before compacting it
- **AND** neither the compact request nor final response request forwards an over-limit `instructions` field
- **AND** the newest user turn remains verbatim after the compact artifact

#### Scenario: Other callers still require explicit permission

- **WHEN** any request outside the authenticated loopback `claudedesktop` profile exceeds the mapped provider-safe budget and omits `context_management.edits`
- **THEN** the facade returns an Anthropic `invalid_request_error` before compact or normal upstream execution

### Requirement: Message batches are durable and independently executable

The facade MUST provide `POST /v1/messages/batches`, batch retrieval/listing, cancellation, deletion, and JSONL results retrieval. Each batch request MUST be independently validated and executed through the canonical non-streaming Messages/Responses path. Batch result records MUST persist successful Messages, Anthropic-shaped errors, cancellation, or expiration outcomes and MUST be scoped to the requesting API key.

#### Scenario: Batch results remain matchable after unordered execution

- **WHEN** a batch containing distinct `custom_id` values completes out of order
- **THEN** the JSONL results contain one terminal object per request with its original `custom_id`

### Requirement: Local capacity pressure is retried safely

For a local Claude Desktop request that receives a configured pre-stream recoverable capacity/transient failure before any response bytes, the facade MUST use bounded retry before returning an Anthropic error. It MUST NOT retry after streamed output begins or repeat a request containing a completed tool action.

#### Scenario: Capacity becomes available during the bounded wait

- **WHEN** the first local account selection is saturated and an eligible account becomes available within the configured wait budget
- **THEN** the request completes through normal Messages execution
