## 1. Regression coverage

- [x] 1.1 Reproduce root rotation with a legacy backup row whose `auth_path` points at root auth; assert all distinct snapshots remain visible once and backed up.
- [x] 1.2 Reproduce a bulk Backup-off operation with a duplicate root/backup identity; assert the response counts logical visible identities.
- [x] 1.3 Reproduce a pool-only Accounts row with stored primary and secondary usage; assert both windows are returned.

## 2. Implementation

- [x] 2.1 Strip transient location metadata from backup registry rows and prefer account-specific snapshots during identity matching.
- [x] 2.2 Deduplicate location rows before bulk operations and bulk-state calculation.
- [x] 2.3 Include all canonical Accounts ids in usage-history queries.

## 3. Verification and delivery

- [x] 3.1 Run focused tests, full CodexNeo backend tests, Ruff, and strict OpenSpec validation.
- [x] 3.2 Update handover and implementation tracking with exact evidence.
- [x] 3.3 Mirror verified Python files into the portable backend, verify hashes and `py_compile`, and leave the running app untouched.
