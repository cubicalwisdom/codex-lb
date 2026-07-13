## 1. Regression coverage

- [x] 1.1 Reproduce legacy revision remap against an already-current schema and require a clean upgrade.
- [x] 1.2 Reproduce request-log finalization after account deletion and require an accountless retained log.
- [x] 1.3 Reproduce whitespace, JSON, bearer, and buyer-token command output and require complete redaction.
- [x] 1.4 Reproduce Windows SQLite backup/retag cleanup and require handles to be released before replacement.
- [x] 1.5 Verify Electron navigation, external URL, sender-origin, and log-rotation policy through focused tests.

## 2. Implementation

- [x] 2.1 Make descendant schema migrations idempotent when a recognized legacy Alembic marker is remapped, without stamping past data migrations.
- [x] 2.2 Retry request-log persistence without a deleted account foreign key while preserving captured metadata.
- [x] 2.3 Reuse the central runtime redactor for every CodexNeo command summary.
- [x] 2.4 Explicitly close SQLite handles and add bounded Windows sharing-violation retries.
- [x] 2.5 Enforce Electron local-origin navigation/IPC and rotate redirected portable logs.
- [x] 2.6 Correct nullable usage typing and unique OpenAPI operation identifiers.

## 3. Verification and delivery

- [x] 3.1 Run focused regression tests, Ruff, ty, OpenSpec validation, and Electron syntax/tests.
- [x] 3.2 Run the broad backend/frontend verification ladder and record any unrelated residual failures.
- [x] 3.3 Mirror verified backend files and stage the locked Electron archive in the portable distribution without restarting it.
- [x] 3.4 Update CodexNeo implementation tracking and the root handover with exact results and restart instructions.
