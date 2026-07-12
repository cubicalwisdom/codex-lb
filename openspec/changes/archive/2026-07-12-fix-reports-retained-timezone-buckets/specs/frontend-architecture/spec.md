## ADDED Requirements

### Requirement: Reports SHALL bucket retained history by the requested timezone

The Reports endpoint SHALL assign both live request rows and retained request aggregates to the same requested local-calendar-day boundaries. UTC storage dates MUST NOT change the displayed local date or cause a report request to fail.

#### Scenario: Retained request crosses UTC and local dates

- **GIVEN** a retained request aggregate whose UTC date is earlier than its date in the requested timezone
- **WHEN** the operator loads Reports for that local date
- **THEN** the aggregate SHALL appear under the requested local date
- **AND** the Reports endpoint SHALL return successfully
