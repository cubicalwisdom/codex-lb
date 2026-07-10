## ADDED Requirements

### Requirement: Codex compaction triggers are bridged into compact output

When `POST /backend-api/codex/responses` receives a request whose top-level `input` array contains exactly one `{"type":"compaction_trigger"}` item as its final element, the proxy SHALL remove that trigger before calling upstream compaction handling and SHALL emit a raw SSE stream that contains exactly one compaction output item.

The stream MUST include a `response.output_item.done` event whose `item` is a `compaction` record, and the terminal `response.completed` event MUST carry the same single compaction item in `response.output`.

When the canonical upstream compact payload supplies an explicit compaction output item with a non-empty string `id`, the proxy MUST preserve that `id` unchanged. The identical preserved item MUST appear in `response.output_item.done.item` and `response.completed.response.output[0]`.

When the proxy derives the compaction item from the legacy top-level `compaction_summary` fallback, it MUST remain compatible with that ID-less shape and MUST NOT invent an item `id`.

The standalone `/responses/compact` endpoint is unchanged by this requirement.

#### Scenario: terminal trigger is converted into a compact stream
- **WHEN** a `POST /backend-api/codex/responses` request ends with exactly one top-level `compaction_trigger`
- **THEN** the proxy strips the trigger, invokes compact handling, and streams one `response.output_item.done` event containing a `compaction` item
- **AND** the terminal `response.completed` event carries that same item in `response.output`

#### Scenario: canonical compact output identity is preserved
- **WHEN** upstream compact handling returns an explicit compaction output item with a non-empty string `id`
- **THEN** the proxy preserves that `id` unchanged in `response.output_item.done.item`
- **AND** `response.completed.response.output[0]` is identical to the preserved item

#### Scenario: legacy compact summary remains ID-less
- **WHEN** upstream compact handling returns only the legacy top-level `compaction_summary`
- **THEN** the proxy derives a compaction item without inventing an `id`
- **AND** it emits that same ID-less item in both stream locations

#### Scenario: malformed trigger placement is rejected
- **WHEN** a `POST /backend-api/codex/responses` request contains a duplicated or non-terminal top-level `compaction_trigger` item
- **THEN** the proxy returns HTTP 400 with `invalid_request_error`
- **AND** it does not attempt upstream compaction handling
