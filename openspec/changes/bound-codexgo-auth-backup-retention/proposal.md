# Bound CodexGO auth backup and transient-root retention

## Why

Each CodexGO use or refresh operation can replace configured Codex Home root `auth.json` and create a timestamped recovery copy first. Those `auth.json.codexgo-backup-*` files were never pruned, so a frequently refreshed portable backend could accumulate hundreds or thousands of stale snapshots.

There is a coupled account path. CodexNeo imports root auth into encrypted Accounts, and reverse sync can promote that transient identity into a managed snapshot. After CodexGO rotates to another identity, a root-only prior identity can remain as a stale Accounts row. Cleanup must be conservative, however: a token-free fingerprint proves that CodexGO wrote the transient root identity, but it does not prove ownership of a pre-existing or user-managed Codex Home/app Backup snapshot with the same identity.

## What Changes

- Apply the existing operation-backup policy only to `auth.json.codexgo-backup-*`: latest 10 by count, latest 3 protected before 14-day age pruning, with the current replacement backup preserved.
- Protect the current replacement backup explicitly even when future-dated/clock-skewed filenames sort ahead of it, while keeping the family at no more than 10 files.
- Compare exact elapsed backup age and prune only when it is greater than 14 full days rather than flooring to integer calendar days.
- Track the active identity written by successful CodexGO root replacement using a normalized token-free fingerprint.
- Reject a provider response that has no stable trackable identity before creating a backup or modifying root auth/provenance state.
- When CodexGO rotates from tracked identity A to identity B, queue A for reconciliation even if an intervening manual switch changed root to untracked identity M; never claim M as CodexGO-owned.
- Retire A's encrypted Accounts row only when no non-root managed Codex Home or app-owned Backup snapshot represents A.
- Preserve every pre-existing/user-owned managed source and preserve its matching Accounts row when an identity collision exists.
- Retain queued provenance after a failed retirement so a later account sync retries instead of abandoning the stale row.
- Keep reverse sync from promoting the active transient CodexGO root identity into managed snapshots.
- Wire the background CodexGO scheduler with account sync so scheduled replacement immediately performs the same reconciliation as interactive replacement.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `codexneo-windows-integration`: Bounds CodexGO root backups and defines collision-safe transient-root provenance and reconciliation.

## Impact

- **Code**: `app/modules/codexneo/service.py`, `app/modules/codexneo/sync.py`, and `app/modules/codexneo/scheduler.py`.
- **Tests**: CodexNeo service, discovery-sync, and scheduler coverage for retention, transient provenance, managed-source collisions, manual switches, identity normalization, reverse-sync exclusion, and immediate scheduled reconciliation.
- **Portable runtime**: verified affected source files must be mirrored into both active portable Python roots before restart.
- **API/data model**: no endpoint, response-schema, settings-schema, or database migration changes.
