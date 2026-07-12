## ADDED Requirements

### Requirement: CodexNeo SHALL expose compact portable operator actions

CodexNeo SHALL place Restart Codex LB in the page header and SHALL present Use auth and Refresh auth as equal compact actions. Restart Codex LB SHALL invoke the Electron restart bridge immediately without a browser confirmation dialog.

#### Scenario: Portable operator opens CodexNeo Accounts

- **GIVEN** CodexNeo is hosted by the portable Electron shell
- **WHEN** the Accounts page renders
- **THEN** Restart Codex LB SHALL be visible in the page header
- **AND** Use auth and Refresh auth SHALL have equivalent action dimensions

#### Scenario: Operator selects Restart Codex LB

- **WHEN** the enabled Restart Codex LB action is selected
- **THEN** the page SHALL invoke the Electron restart bridge immediately
- **AND** SHALL NOT show a confirmation dialog
