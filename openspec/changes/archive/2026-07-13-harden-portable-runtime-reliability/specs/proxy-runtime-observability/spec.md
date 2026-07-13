## ADDED Requirements

### Requirement: Request finalization SHALL survive concurrent account removal

Request-log persistence SHALL retain request, model, token, cost, status, and captured account metadata when its account is removed before commit. The retained log SHALL use a null account foreign key and SHALL NOT recreate the deleted account.

#### Scenario: Account is deleted before request-log commit

- **WHEN** a request completed using an account that no longer exists at log commit time
- **THEN** request-log persistence SHALL retry without the account foreign key
- **AND** the completed request statistics SHALL remain queryable

### Requirement: Portable redirected logs SHALL be bounded

The Electron portable launcher SHALL rotate redirected backend stdout and stderr logs by configured size and retained-file count before opening them for append.

#### Scenario: Redirected log exceeds the configured limit

- **WHEN** the portable backend is next launched
- **THEN** the existing log SHALL be rotated before new output is appended
- **AND** files older than the retained count SHALL be removed

### Requirement: OpenAPI operation identifiers SHALL be unique

Every generated OpenAPI operation SHALL have a unique operation identifier, including endpoints that intentionally support more than one HTTP method.

#### Scenario: Thread goal retrieval supports GET and POST

- **WHEN** the OpenAPI document is generated
- **THEN** the GET and POST operations SHALL have distinct identifiers
