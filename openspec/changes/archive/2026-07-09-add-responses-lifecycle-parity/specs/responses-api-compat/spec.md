## ADDED Requirements

### Requirement: Stored Responses lifecycle is API-key scoped

`POST /v1/responses` with `store=true` or `background=true` MUST create a durable response resource scoped to the authenticated downstream API key. The same scope MUST be able to retrieve the resource, list its input items, and delete it. Other API-key scopes MUST receive an OpenAI-style not-found error and MUST NOT learn whether the resource exists.

#### Scenario: Stored synchronous response is retrievable

- **WHEN** a client creates a non-streaming response with `store=true`
- **THEN** the terminal public response is persisted
- **AND** `GET /v1/responses/{response_id}` returns the same response id, status, output, and usage

#### Scenario: Response cannot cross API-key scopes

- **GIVEN** a stored response was created by one API key
- **WHEN** another API key retrieves, lists input items for, cancels, or deletes that id
- **THEN** the service returns the same not-found contract as an unknown id

### Requirement: Background Responses have an owned cancellable lifecycle

`POST /v1/responses` with `background=true` MUST return promptly with a durable queued response and a stable public id. The application MUST own and track the execution task, persist in-progress and terminal states, cancel and await owned tasks during shutdown, and mark stranded non-terminal records failed during startup recovery. `POST /v1/responses/{response_id}/cancel` MUST cancel only an active background response in the same API-key scope.

#### Scenario: Background response completes after polling

- **WHEN** a client creates a response with `background=true`
- **THEN** create returns a response with `status=queued` or `status=in_progress`
- **AND** later retrieval returns a terminal response with the same public id

#### Scenario: Active background response is cancelled

- **WHEN** the owning client cancels an active background response
- **THEN** the owned task is cancelled and awaited
- **AND** the durable response status becomes `cancelled`

### Requirement: Stored response input items are listable

`GET /v1/responses/{response_id}/input_items` MUST return the normalized input items recorded for a same-scope stored response. Items MUST have stable ids, preserve input ordering, and support `after`, `limit`, and `order` cursor parameters using the OpenAI list envelope.

#### Scenario: String input becomes one stable message item

- **GIVEN** a stored response created from string input
- **WHEN** the owner lists input items twice
- **THEN** both calls return the same message item id and input text

### Requirement: Input-token count is explicit about local limitations

`POST /v1/responses/input_tokens` MUST return a deterministic `input_tokens` count for locally visible text and tool definitions. It MUST reject file/image references and unresolved previous-response context with an OpenAI-style error rather than report an invented exact count. The result MUST NOT be used as actual upstream billing usage.

#### Scenario: Text request receives a deterministic count

- **WHEN** the same text-only token-count payload is submitted twice
- **THEN** both responses contain the same non-negative `input_tokens` value

#### Scenario: Opaque input is rejected

- **WHEN** token counting depends on a file, image, or unresolved upstream response
- **THEN** the service returns HTTP 400 with a stable explicit error code

### Requirement: Conversations and items are durable scoped resources

The `/v1/conversations` resource and its item subresource MUST support create, retrieve, metadata update, delete, item create, item retrieve, item delete, and cursor-based item list operations within the owning API-key scope. Conversation ids and item ids MUST be stable. Deleting a conversation MUST delete its items.

#### Scenario: Conversation CRUD preserves metadata

- **WHEN** a client creates a conversation, updates its metadata, and retrieves it
- **THEN** the same conversation id and updated metadata are returned

#### Scenario: Conversation items preserve order

- **WHEN** a client adds multiple items and lists them ascending
- **THEN** the returned items match insertion order and have stable ids

### Requirement: Responses can execute against local conversation state

When a same-scope `POST /v1/responses` names a local conversation, the service MUST expand existing conversation items before new input for private upstream execution, MUST NOT forward the local conversation id as an upstream resource id, and MUST append the successful response input and output items back to that conversation in order. Unknown or cross-scope conversation ids MUST fail before upstream execution.

#### Scenario: Conversation response uses accumulated context

- **GIVEN** a conversation already contains one user message
- **WHEN** the owner creates a response with that conversation and new input
- **THEN** upstream execution receives the prior item before the new input
- **AND** successful response input and output are appended to the conversation

## MODIFIED Requirements

### Requirement: Unsupported Responses controls fail explicitly

The HTTP Responses compatibility surfaces MUST return HTTP 400 with an OpenAI-style error whose `code` is `unsupported_parameter` and whose `param` identifies the field when a request asks for generation behavior the ChatGPT-backed upstream cannot honor. `background=true`, `store=true`, and locally supported `metadata` are no longer unsupported on `/v1/responses`; they MUST be handled by the local lifecycle layer and removed before private upstream forwarding. Explicitly supplied unsupported controls such as `max_output_tokens`, `prompt_cache_retention`/`promptCacheRetention`, `safety_identifier`, `temperature`, `top_p`, `truncation`, or `user` MUST still fail and MUST NOT be silently discarded.

#### Scenario: Locally implemented persistence flags are accepted

- **WHEN** a `/v1/responses` client sends `store=true` or `background=true`
- **THEN** the local lifecycle implementation handles the requested behavior
- **AND** the unsupported private-upstream flags are not forwarded

#### Scenario: Unsupported generation control is supplied

- **WHEN** a client explicitly supplies one of the remaining unsupported generation controls
- **THEN** the service returns HTTP 400 with `code=unsupported_parameter`
- **AND** the error identifies the exact field in `param`
