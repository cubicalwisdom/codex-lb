## ADDED Requirements

### Requirement: Responses lifecycle resources have a reversible schema

The database SHALL persist API-key-scoped stored responses, conversations, and ordered conversation items through an Alembic revision on the current single-head migration graph. The schema MUST cascade conversation deletion to its items, index resource scope lookups, and support upgrade and downgrade without leaving a second Alembic head.

#### Scenario: Migration creates lifecycle tables

- **WHEN** the migration upgrades from its declared parent
- **THEN** stored response, conversation, and conversation item tables exist with scope and lifecycle columns
- **AND** Alembic reports exactly one head

#### Scenario: Migration is reversible

- **WHEN** the lifecycle migration is downgraded
- **THEN** all three added tables and their indexes are removed
