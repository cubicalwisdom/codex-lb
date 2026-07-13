# Harden Portable Runtime Reliability

## Why

The Windows portable audit found reproducible startup, deletion, credential-handling, file-lock, Electron navigation, and log-retention defects. The current live database is healthy, but legacy Alembic markers can replay migrations against an already-current schema; account deletion can race request-log finalization; CodexNeo command summaries can expose secrets; SQLite handles remain open on Windows; Electron does not restrict the loaded origin; and redirected server logs grow without bound while retaining bootstrap-token output.

## What Changes

- Make the affected descendant migrations safe to replay after a recognized legacy revision is remapped, without skipping data migrations.
- Preserve request accounting when an account disappears during request-log finalization.
- Apply one shared credential redactor to CodexNeo command and exception summaries.
- Explicitly close SQLite connections before Windows replace/delete operations and use bounded retries for transient sharing violations.
- Restrict Electron navigation and privileged IPC to the configured local Codex LB origin.
- Rotate portable server logs and keep dashboard bootstrap credentials out of persistent redirected logs.
- Correct the affected typing contracts and duplicate OpenAPI operation identifiers.

## Non-goals

- Change account selection, routing, provider ingestion, automatic-deletion eligibility, or usage-retention policy.
- Restart Codex Desktop or the running Codex LB portable application automatically.
- Delete existing diagnostic logs or account data during installation of the fix.
