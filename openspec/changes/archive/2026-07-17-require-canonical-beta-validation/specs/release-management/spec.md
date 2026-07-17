## ADDED Requirements

### Requirement: Canonical beta PRs with unchanged metadata still require validation

Before merge, the beta release guard SHALL require release-candidate validation
evidence for canonical `release/beta-X.Y.Z-beta.N` pull requests whose checked-
out tree already contains the matching beta version, even when the release-
managed version files are unchanged relative to the base branch.

#### Scenario: canonical beta PR with unchanged metadata still requires validation

- **GIVEN** `main` already contains release-managed files set to `1.20.0-beta.3`
- **AND** a pull request from `release/beta-1.20.0-beta.3` targets `main`
- **WHEN** the beta release guard evaluates the pull request before merge
- **THEN** it requires release-candidate validation evidence for the pull request head SHA
- **AND** it fails while that evidence is missing, even though the release-managed version files are unchanged relative to `main`
