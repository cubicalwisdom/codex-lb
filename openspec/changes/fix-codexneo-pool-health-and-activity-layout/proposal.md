## Why

The CodexNeo health card compares a legacy locally-discovered snapshot subset with the canonical Codex LB account pool. CodexGo intentionally rotates the live `auth.json`, so those inventories are not required to match and the comparison falsely reports a mismatch. The separate Activity page also constrains its log to a fixed height, wasting available maximized-window space.

## What Changes

- Report the canonical managed-pool count as the health diagnostic; keep live Codex Home and managed backups as independent states.
- Remove the invalid cross-source mismatch status.
- Make the separate Activity page fill the available viewport with a sticky filter area and an internally scrollable activity stream.

## Impact

The CodexNeo health endpoint and the Activity page layout change. Account identities, backup records, usage statistics, and provider-delivered live auth files are not changed.
