# Tasks

## 1. Contract and backup-retention evidence

- [x] 1.1 Record the unbounded backup and coupled transient-root paths with the managed-collision safety boundary.
- [x] 1.2 Prove more than 10 CodexGO backups are pruned to the newest 10 and the current replacement backup remains.
- [x] 1.3 Prove age pruning preserves the newest 3 managed backups before applying the 14-day limit.
- [x] 1.4 Prove unrelated auth backup families remain byte-for-byte unchanged.
- [x] 1.5 Prove provider auth without stable account identity is rejected before root, backup, or provenance-state mutation.
- [x] 1.6 Prove the just-created backup remains protected when future-dated filenames sort ahead of it and the total remains at most 10.
- [x] 1.7 Prove age pruning uses exact elapsed time and removes an eligible backup older than 14 days but less than 15 days.

## 2. Backup-retention implementation

- [x] 2.1 Parameterize operation-backup pruning by exact family label while preserving config-backup behavior.
- [x] 2.2 Apply family-scoped pruning after validated CodexGO root replacement.
- [x] 2.3 Preserve atomic writing, auth validation, current-backup reporting, and secret handling.
- [x] 2.4 Require a stable identity fingerprint before entering any CodexGO root/backup/state write path.
- [x] 2.5 Pass the current backup path as an explicit protected retention member without increasing the 10-file cap.
- [x] 2.6 Compare backup age as an exact duration greater than 14 days.

## 3. Transient-root regression evidence

- [x] 3.1 Prove a root-only tracked identity A is removed from encrypted Accounts after CodexGO writes B, while B remains root and A's usage history is detached.
- [x] 3.2 Prove reverse sync does not create a managed snapshot for the active tracked transient identity and the state file contains only a token-free fingerprint.
- [x] 3.3 Prove pre-existing managed Codex Home and app-owned Backup snapshots with A's identity remain untouched and preserve A's Accounts row after rotation.
- [x] 3.4 Prove an intervening manual root identity M is preserved while previously tracked CodexGO identity A is still reconciled when CodexGO writes B.
- [x] 3.5 Prove a root-only tracked identity without email is retired using the same normalization as the encrypted Accounts row.
- [x] 3.6 Prove the production background scheduler injects account sync for immediate post-refresh reconciliation.
- [x] 3.7 Prove same-identity token renewal does not queue retirement.
- [x] 3.8 Prove a failed Accounts retirement keeps the queued fingerprint and succeeds on a later sync retry.

## 4. Transient-root implementation

- [x] 4.1 Persist active/pending CodexGO provenance as normalized token-free SHA-256 fingerprints.
- [x] 4.2 Queue the prior tracked fingerprint when a later CodexGO identity differs, independently of an intervening untracked root identity.
- [x] 4.3 Preserve every matching non-root managed Codex Home/app Backup source and its encrypted Accounts row.
- [x] 4.4 Remove only root-only matching Accounts rows and preserve their request/usage/audit history as detached records.
- [x] 4.5 Exclude the active tracked transient identity from Accounts-to-Codex-Home reverse sync.
- [x] 4.6 Serialize root/state replacement and account reconciliation with one process-local guard.
- [x] 4.7 Construct the background CodexGO scheduler with an account-sync-enabled service.
- [x] 4.8 Clear queued provenance only after successful reconciliation so failures remain retryable.

## 5. Verification and portable activation

- [x] 5.1 Run the focused/broad CodexNeo backend verification covering the current implementation and regressions.
- [x] 5.2 Run scoped Ruff/ty, strict OpenSpec validation, and `git diff --check` for the completed change.
- [x] 5.3 Mirror `service.py`, `sync.py`, and `scheduler.py` into both active portable Python roots; verify 6/6 source/runtime SHA matches and embedded/venv `py_compile` success.
- [x] 5.4 Observe the next natural Electron-managed portable backend reload, then verify readiness and a secret-safe live bounded-backup/current-account smoke without an agent-initiated restart. Backend PID `51836` was healthy/ready with drain off; the scheduled `01:39` refresh retained the current recovery backup at the 10-file cap, created token-free active provenance with no pending retired identity, and left Accounts/snapshots aligned at `29/29` without a new snapshot.
- [x] 5.5 Update `CODEXNEO_IMPLEMENTATION_LIST.md` and `HANDOVER_CODEXNEO_INTEGRATION.md` with CN-063/CN-064/CN-065 root cause, safe provenance behavior, activation limits, and verification evidence.
