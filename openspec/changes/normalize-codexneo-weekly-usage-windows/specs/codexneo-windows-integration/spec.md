## ADDED Requirements

### Requirement: CodexNeo SHALL classify quota windows by duration

CodexNeo SHALL classify current quota usage by the actual window duration rather than the legacy persistence slot name.

#### Scenario: Weekly-only usage is stored in the primary slot

- **GIVEN** the latest `primary` usage record has the configured weekly duration
- **AND** no genuine short-window record is available
- **WHEN** CodexNeo returns the shared account pool
- **THEN** it SHALL return no 5h value
- **AND** SHALL return that record as the Weekly value

#### Scenario: A newer weekly primary record coexists with stale secondary history

- **GIVEN** `primary` and `secondary` both contain weekly-duration records
- **AND** the `primary` record is the current effective weekly record
- **WHEN** CodexNeo returns usage
- **THEN** it SHALL show the current record under Weekly
- **AND** SHALL NOT show the stale secondary record

#### Scenario: Separate short and weekly windows are available

- **GIVEN** a genuine short-window primary record and a weekly secondary record
- **WHEN** CodexNeo returns usage
- **THEN** it SHALL show each record in its matching 5h or Weekly column
