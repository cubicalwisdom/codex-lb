# Unify CodexNeo Account Pool

## Why

CodexGO desktop file delivery and CodexGO API delivery are two inputs for the same account provider, but the current CodexNeo implementation treats root-auth accounts as transient, maintains competing account inventories, and can hide valid backup snapshots. The result is a mismatch between CodexNeo and the Codex LB Accounts pool.

## What Changes

- Make the encrypted Codex LB Accounts table the sole routing-pool authority; CodexNeo becomes a view and controller for that pool.
- Ingest root `auth.json` and CodexGO API responses through one durable path that upserts one account identity and one managed account snapshot without retiring an earlier pooled account merely because the live root changes.
- Add backend-owned detection/reconciliation so provider desktop file replacements are captured while the CodexNeo page is closed.
- Replace the CodexNeo page with `Accounts` and `Activity` views, embed Auth→API on Accounts, clarify import/export folders, and retain per-row Switch / Switch & Restart actions.
- Move combined Codex LB/CodexNeo/provider activity into a separate, scrollable Activity view with exactly 24-hour backend retention.
- Add guarded selected-account deletion across the pool, app-owned snapshots, and app-managed Codex Home entries while preserving aggregate usage statistics.

## Non-goals

- Change Codex LB proxy routing, request execution, main Accounts page behavior, dashboard calculations, or Electron launch/restart behavior.
- Restart Codex Desktop or the portable app automatically.

