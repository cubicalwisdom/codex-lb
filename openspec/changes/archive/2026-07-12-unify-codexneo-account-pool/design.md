# Design: One Pool, Two Views

## Authority

`accounts` is the canonical pool. Each pooled identity has one current encrypted credential record and one app-owned snapshot under `portable-data/account-backups`. CodexNeo and the existing Codex LB Accounts page render the same identities; CodexNeo adds source, current-live, and backup state.

## Ingestion

Both CodexGO delivery methods use the same ingestion operation:

1. Read a stable valid auth payload and derive the normalized account identity.
2. Atomically upsert encrypted credentials in the Accounts table without overwriting an operator-paused state.
3. Atomically upsert the account-specific managed snapshot and token-free backup registry row.
4. Mark the matching pool identity as current-live when it matches root `auth.json`.

No source may delete or retire a previously pooled identity because another identity became live. A backend periodic reconciler watches root `auth.json` independently of the browser page. API-originated auth is ingested before it replaces root `auth.json`.

## Deletion and retention

Delete selected is confirmation-gated. It removes only the selected account credentials from the routing pool, app-owned backup snapshot/registry, and app-managed Codex Home snapshot/registry. If selected identity is current-live, its live reference is cleared. It does not restart Codex Desktop and leaves aggregate usage statistics intact. The weekly auto-delete policy may delete only an account whose latest successful weekly refresh explicitly reports remaining `0`; positive and unknown values are retained.

## Activity

Activity is a separate CodexNeo page. It combines safe Codex LB request/routing/quota events with CodexNeo sync/backup/provider events, is scrollable, and is pruned by backend time retention at 24 hours. It must not expose tokens or raw auth JSON.

