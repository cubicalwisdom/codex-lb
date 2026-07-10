## 1. Contract and regressions

- [x] 1.1 Add failing pricing tests for the generic GPT-5.6 alias, published cache-write rates, clamping, and Fast non-double-counting.
- [x] 1.2 Add failing response-model and request-log persistence/API tests for `cache_write_tokens`.
- [x] 1.3 Add a failing migration test for the nullable request-log column and single-head Alembic graph.
- [x] 1.4 Add failing frontend schema/detail tests for cache-write tokens and cost.

## 2. Backend implementation

- [x] 2.1 Type and normalize response cache-write usage details.
- [x] 2.2 Extend shared pricing with cache-write rates/cost breakdown and the exact GPT-5.6 Sol alias.
- [x] 2.3 Carry cache-write tokens through HTTP streaming, websocket, compact, warmup, settlement, and request-log persistence paths.
- [x] 2.4 Add the ORM field, repository mapping, API schema mapping, and Alembic migration without historical backfill.

## 3. Dashboard implementation

- [x] 3.1 Accept cache-write fields in the request-log frontend schema.
- [x] 3.2 Show cache-write tokens and their separate cost in recent-request detail.

## 4. Verification and portable closeout

- [x] 4.1 Run focused backend pricing/model/request-log/migration tests and lint.
- [x] 4.2 Run focused frontend tests, typecheck, and production build.
- [x] 4.3 Run strict OpenSpec validation and relevant integration tests.
- [x] 4.4 Mirror verified backend/static/migration files into the active portable distribution without restarting Codex Desktop or Electron.
- [x] 4.5 Update CodexNeo implementation tracking and handover with exact verification evidence.
