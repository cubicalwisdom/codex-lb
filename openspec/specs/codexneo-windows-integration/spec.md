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

### Requirement: CodexGO auth replacement backups are bounded by managed retention

When a CodexGO use or refresh action replaces an existing configured Codex Home root `auth.json`, the system MAY create a timestamped recovery file in the `auth.json.codexgo-backup-*` family before replacement. After replacement, the system MUST apply the existing operation-backup policy only to that managed family: retain no more than 10 backups, protect at least 3 backups before age pruning, and prune additional managed backups only when their exact elapsed age is greater than 14 days. The recovery file created for the current replacement MUST remain present regardless of timestamp ordering or clock-skewed/future-dated family members, and its protection MUST NOT increase the 10-file cap. Files outside the exact `auth.json.codexgo-backup-*` family MUST NOT be deleted by this retention path.

#### Scenario: Repeated replacements retain the current bounded recovery set

- **GIVEN** existing root `auth.json` and more than 10 older `auth.json.codexgo-backup-*` files
- **WHEN** CodexGO creates a recovery copy and replaces root auth
- **THEN** the new recovery copy remains present
- **AND** no more than the latest 10 CodexGO-managed recovery files remain

#### Scenario: Age pruning preserves the minimum recovery floor

- **GIVEN** CodexGO-managed backups older than 14 days
- **WHEN** retention runs
- **THEN** the latest 3 managed backups remain protected from age pruning
- **AND** additional managed backups older than 14 days are pruned
- **AND** the managed count never exceeds 10

#### Scenario: Current recovery copy survives future-dated filenames

- **GIVEN** 10 CodexGO-managed backups whose clock-skewed filenames sort after the timestamp of the current operation
- **WHEN** CodexGO creates the current recovery copy and retention runs
- **THEN** the current recovery copy remains present
- **AND** one other managed backup is pruned so no more than 10 remain

#### Scenario: Backup at the exact age boundary is retained

- **GIVEN** a managed backup is outside the latest 3 protected files
- **WHEN** its exact elapsed age is equal to 14 days
- **THEN** age pruning does not remove it

#### Scenario: Backup beyond the exact age boundary is eligible

- **GIVEN** a managed backup is outside the latest 3 protected files
- **WHEN** its exact elapsed age is greater than 14 days
- **THEN** it is eligible for age pruning without waiting for a fifteenth calendar day

#### Scenario: Unrelated backup families are isolated

- **GIVEN** files beside root auth that do not match `auth.json.codexgo-backup-*`
- **WHEN** CodexGO backup retention runs
- **THEN** those unrelated files remain unchanged

### Requirement: CodexGO root provenance is transient and collision-safe

Before a CodexGO use or refresh action creates a recovery copy or modifies configured Codex Home root `auth.json` or provenance state, the system MUST derive a stable normalized logical identity from the validated provider auth. If no stable identity can be derived, the action MUST fail without creating a backup and without modifying root auth or provenance state. After a successful write, the system MUST track that identity as active transient-root provenance using a token-free fingerprint. The state MUST NOT contain raw auth JSON, tokens, buyer tokens, email, account id, workspace labels, or other recoverable credential/identity contents. Same-identity token renewal MUST NOT queue retirement.

When a later successful CodexGO action writes a different logical identity, the system MUST queue the prior active tracked fingerprint for reconciliation and make the new fingerprint active. The queued fingerprint MUST come from prior CodexGO state, not from any untracked auth that happened to occupy root immediately before replacement. A manual or external root identity MUST NOT be claimed or removed as CodexGO provenance.

Reconciliation MUST inspect non-root managed Codex Home and app-owned Backup snapshots before removing a queued identity from encrypted Accounts. If any such managed source represents the queued identity, the system MUST preserve every managed source and MUST preserve the matching Accounts row. If no non-root managed source represents it, the system MUST remove matching Accounts rows without deleting their request, usage, or audit history. This reconciliation MUST NOT delete managed source files or root `auth.json`. A failed retirement MUST leave the queued fingerprint pending, and a later account sync MUST retry it; the fingerprint MUST be cleared only after reconciliation completes successfully.

Accounts-to-Codex-Home reverse sync MUST NOT create a managed snapshot for the active tracked transient fingerprint. The production CodexGO background scheduler MUST construct its service with account reconciliation so scheduled root replacement performs this cleanup immediately.

#### Scenario: Untrackable provider auth is rejected before mutation

- **GIVEN** CodexGO returns schema-valid auth with token material but no stable account or workspace identity
- **WHEN** CodexNeo validates the replacement
- **THEN** the action fails with a stable identity-missing error
- **AND** existing root `auth.json` remains unchanged
- **AND** no recovery backup or provenance-state file is created or modified

#### Scenario: Root-only tracked identity is retired after rotation

- **GIVEN** CodexGO previously wrote identity A
- **AND** A exists in encrypted Accounts with no matching non-root managed Codex Home or app Backup source
- **WHEN** CodexGO writes different identity B
- **THEN** A's Accounts row is removed
- **AND** A's request, usage, and audit history remains detached
- **AND** root `auth.json` remains identity B

#### Scenario: Same-identity managed collision is preserved

- **GIVEN** CodexGO previously wrote identity A
- **AND** a pre-existing or user-owned non-root managed Codex Home or app Backup snapshot also represents A
- **WHEN** CodexGO later writes different identity B
- **THEN** every matching managed source remains unchanged
- **AND** A's encrypted Accounts row remains available
- **AND** root `auth.json` remains identity B

#### Scenario: Manual root switch does not replace tracked provenance

- **GIVEN** CodexGO previously tracked identity A
- **AND** a manual or external action changes root auth to untracked identity M
- **WHEN** CodexGO later writes different identity B
- **THEN** A is still queued from tracked CodexGO state and reconciled under the managed-collision rule
- **AND** M is not queued or removed as CodexGO provenance
- **AND** root auth remains B

#### Scenario: Missing-email identity uses database normalization

- **GIVEN** a tracked root-only CodexGO identity has an account id but no email
- **WHEN** CodexGO rotates to a different identity
- **THEN** reconciliation matches the same normalized encrypted Accounts identity
- **AND** the stale root-only Accounts row is removed

#### Scenario: Reverse sync does not promote active transient root

- **GIVEN** encrypted Accounts contains the active tracked CodexGO root identity
- **AND** no matching managed Codex Home snapshot exists
- **WHEN** Accounts-to-Codex-Home reverse sync runs
- **THEN** it does not create a managed snapshot for that active fingerprint

#### Scenario: Scheduled refresh reconciles immediately

- **GIVEN** CodexGO automatic refresh is enabled
- **WHEN** the production scheduler performs a CodexGO root replacement
- **THEN** its service runs account reconciliation for that replacement
- **AND** a queued root-only prior identity does not wait for an unrelated later sync

#### Scenario: Failed retirement remains retryable

- **GIVEN** a queued root-only prior identity has no matching non-root managed source
- **WHEN** encrypted Accounts deletion fails before reconciliation completes
- **THEN** the queued fingerprint remains in app-owned state
- **AND** a later account sync retries retirement
- **AND** the fingerprint is cleared after the retry completes successfully
