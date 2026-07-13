## ADDED Requirements

### Requirement: CodexNeo command summaries SHALL redact credentials

All provider, import/export, account-action, and filesystem-sync command or exception summaries exposed through the API or activity UI SHALL use the shared structured-log credential redactor before truncation.

#### Scenario: Command output contains a credential

- **WHEN** output contains a JSON, delimited, whitespace-separated, bearer, authorization, API-key, or buyer-token credential
- **THEN** the complete credential value SHALL be replaced with `[REDACTED]`
- **AND** surrounding non-sensitive diagnostic text SHALL remain visible

### Requirement: Windows SQLite maintenance SHALL release handles before replacement

Portable backup, migration, archive, and Codex session maintenance SHALL explicitly close SQLite connections before deleting, rotating, or replacing database files. Transient Windows sharing violations MAY be retried for a bounded interval.

#### Scenario: SQLite backup is rotated on Windows

- **WHEN** a new backup has completed and an old backup must be removed
- **THEN** no connection owned by the operation SHALL retain a handle to either file
- **AND** a transient sharing violation SHALL be retried without an unbounded wait

### Requirement: Electron privileged actions SHALL be restricted to the local app origin

The Electron shell SHALL allow in-window navigation and privileged preload IPC only from the configured Codex LB local origin. External opening SHALL accept only HTTP and HTTPS URLs.

#### Scenario: Loaded content navigates away from Codex LB

- **WHEN** navigation targets a different origin or an unsafe URL scheme
- **THEN** in-window navigation SHALL be denied
- **AND** privileged restart or startup-setting IPC SHALL reject a non-local sender

### Requirement: Bootstrap credentials SHALL NOT enter persistent portable logs

When the backend is launched by the Electron portable shell, auto-generated dashboard bootstrap credentials SHALL not be written into persistent redirected stdout or stderr logs.

#### Scenario: First-run token is generated in portable mode

- **WHEN** the server creates an automatic dashboard bootstrap token
- **THEN** persistent server logs SHALL contain only a credential-available notice
- **AND** SHALL NOT contain the token value
