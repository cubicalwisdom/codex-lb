# codexneo-windows-integration Specification

## Purpose
TBD - created by archiving change harden-codex-desktop-api-parity-pass. Update Purpose after archive.
## Requirements
### Requirement: Explicit Codex Desktop restart owns the packaged process tree

When an admin invokes the explicit Restart Codex or Switch & Restart action on Windows, the system MUST close the visible `ChatGPT.exe` shell belonging to the installed `OpenAI.Codex` package before relaunching the package. If graceful close does not terminate the package, the system MAY force-stop remaining processes only when they belong to the same WindowsApps package. The restart action MUST NOT stop an unrelated `codex.exe` CLI or agent process based on process name alone.

#### Scenario: Packaged shell has a child app-server

- **GIVEN** Codex Desktop is running as a packaged `ChatGPT.exe` shell with a child `codex.exe app-server`
- **WHEN** the explicit restart action runs
- **THEN** the shell receives the graceful close request
- **AND** any forced cleanup is limited to remaining `OpenAI.Codex` package processes
- **AND** the package launch is requested only after cleanup

#### Scenario: Unrelated Codex CLI is running

- **GIVEN** a bare `codex.exe` process is running outside the `OpenAI.Codex` WindowsApps package
- **WHEN** the explicit restart action runs
- **THEN** that process is not selected or stopped by name alone

### Requirement: CodexNeo SHALL display the canonical Codex LB pool

CodexNeo SHALL render the same canonical account identities as the Codex LB Accounts table and SHALL decorate them with current-live, managed-backup, and provider-source state without maintaining an independent routing inventory. Its health diagnostics SHALL report the canonical managed-pool count without treating the live Codex Home registry or locally discovered snapshot count as a mismatch.

#### Scenario: Provider replacement preserves earlier pool accounts

- **WHEN** CodexGO desktop delivery or CodexGO API delivery replaces root `auth.json` with a different valid identity
- **THEN** the system SHALL upsert the new identity into the canonical pool and managed snapshot store
- **AND** SHALL retain earlier pool identities and snapshots unless a separate explicit deletion policy removes them

#### Scenario: Provider rotation leaves historical pooled identities

- **WHEN** CodexGo replaces the live root `auth.json` while earlier identities remain in the canonical pool
- **THEN** the shared-pool health diagnostic SHALL report the canonical managed-pool count as healthy
- **AND** the live Codex Home registry count SHALL remain a separate informational diagnostic
- **AND** no mismatch status SHALL be derived from comparing those independent inventories

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

### Requirement: CodexNeo SHALL classify quota windows by duration

CodexNeo SHALL classify current quota usage by the actual window duration rather than the legacy persistence slot name and SHALL NOT invent a missing short-window value.

#### Scenario: Weekly-only usage is stored in the primary slot

- **GIVEN** the latest `primary` usage record has the configured weekly duration
- **AND** no genuine short-window record is available
- **WHEN** CodexNeo returns the shared account pool
- **THEN** it SHALL return no 5-hour value
- **AND** SHALL return that record as the Weekly value

#### Scenario: Current and stale weekly records coexist

- **GIVEN** the legacy primary and secondary slots both contain weekly-duration records
- **WHEN** CodexNeo returns usage
- **THEN** it SHALL select the current effective weekly record using the shared usage-window policy
- **AND** SHALL NOT display the stale record

#### Scenario: Separate short and weekly windows are available

- **GIVEN** a genuine short-window primary record and a weekly secondary record
- **WHEN** CodexNeo returns usage
- **THEN** it SHALL show each record in its matching 5-hour or Weekly column

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

CodexNeo SHALL expose a separate responsive Activity view containing redacted Codex LB, CodexNeo, and provider events. The backend SHALL delete activity older than 24 hours. When the window is maximized, the Activity view SHALL use the available viewport height while keeping the filter controls visible and the event stream internally scrollable.

#### Scenario: Old activity is pruned while page is closed

- **WHEN** activity reaches 24 hours of age
- **THEN** backend retention SHALL remove it without a browser request
- **AND** SHALL not remove usage statistics or account pool records

#### Scenario: Maximized Activity page

- **WHEN** an operator opens Activity in a maximized Codex LB window
- **THEN** the Activity stream SHALL expand to the available viewport height
- **AND** the filters and retention notice SHALL remain visible
- **AND** scrolling the event stream SHALL not require a fixed-height blank page region
