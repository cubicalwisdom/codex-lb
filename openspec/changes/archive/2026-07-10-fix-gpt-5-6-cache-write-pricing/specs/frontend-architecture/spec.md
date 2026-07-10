## ADDED Requirements

### Requirement: Request detail identifies cache-write usage and cost

The dashboard request-log contract MUST accept nullable cache-write token counts and cache-write dollar cost. Recent-request detail SHALL show cache writes as a category separate from ordinary input and cache reads when the value is present and positive.

#### Scenario: Request contains cache writes

- **WHEN** a request-log row contains positive `cacheWriteTokens` and `cacheWriteInputUsd`
- **THEN** the recent-request token detail identifies the cache-write token count
- **AND** the cost summary identifies the cache-write cost separately

#### Scenario: Historical request has no cache-write value

- **WHEN** a historical request-log row has a null cache-write token count
- **THEN** the request detail remains valid
- **AND** it does not render a misleading cache-write segment

#### Scenario: Cache-write detail exists without cache-read detail

- **WHEN** a request log contains positive cache-write usage but omits the cache-read counter
- **THEN** the cost breakdown still identifies ordinary input and cache-write cost separately
- **AND** the cache-read cost remains zero rather than suppressing the cache-write category
