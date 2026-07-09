## 1. Contract Tests

- [x] 1.1 Add backend tests for the native default, exact legacy migration persistence, and custom URL preservation.
- [x] 1.2 Add provider-test coverage for native, generic OpenAI, and invalid JSON model catalogs.
- [x] 1.3 Update focused diagnostics and frontend expectations for the native Codex URL.
- [x] 1.4 Add a regression proving the legacy migration preserves unrecognized persisted settings.
- [x] 1.5 Add a regression proving a redirect is not accepted as a native model catalog.

## 2. Implementation

- [x] 2.1 Implement centralized native Codex URL normalization and the one-time persisted legacy migration.
- [x] 2.2 Require the native `models` response envelope in the CodexNeo provider connectivity test.
- [x] 2.3 Update CodexNeo dashboard guidance while preserving generic `/v1` client documentation.
- [x] 2.4 Restrict the migration write to the legacy provider key so unknown settings remain intact.
- [x] 2.5 Require a direct 2xx response and reject redirects during provider validation.

## 3. Portable And Continuity

- [x] 3.1 Synchronize the verified source/backend/frontend changes into the portable runtime and compare relevant files.
- [x] 3.2 Update the CodexNeo implementation tracker and handover with root cause, migration behavior, and verification evidence.

## 4. Verification

- [x] 4.1 Run focused backend and frontend tests plus formatting/type checks for changed code.
- [ ] 4.2 Run the repository's documented OpenSpec and portable verification checks and record any limitations.
