## ADDED Requirements

### Requirement: Continuation-only Responses requests are accepted

`POST /v1/responses` and OpenAI-compatible requests sent to `POST /backend-api/codex/responses` MUST accept a request with no `input` or `messages` when it contains exactly one non-empty continuity key: `previous_response_id` or `conversation`. The normalized upstream payload MUST use empty instructions and an empty input list when those fields are omitted. Requests containing both continuity keys MUST remain invalid.

#### Scenario: Continue by previous response without new input

- **WHEN** a client sends a model and non-empty `previous_response_id` without `input` or `messages`
- **THEN** local validation accepts the request
- **AND** the normalized payload contains the same `previous_response_id`, `instructions=""`, and `input=[]`

#### Scenario: Continue by conversation without new input

- **WHEN** a client sends a model and non-empty `conversation` without `input` or `messages`
- **THEN** local validation accepts the request
- **AND** the normalized payload contains the same `conversation`, `instructions=""`, and `input=[]`

### Requirement: Unsupported Responses controls fail explicitly

The HTTP Responses compatibility surfaces MUST return HTTP 400 with an OpenAI-style error whose `code` is `unsupported_parameter` and whose `param` identifies the field when a request asks for behavior the ChatGPT-backed upstream cannot honor. This includes `background=true`, `store=true`, and explicitly supplied `max_output_tokens`, `metadata`, `prompt_cache_retention`/`promptCacheRetention`, `safety_identifier`, `temperature`, `top_p`, `truncation`, or `user`. The service MUST NOT silently accept and discard those requested behaviors.

#### Scenario: Background execution is requested without lifecycle support

- **WHEN** a client sends `background=true`
- **THEN** the service returns HTTP 400 with `code=unsupported_parameter` and `param=background`
- **AND** no upstream response job is created

#### Scenario: Unsupported generation control is supplied

- **WHEN** a client explicitly supplies one of the unsupported generation controls
- **THEN** the service returns HTTP 400 with `code=unsupported_parameter`
- **AND** the error identifies the exact field in `param`

#### Scenario: Explicit false flags remain compatible

- **WHEN** a client sends `background=false` or `store=false`
- **THEN** local validation accepts the flag
- **AND** the proxy does not enable background execution or persistence upstream
