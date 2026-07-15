## Why

The portable branch selectively backports v1.21 proxy compatibility work while retaining its v1.20.1 package baseline. Operators need the dashboard footer to identify that local parity state without falsely presenting the bundle as the complete upstream v1.21.0 release.

## What Changes

- Display `v1.21parity` as the portable runtime label returned to the dashboard.
- Keep the canonical package version for GitHub release comparison and outbound release-check identity.

## Impact

- Affects only the dashboard runtime-version presentation.
- Does not change package metadata, release tags, or the `X-App-Version` response header.
