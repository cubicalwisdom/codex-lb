## MODIFIED Requirements

### Requirement: CodexNeo SHALL display the canonical Codex LB pool

CodexNeo SHALL render the same canonical account identities as the Codex LB Accounts table and SHALL decorate them with current-live, managed-backup, and provider-source state without maintaining an independent routing inventory. Its health diagnostics SHALL report the canonical managed-pool count without treating the live Codex Home registry or locally discovered snapshot count as a mismatch.

#### Scenario: Provider rotation leaves historical pooled identities

- **WHEN** CodexGo replaces the live root `auth.json` while earlier identities remain in the canonical pool
- **THEN** the shared-pool health diagnostic SHALL report the canonical managed-pool count as healthy
- **AND** the live Codex Home registry count SHALL remain a separate informational diagnostic
- **AND** no mismatch status SHALL be derived from comparing those independent inventories

### Requirement: Activity SHALL be a separate 24-hour view

CodexNeo SHALL expose a separate responsive Activity view containing redacted Codex LB, CodexNeo, and provider events. The backend SHALL delete activity older than 24 hours. When the window is maximized, the Activity view SHALL use the available viewport height while keeping the filter controls visible and the event stream internally scrollable.

#### Scenario: Maximized Activity page

- **WHEN** an operator opens Activity in a maximized Codex LB window
- **THEN** the Activity stream SHALL expand to the available viewport height
- **AND** the filters and retention notice SHALL remain visible
- **AND** scrolling the event stream SHALL not require a fixed-height blank page region
