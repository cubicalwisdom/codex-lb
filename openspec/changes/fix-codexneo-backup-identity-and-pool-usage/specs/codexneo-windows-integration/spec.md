## ADDED Requirements

### Requirement: Managed backup identity SHALL be stable across root rotation

The system SHALL identify an app-owned backup from its account-specific snapshot and SHALL NOT allow a mutable root auth path stored in registry metadata to change that identity.

#### Scenario: Root auth changes after an earlier account was backed up

- **WHEN** account A is backed up from root auth and root auth later changes to account B
- **THEN** account A SHALL remain visible exactly once with Backup enabled
- **AND** account B SHALL remain a separate logical identity

### Requirement: Bulk location actions SHALL count logical accounts

Bulk Codex and Backup actions SHALL operate on the same deduplicated logical identities rendered by the CodexNeo table.

#### Scenario: Root and Backup contain equivalent physical rows

- **WHEN** the active root identity also has a managed backup row
- **THEN** a bulk location response SHALL count that identity once
- **AND** SHALL NOT report a hidden physical-row count

### Requirement: Canonical pool usage SHALL appear without filesystem decoration

CodexNeo SHALL load usage history for every canonical Codex LB Accounts identity, including an identity with no current Codex Home or Backup location.

#### Scenario: Pool-only account has stored quota history

- **WHEN** a canonical pool-only account has latest primary and secondary usage records
- **THEN** its 5-hour and weekly values SHALL appear in the CodexNeo table
- **AND** its latest usage timestamp SHALL be populated
