## ADDED Requirements

### Requirement: Request logs persist cache-write tokens compatibly

The database migration graph MUST add a nullable integer `cache_write_tokens` column to `request_logs` from the current single Alembic head. Upgrade and downgrade MUST preserve a single valid graph, and historical rows MUST remain valid with a null value rather than an inferred backfill.

#### Scenario: Existing database upgrades

- **WHEN** an existing database upgrades from the prior head
- **THEN** `request_logs.cache_write_tokens` exists and is nullable
- **AND** pre-existing request rows have a null cache-write value

#### Scenario: Migration downgrades

- **WHEN** the cache-write migration is downgraded
- **THEN** only the `cache_write_tokens` column is removed
- **AND** the migration graph returns to the prior head
