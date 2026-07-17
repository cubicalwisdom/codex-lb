# database-migrations Specification

## Purpose

Define migration, drift detection, and Alembic governance contracts so deployments fail closed on schema mismatch.
## Requirements
### Requirement: Alembic as migration source of truth

The system SHALL use Alembic as the only runtime migration mechanism and SHALL NOT execute custom migration runners. Dashboard settings schema changes, including weekly pace working days, MUST be represented by Alembic revisions and ORM metadata so startup drift detection can verify them.

#### Scenario: Application startup performs Alembic migration

- **WHEN** the application starts
- **THEN** it runs Alembic upgrade to `head`
- **AND** it applies fail-fast behavior according to configuration

#### Scenario: Dashboard settings migration persists weekly pace working days

- **WHEN** migrations run to head on an existing install
- **THEN** `dashboard_settings` contains a non-null `weekly_pace_working_days` column
- **AND** existing rows default to `0,1,2,3,4,5,6`

### Requirement: Startup schema drift guard

After startup migrations report success, the system SHALL verify that the live database schema matches ORM metadata before the application continues normal startup. If drift remains, the system SHALL surface explicit drift details and SHALL apply fail-fast behavior according to configuration instead of silently serving with a divergent schema.

#### Scenario: Startup detects drift with fail-fast enabled

- **GIVEN** startup migrations complete without raising an Alembic upgrade error
- **AND** post-migration schema drift check returns one or more diffs
- **AND** `database_migrations_fail_fast=true`
- **WHEN** application startup continues
- **THEN** the system raises an explicit startup error that includes schema drift context
- **AND** the application does not continue normal startup

#### Scenario: Startup detects drift with fail-fast disabled

- **GIVEN** startup migrations complete without raising an Alembic upgrade error
- **AND** post-migration schema drift check returns one or more diffs
- **AND** `database_migrations_fail_fast=false`
- **WHEN** application startup continues
- **THEN** the system logs the drift details as an error
- **AND** it does not silently suppress the drift context

### Requirement: Request-log account deletion preserves historical rows

The database schema SHALL preserve historical `request_logs` rows when their parent account is deleted. The schema MUST support a nullable request-log soft-delete marker and MUST NOT use a cascading account foreign key that deletes request-log history.

#### Scenario: Request-log soft-delete schema exists after migration

- **WHEN** migrations run to head
- **THEN** `request_logs` contains a nullable `deleted_at` column
- **AND** the dashboard request-log list path has an index that supports filtering non-deleted rows latest-first

#### Scenario: Request-log account foreign key no longer cascades

- **WHEN** migrations run to head
- **THEN** the `request_logs.account_id -> accounts.id` foreign key uses `ON DELETE SET NULL`
- **AND** deleting an account at the database level does not delete matching request-log rows

### Requirement: Limit warm-up persistence

The database SHALL persist global warm-up settings, per-account opt-in, warm-up attempt history, and request-log source metadata.

#### Scenario: Warm-up attempt is unique per reset
- **WHEN** an attempt is stored for an account, window, and reset timestamp
- **THEN** the database enforces uniqueness for that account/window/reset tuple

#### Scenario: Existing installs remain disabled
- **WHEN** an existing database is migrated
- **THEN** global warm-up is disabled
- **AND** all existing accounts remain opted out

#### Scenario: Warm-up request logs remain separable from user traffic
- **WHEN** a warm-up request is logged
- **THEN** the request log records a source value that allows account usage summaries to exclude internal warm-up traffic

### Requirement: Responses lifecycle resources have a reversible schema

The database SHALL persist API-key-scoped stored responses, conversations, and ordered conversation items through an Alembic revision on the current single-head migration graph. The schema MUST cascade conversation deletion to its items, index resource scope lookups, and support upgrade and downgrade without leaving a second Alembic head.

#### Scenario: Migration creates lifecycle tables

- **WHEN** the migration upgrades from its declared parent
- **THEN** stored response, conversation, and conversation item tables exist with scope and lifecycle columns
- **AND** Alembic reports exactly one head

#### Scenario: Migration is reversible

- **WHEN** the lifecycle migration is downgraded
- **THEN** all three added tables and their indexes are removed

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

### Requirement: Legacy revision reconciliation SHALL safely replay descendant migrations

When a recognized legacy Alembic revision identifier is remapped, descendant schema migrations SHALL tolerate their tables, indexes, or columns already being present. The system SHALL still execute the migration chain so data-normalization migrations are not skipped solely because the physical schema appears current.

#### Scenario: Current schema carries a legacy revision identifier

- **GIVEN** all current tables and indexes are present
- **AND** `alembic_version` contains a recognized legacy identifier
- **WHEN** startup migration runs
- **THEN** already-present schema objects SHALL not cause duplicate-object failures
- **AND** descendant data migrations SHALL still run

#### Scenario: Genuinely old schema carries a legacy revision identifier

- **GIVEN** the physical schema lacks changes introduced after the mapped legacy revision
- **WHEN** startup migration runs
- **THEN** the legacy identifier SHALL be mapped to its equivalent revision
- **AND** descendant migrations SHALL create only missing schema objects and perform their required data work

### Requirement: New request-log failure metadata migration MUST be linear on current heads

The new request-log failure metadata migration MUST be ordered after the merge
revision that joins parallel
`20260426_000000_add_dashboard_relative_availability_settings` and
`20260525_000000_add_usage_raw_window_latest_index` when a deployment upgrades
from current `main`.

#### Scenario: Migration check does not report multiple heads

- **WHEN** Alembic migration check runs on a database that includes current
  upstream `main` history
- **THEN** the check passes without `MultipleHeads` for request-log metadata migration
- **AND** the migration path remains `... -> 20260601_... -> 20260526_...`

### Requirement: Legacy free-account usage-history rows are isolated from monthly semantics

The database migration path SHALL rename legacy free-account `usage_history.window` labels before normalized monthly-only free-account rows are written.

#### Scenario: Free-account legacy primary and secondary rows are renamed
- **WHEN** the migration runs against `usage_history` rows joined to accounts whose current `plan_type` is `free`
- **THEN** rows whose `window` is `primary` are rewritten to `old-primary`
- **AND** rows whose `window` is `secondary` are rewritten to `old-secondary`

#### Scenario: Non-free account rows remain unchanged
- **WHEN** the migration runs against `usage_history` rows joined to accounts whose current `plan_type` is not `free`
- **THEN** existing `primary` and `secondary` labels remain unchanged

### Requirement: Account schema preserves workspace membership metadata

The database schema SHALL store optional workspace and seat metadata for accounts without rewriting existing account primary keys.

#### Scenario: Existing account ids remain stable

- **WHEN** the workspace identity migration is applied
- **THEN** existing `accounts.id` values are not modified
- **AND** nullable `workspace_id`, `workspace_label`, and `seat_type` columns are available

### Requirement: SQLite pre-migration backups use online snapshots

When startup creates a pre-migration backup for a SQLite database, it SHALL use
SQLite's online backup mechanism rather than copying only the main database
file. The backup SHALL include committed rows that are currently resident in WAL
state and SHALL produce a standalone SQLite database file without requiring a
sidecar WAL file.

#### Scenario: WAL-resident rows are present in the backup

- **GIVEN** a file-backed SQLite database has WAL mode enabled
- **AND** committed rows are still present in the source database WAL
- **WHEN** the pre-migration backup is created
- **THEN** those rows are queryable from the backup database
- **AND** the backup passes SQLite integrity checking

