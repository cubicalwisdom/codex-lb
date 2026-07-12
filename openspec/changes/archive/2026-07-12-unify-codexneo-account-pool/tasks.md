## 1. Canonical pool and provider ingestion

- [x] Add regression tests proving root-file and API delivery each upsert the same durable pool/snapshot contract.
- [x] Remove CodexGO root-account retirement and make same-identity updates replace the current managed snapshot.
- [x] Add backend-owned root-auth reconciliation that does not depend on the browser page.
- [x] Verify neither source deletes an earlier pooled account.

## 2. Single inventory and account actions

- [x] Make CodexNeo rows derive from canonical Accounts rows plus source/live/backup decoration.
- [x] Fix stale snapshot metadata/dedupe so every valid pool identity appears once.
- [x] Add selected deletion across pool, backup, and app-managed Codex Home locations while retaining usage aggregates.
- [x] Restrict weekly auto-delete to successful explicit zero weekly remaining values.

## 3. Import/export and activity service

- [x] Make folder import use canonical ingestion and a separate export destination for selected files.
- [x] Implement combined safe app activity storage/query with 24-hour backend retention.
- [x] Add focused regression coverage for import, export, deletion, retention, and redaction.

## 4. CodexNeo UI redesign

- [x] Replace the page with Accounts and Activity views.
- [x] Keep CodexGO and embedded Auth→API controls on Accounts; remove activity-log toggles.
- [x] Add selected refresh/export/delete controls, separate import/export folder selectors, Switch, and Switch & Restart.
- [x] Add a scrollable Activity view with filters and clear-visible action.

## 5. Verification and portable delivery

- [x] Run focused backend/frontend tests, lint, typecheck/build, and strict OpenSpec validation.
- [x] Mirror only changed runtime files into the portable distribution; do not restart the portable app or Codex Desktop.
- [x] Update the root handover and implementation inventory.
