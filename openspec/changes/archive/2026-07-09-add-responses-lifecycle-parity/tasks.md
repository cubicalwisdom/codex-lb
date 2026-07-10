## 1. Durable resources

- [x] 1.1 Add stored-response, conversation, and conversation-item ORM models and Alembic migration.
- [x] 1.2 Add scoped repositories and lifecycle service with startup recovery.

## 2. Responses lifecycle

- [x] 2.1 Enable synchronous `store=true` persistence and stable retrieval/deletion.
- [x] 2.2 Add owned background execution, polling, cancellation, and shutdown cleanup.
- [x] 2.3 Add response input-item listing with stable ids and cursor pagination.
- [x] 2.4 Add local input-token count compatibility with opaque-input rejection.

## 3. Conversations

- [x] 3.1 Add conversation create/retrieve/update/delete routes.
- [x] 3.2 Add conversation item create/retrieve/delete/list routes.
- [x] 3.3 Expand conversation context for Responses execution and append terminal input/output.

## 4. Verification and closeout

- [x] 4.1 Add HTTP and OpenAI SDK regressions for lifecycle, background, scoping, and conversations.
- [x] 4.2 Add migration upgrade/downgrade and single-head verification.
- [x] 4.3 Run focused and neighboring pytest, Ruff, ty, and OpenSpec checks.
- [x] 4.4 Update implementation tracking and handover, then mirror runtime files without restarting Codex Desktop or Electron.
