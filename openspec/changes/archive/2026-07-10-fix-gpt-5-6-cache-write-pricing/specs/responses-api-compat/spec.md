## ADDED Requirements

### Requirement: Responses cache-write usage remains typed and available for accounting

The proxy MUST parse `usage.input_tokens_details.cache_write_tokens` as a non-negative token count when it is present and MUST carry the value through every successful Responses finalization path used for request accounting.

#### Scenario: HTTP response reports cache-write tokens

- **WHEN** an HTTP Responses completion reports `input_tokens_details.cache_write_tokens = 1000`
- **THEN** the typed response usage exposes `cache_write_tokens = 1000`
- **AND** the finalized request log receives `cache_write_tokens = 1000`

#### Scenario: Websocket response omits cache-write tokens

- **WHEN** a websocket Responses completion omits `input_tokens_details.cache_write_tokens`
- **THEN** the typed response remains valid
- **AND** the finalized request log records a null cache-write count

#### Scenario: Upstream reports a negative cache-write count

- **WHEN** a Responses completion reports a negative `input_tokens_details.cache_write_tokens`
- **THEN** the typed usage normalizes the value to zero
- **AND** request-log persistence cannot store a negative cache-write count
