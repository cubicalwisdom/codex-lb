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
