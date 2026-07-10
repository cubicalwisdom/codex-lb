## 1. Codex Desktop restart

- [x] 1.1 Refactor the restart PowerShell into a testable builder.
- [x] 1.2 Close the packaged `ChatGPT.exe` shell and force-stop only remaining `OpenAI.Codex` package processes.
- [x] 1.3 Add regression coverage proving bare non-package `codex.exe` processes are not targeted.

## 2. Model catalogue parity

- [x] 2.1 Stop filtering `model_messages` from fetched model metadata.
- [x] 2.2 Add parser and native endpoint contract-diff tests for `model_messages` and unknown future fields.
- [x] 2.3 Update bootstrap expectations for GPT-5.6 Sol, Terra, and Luna.

## 3. Responses request behavior

- [x] 3.1 Accept `previous_response_id`-only and `conversation`-only requests while preserving mutual exclusion.
- [x] 3.2 Reject unsupported background, persistence, and generation controls with exact parameter errors.
- [x] 3.3 Add focused unit and HTTP-route regression coverage.

## 4. Verification and closeout

- [x] 4.1 Run focused pytest and Ruff checks.
- [x] 4.2 Validate the OpenSpec change and stable specs.
- [x] 4.3 Update the CodexNeo implementation list and handover with verified behavior and remaining full-parity work.
- [x] 4.4 Mirror safe runtime files into the portable distribution without restarting Codex Desktop or the Electron app.
