## MODIFIED Requirements

### Requirement: Runtime version status checks latest GitHub release

The service SHALL expose a dashboard-auth protected runtime version status API that reports a running application display label, the latest known GitHub release version when available, whether an update is available, and the time of the latest lookup attempt. The lookup MUST be cached in-process to avoid per-request GitHub traffic, and lookup failures MUST NOT cause the API to fail. When a portable build uses a display label that differs from its canonical package version, GitHub-release comparison and the release-check user agent MUST continue to use the canonical package version; only the reported dashboard `currentVersion` value MAY use the display label.

#### Scenario: Latest release is newer than current version

- **WHEN** the running version is `1.19.0`
- **AND** the GitHub latest release tag is `v1.20.0`
- **THEN** the runtime version status reports `currentVersion: "1.19.0"`, `latestVersion: "1.20.0"`, and `updateAvailable: true`

#### Scenario: Latest release is newer than canonical package version

- **GIVEN** the running canonical package version is `1.20.1`
- **AND** the portable display label is `v1.21parity`
- **WHEN** the GitHub latest release tag is `v1.21.0`
- **THEN** the runtime version status reports `currentVersion: "v1.21parity"`, `latestVersion: "1.21.0"`, and `updateAvailable: true`

#### Scenario: GitHub lookup fails

- **WHEN** the GitHub latest release lookup fails
- **THEN** the runtime version status API still returns the current version
- **AND** `updateAvailable` is `false`

#### Scenario: Version lookup is unavailable for a parity display label

- **GIVEN** the portable display label is `v1.21parity`
- **WHEN** the GitHub latest release lookup fails
- **THEN** the runtime version status API still returns `currentVersion: "v1.21parity"`
