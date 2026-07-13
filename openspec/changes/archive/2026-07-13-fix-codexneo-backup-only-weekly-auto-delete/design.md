# Design

## Candidate resolution

Eligibility remains strict: the persisted setting must be enabled, the latest weekly sample must be the real 10,080-minute window with exactly 0% remaining, and the account must be quota-exceeded under the shared status rules. The candidate lookup will use the existing all-managed-snapshot discovery helper rather than live Codex Home snapshots alone.

That helper discovers both app-managed Codex Home records and Backup records, while the existing location service deletes equivalent live and Backup keys together by parsed auth identity. This preserves safety for an account that has both locations and permits cleanup for an account that is Backup-only.

## Example

If account A has `Weekly = 0%`, `Avail = Backup`, and its snapshot exists only in `portable-data/account-backups`, the enabled rule removes A's encrypted pool credential and its managed Backup registry/snapshot. Its aggregate usage history remains retained.
