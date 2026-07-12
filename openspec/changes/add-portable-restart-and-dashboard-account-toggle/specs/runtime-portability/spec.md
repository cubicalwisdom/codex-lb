## ADDED Requirements

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
