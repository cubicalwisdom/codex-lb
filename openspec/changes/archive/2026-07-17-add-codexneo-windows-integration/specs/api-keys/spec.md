# API Keys Delta

## ADDED Requirements

### Requirement: API key edit selectors commit exact typed matches

The Settings API-key edit dialog SHALL persist assigned account, allowed model, and enforced model changes made by an admin.

#### Scenario: Exact searched account is saved

- **WHEN** an admin opens Edit API key, types an exact account email, display name, or account id into the Assigned accounts search box, and closes the selector or presses Enter
- **THEN** the selector SHALL commit that exact account before the dialog is saved
- **AND** saving the dialog SHALL persist the selected account restriction instead of reverting to all accounts

#### Scenario: Exact searched model is saved

- **WHEN** an admin opens Edit API key, types an exact model id or model name into the Allowed models search box, and closes the selector or presses Enter
- **THEN** the selector SHALL commit that exact model before the dialog is saved
- **AND** saving the dialog SHALL persist the selected model restriction instead of reverting to all models

#### Scenario: Enforced model is saved

- **WHEN** an admin edits the Enforced model field and saves the dialog
- **THEN** the submitted API-key update SHALL include the enforced model value
- **AND** the saved key SHALL not silently discard that value because a selector popover closed
