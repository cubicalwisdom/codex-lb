## ADDED Requirements

### Requirement: CodexNeo SHALL display the canonical Codex LB pool

CodexNeo SHALL render the same canonical account identities as the Codex LB Accounts table and SHALL decorate them with current-live, managed-backup, and provider-source state without maintaining an independent routing inventory.

#### Scenario: Provider replacement preserves earlier pool accounts

- **WHEN** CodexGO desktop delivery or CodexGO API delivery replaces root `auth.json` with a different valid identity
- **THEN** the system SHALL upsert the new identity into the canonical pool and managed snapshot store
- **AND** SHALL retain earlier pool identities and snapshots unless a separate explicit deletion policy removes them

### Requirement: CodexNeo SHALL ingest provider auth independently of the browser page

The backend SHALL reconcile a changed valid root `auth.json` while the CodexNeo page is closed.

#### Scenario: Desktop provider replaces root auth while page is closed

- **WHEN** the configured Codex Home root auth file changes to a valid new identity
- **THEN** backend reconciliation SHALL ingest that identity into the canonical pool and managed snapshot store
- **AND** the next CodexNeo Accounts query SHALL show the identity once

### Requirement: Account deletion SHALL remove selected managed credentials everywhere

Delete selected SHALL be confirmation-gated and SHALL remove selected routing-pool credentials, app-owned backup entries, and app-managed Codex Home entries without deleting aggregate usage statistics.

#### Scenario: Admin deletes selected non-live account

- **WHEN** an admin confirms Delete selected for a pooled non-live identity
- **THEN** its Accounts row, managed backup snapshot/registry entry, and app-managed Codex Home snapshot/registry entry SHALL be removed
- **AND** aggregate usage statistics SHALL remain available

### Requirement: Activity SHALL be a separate 24-hour view

CodexNeo SHALL expose a separate scrollable Activity view containing redacted Codex LB, CodexNeo, and provider events. The backend SHALL delete activity older than 24 hours.

#### Scenario: Old activity is pruned while page is closed

- **WHEN** activity reaches 24 hours of age
- **THEN** backend retention SHALL remove it without a browser request
- **AND** SHALL not remove usage statistics or account pool records

