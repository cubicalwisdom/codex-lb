# Design: Stable Snapshot Identity and Canonical Usage Decoration

## Backup identity

An app-owned backup is identified by its account-specific snapshot. Registry metadata may describe the snapshot but must not retain transient fields such as root `auth_path`, `active`, `codex`, or `backup`. Identity resolution checks the immutable snapshot first. A root auth path is used only for an actual root row that has no account-specific snapshot.

## Logical bulk actions

Location rows are collapsed by normalized auth identity before `Codex all` or `Backup all` computes its requested keys. The preferred row is the current/root row, while location flags are OR-merged. Messages count logical requested identities, not equivalent physical registry keys.

## Usage decoration

The canonical Accounts query supplies the complete set of account ids to usage history lookups. Filesystem-matched rows and pool-only rows consume the same primary, secondary, and monthly maps, so a canonical account with stored usage always receives its latest windows.

## Compatibility

Existing backup snapshots remain authoritative. Saving a backup registry strips transient fields from all rows, which repairs legacy metadata without rewriting auth payloads.
