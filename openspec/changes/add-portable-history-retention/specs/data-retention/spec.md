## ADDED Requirements

### Requirement: Raw operational history is capped at one day

The system SHALL retain detailed `request_logs`, `usage_history`, and `additional_usage_history` rows for at most 24 hours when history retention is enabled. Account state, credentials, configuration, and current usage SHALL NOT be deleted by history retention.

#### Scenario: A detailed row has expired

- **WHEN** a detailed history row is older than the configured 24-hour cutoff
- **THEN** the retention job deletes it

### Requirement: Usage statistics survive raw log retention

Before deleting an expired normal request log, the system SHALL preserve its request count, token totals, cost, error count, account, API-key, model, and time-bucket statistics in compact roll-up storage. Dashboard, Report, API-key, and account aggregate queries SHALL include both live detailed logs and retained roll-ups.

#### Scenario: A report includes expired activity

- **WHEN** a Dashboard or Report query spans activity older than 24 hours
- **THEN** its aggregate totals include the retained roll-up values
