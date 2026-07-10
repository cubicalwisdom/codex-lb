## ADDED Requirements

### Requirement: Reasoning controls expose model-supported max and ultra levels

Dashboard model data MUST expose supported and default reasoning efforts. API-key create/edit controls MUST offer `max` and `ultra` when supported and MUST validate those values through the shared frontend schema.

#### Scenario: Operator selects an extended GPT-5.6 effort

- **GIVEN** the model catalog advertises `max` or `ultra`
- **WHEN** the operator configures an API key in the create or edit dialog
- **THEN** the advertised effort appears as a selectable option
- **AND** the submitted schema retains that exact configured value
