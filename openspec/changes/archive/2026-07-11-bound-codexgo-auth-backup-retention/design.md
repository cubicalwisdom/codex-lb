# Design

## Context and root cause

CodexGO use and refresh actions replace configured Codex Home root `auth.json`. If root auth already exists, CodexNeo first creates `auth.json.codexgo-backup-<timestamp>`. The config replacement path already bounds its timestamped operation backups, but the CodexGO path did not invoke that retention behavior.

CodexNeo also imports root auth into encrypted Accounts. Without provenance state, a later CodexGO rotation cannot distinguish the prior transient root identity from ordinary account inventory. Reverse sync can additionally create a managed Codex Home snapshot for that transient identity, making it durable after root rotates.

The key safety constraint is identity collision. A CodexGO-written root identity can equal an independently pre-existing managed Codex Home or app-owned Backup snapshot. A fingerprint proves transient root provenance only; it cannot prove that every same-identity source is owned by CodexGO.

## Goals

- Reuse the existing 10/3/14 operation-backup policy for the exact CodexGO backup family.
- Preserve the just-created recovery copy explicitly under clock skew and evaluate the 14-day limit using exact elapsed duration.
- Persist token-free provenance for the active logical identity written by CodexGO.
- Refuse untrackable provider auth before any root, backup, or state mutation.
- Remove a prior transient root Accounts row when it has no non-root managed source.
- Preserve all user-owned/pre-existing managed sources and their DB account on identity collision.
- Preserve an intervening manual root identity while still reconciling the earlier tracked CodexGO identity when CodexGO rotates again.
- Prevent reverse sync from promoting the active transient CodexGO identity.
- Make scheduled refresh run immediate account reconciliation.

## Non-goals

- Deleting any managed Codex Home or app-owned Backup registry row or snapshot through transient-root reconciliation.
- Treating a same-identity managed snapshot as CodexGO-owned merely because its identity matches the tracked fingerprint.
- Inferring CodexGO provenance for identities that predate the state file.
- Bulk-deleting historical stale accounts whose provenance cannot be proved.
- Deleting request, usage, or audit history when a root-only Accounts row is retired.
- Changing refresh scheduling, auth validation, provider calls, retention values, or public APIs.

## Decisions

### 1. Parameterize the existing operation-backup pruner by family label

The config and CodexGO paths share ordering and retention rules, while labels define separate ownership boundaries. The helper accepts a label and matches exactly `<target>.<label>-*`. A global `auth.json.*backup-*` cleanup is rejected because it could delete recovery files owned by users or other tools.

The backup path created for the current operation is passed to retention as an explicit protected member and placed first. Remaining files are ordered newest first by timestamped name. This prevents a future-dated or clock-skewed filename from displacing the recovery copy for the write that just occurred. The protected file still consumes one of the 10 slots, so protection never expands the total cap.

Files beyond the latest 10 are count-pruned. Age pruning starts only after the latest 3, so those 3 remain recoverable even when older than 14 days. Age is compared as an exact duration: exactly 14 elapsed days is retained, while more than 14 days is eligible. Future-dated files have negative elapsed age and therefore are not age-pruned, but they remain subject to the count cap.

### 2. Validate stable identity before filesystem mutation

Schema-valid provider auth can still lack stable account/workspace identity claims. Such a response cannot be tracked safely and therefore cannot participate in collision-safe retirement. CodexNeo derives the identity fingerprint before entering the root-state guard and before creating a recovery copy, replacing root auth, or writing provenance state. If no stable fingerprint can be derived, the action fails with a stable dashboard error and leaves all three surfaces unchanged.

### 3. Track normalized logical identity, not token bytes

After a successful CodexGO root write, app-owned state records a SHA-256 fingerprint derived from normalized account/email/workspace identity fields. It does not hash the whole auth file, so token renewal for the same logical identity does not create a rotation. The state contains only the active fingerprint and fingerprints awaiting reconciliation; it stores no raw auth, token, email, account id, or workspace label.

Missing-email identities use the same normalized identity shape as encrypted Accounts matching. This prevents a root-only no-email account from surviving because its file and DB representations normalize differently.

### 4. Track provenance across an intervening manual switch

State identifies the last successful CodexGO-written identity A. When a later successful CodexGO response writes different identity B, A is queued from state, not from the bytes that happened to be in root immediately before replacement. Therefore an intervening manual identity M is never queued, while A remains eligible for reconciliation. B becomes the new active fingerprint.

Root replacement and account sync share one process-local asynchronous guard so a concurrent sync cannot observe a half-written root/state transition.

### 5. Managed-source presence is a preservation signal

Reconciliation scans non-root managed Codex Home and app-owned Backup snapshots and fingerprints their logical identities. If any managed source matches queued A, all managed sources remain untouched and the matching encrypted Accounts row is preserved. The fingerprint proves CodexGO root provenance but cannot disambiguate ownership of a same-identity managed source, so preservation is the only safe action.

If no non-root managed source matches A, matching encrypted Accounts rows are removed without cascading historical records. Request, usage, and audit history remains detached. Root `auth.json` is never a deletion target, so newly written B and manual M sources are preserved. The queued fingerprint is cleared only after reconciliation completes; a DB deletion failure leaves it pending so a later sync retries the same collision-safe decision.

### 6. Reverse sync excludes the active transient identity

Accounts-to-Codex-Home reverse sync skips the active tracked CodexGO fingerprint. The identity can exist in encrypted Accounts for current routing/status while it occupies root, but reverse sync cannot turn that provenance into a managed snapshot. Other identities, including untracked manual root identities, continue through the existing sync rules.

### 7. Scheduler construction supplies account reconciliation

Interactive CodexGO actions already reconcile when `CodexNeoService` has an account-sync dependency. The production scheduler factory must construct the service with `CodexNeoAccountsSyncService`; otherwise timed refresh would write root/state but leave queued retirement until an unrelated later sync.

## Failure and safety behavior

Auth schema validation remains unchanged, while stable identity validation now gates every write. Backup pruning happens after replacement, protects the current recovery path explicitly, and remains restricted to the exact managed family. Reconciliation never deletes managed location files. A failed reconciliation does not convert provenance into authority over a collision or discard pending work; the queued fingerprint remains until a later sync completes successfully.

No auth JSON, access token, refresh token, ID token, buyer token, email, account id, or workspace label is added to the provenance file, log, or response.

## Verification strategy

Service tests cover count pruning, the 3-file age floor, explicit current-backup protection against future-dated filenames, exact elapsed age beyond 14 days, unrelated-family isolation, and write-free rejection of untrackable auth. Discovery-sync tests cover root-only A-to-B retirement with detached history, pre-existing live/Backup collision preservation, manual M preservation while A is reconciled, missing-email normalization, same-identity token renewal, token-free state, reverse-sync exclusion, and failed-retirement retry. Scheduler coverage proves its production factory injects account sync.

After focused and broad backend checks plus static/OpenSpec validation pass, affected files are mirrored to both portable Python roots. Managed restart and a secret-safe live smoke verify bounded backups and current account reconciliation.
