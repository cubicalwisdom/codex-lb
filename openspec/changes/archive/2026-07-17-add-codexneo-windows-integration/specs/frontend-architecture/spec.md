# Frontend Architecture Delta

## ADDED Requirements

### Requirement: CodexNeo dashboard route

The dashboard SHALL expose a CodexNeo route in the primary navigation near APIs and Settings.

#### Scenario: Admin opens CodexNeo tab

- **WHEN** an admin opens the CodexNeo tab
- **THEN** the page SHALL show controls for Codex API base URL, Auth->API Test, Auth->API Set, Auth->API Revert, CodexGO auto-refresh, refresh interval minutes, buyer token, provider URL, Use auth, and Refresh auth

#### Scenario: Guest opens CodexNeo tab

- **WHEN** a read-only guest opens the CodexNeo tab
- **THEN** settings MAY be visible except plaintext secrets
- **AND** mutating controls SHALL be disabled

#### Scenario: Buyer token is saved

- **WHEN** a buyer token is already saved
- **THEN** the UI SHALL indicate that a token exists without rendering the token value

#### Scenario: Admin views activity log

- **WHEN** an admin opens the CodexNeo tab
- **THEN** the page SHALL show OpenAI log and Management log toggles
- **AND** the page SHALL show an Activity log panel with a Clear button

#### Scenario: Admin views Codex Home accounts

- **WHEN** an admin opens the CodexNeo tab
- **THEN** the page SHALL show a Codex Home account table populated from the safe account discovery API
- **AND** the table SHALL NOT render auth secrets
