# runtime-portability Specification

## Purpose

Define runtime portability contracts so resilience features degrade safely across supported operating systems.
## Requirements
### Requirement: Memory monitor startup remains portable across supported platforms

The resilience memory monitor MUST NOT prevent application startup on platforms where Unix-specific standard-library modules are unavailable. The system MUST resolve RSS measurement through a platform-appropriate provider when one exists, and MUST fall back to treating memory pressure telemetry as unavailable instead of crashing when no provider is available.

#### Scenario: Windows startup does not import Unix-only resource module

- **WHEN** the application starts on Windows
- **AND** the Python runtime does not provide the Unix-only `resource` module
- **THEN** the memory monitor imports successfully
- **AND** application startup continues without `ModuleNotFoundError`

#### Scenario: RSS provider unavailable does not crash request handling

- **WHEN** the memory monitor cannot resolve RSS from `psutil`, a platform API, or `resource`
- **THEN** RSS lookup returns an unavailable result without raising to callers
- **AND** memory warning and rejection checks do not crash request handling

### Requirement: Codex session provider retag CLI

The `codex-lb` CLI SHALL provide a `codex-sessions retag` subcommand that rewrites local Codex session metadata from one supported model provider tag to another supported model provider tag. The command MUST support `openai` and `codex-lb` provider tags, MUST reject unknown providers, and MUST reject retag requests where `--from` and `--to` are the same provider.

#### Scenario: Dry run previews JSONL and SQLite changes without writing

- **WHEN** an operator runs `codex-lb codex-sessions retag --from openai --to codex-lb --dry-run`
- **THEN** the command scans JSONL session files under the selected Codex home
- **AND** it scans `state_*.sqlite` databases that contain a `threads.model_provider` column
- **AND** it reports the matching files and rows
- **AND** it does not create backups or mutate session metadata

#### Scenario: Confirmed retag updates both storage formats with backup

- **WHEN** an operator runs `codex-lb codex-sessions retag --from openai --to codex-lb --yes`
- **THEN** matched JSONL session provider tags are rewritten to `codex-lb`
- **AND** matched SQLite `threads.model_provider` rows are rewritten to `codex-lb`
- **AND** the command creates a backup under the selected Codex home before rewriting matched metadata
- **AND** the command reports a summary of scanned and updated JSONL files and SQLite rows

#### Scenario: Non-interactive writes require explicit confirmation

- **WHEN** the command is run in a non-interactive shell without `--dry-run` and without `--yes`
- **THEN** it refuses to write session metadata
- **AND** it exits with an error explaining that `--yes` is required

#### Scenario: Codex home resolves across host runtimes

- **WHEN** `--codex-home` is provided
- **THEN** the command uses that path as the Codex data directory
- **AND** otherwise it falls back to `CODEX_HOME`, `/codex-home` in containers, a discoverable WSL Windows profile Codex directory, or `~/.codex`

### Requirement: Portable Codex LB SHALL restart itself as one coordinated process tree

The packaged Electron app SHALL expose an immediate Restart Codex LB action that stops the backend child owned by the current shell, waits for its exit, relaunches the packaged Electron app, and exits the old shell. It SHALL NOT terminate an unowned process merely because that process listens on the configured port. The action SHALL NOT restart Codex Desktop.

#### Scenario: Operator restarts the portable app

- **GIVEN** the Electron shell owns the running portable backend child
- **WHEN** the operator selects Restart Codex LB
- **THEN** the owned backend exits before the replacement shell boots
- **AND** the old Electron process exits
- **AND** the replacement portable app follows the normal health-checked startup path

#### Scenario: Renderer is not hosted by the portable shell

- **GIVEN** CodexNeo is opened in a normal browser without the Electron preload bridge
- **WHEN** the page renders the restart action
- **THEN** the action SHALL be disabled
- **AND** no backend or desktop process SHALL be terminated

#### Scenario: Current shell does not own the healthy backend

- **GIVEN** the Electron shell attached to a healthy backend it did not launch
- **WHEN** the operator requests Restart Codex LB
- **THEN** the request SHALL fail visibly
- **AND** the unowned backend SHALL remain running

