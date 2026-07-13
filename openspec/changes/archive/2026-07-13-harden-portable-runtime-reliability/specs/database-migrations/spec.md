## ADDED Requirements

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
