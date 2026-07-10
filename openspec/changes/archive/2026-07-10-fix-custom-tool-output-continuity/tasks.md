## 1. Contract and RED regressions

- [x] 1.1 Add a regression that classifies `No tool output found for custom tool call call_*` as missing-output continuity corruption.
- [x] 1.2 Add a regression that records the required output type for a completed custom tool call.
- [x] 1.3 Add a native WebSocket continuation regression that injects `custom_tool_call_output` only when it is absent.
- [x] 1.4 Add the observed pre-response custom missing-output regression: owner-pinned anchored request, safe full transcript, one fresh replay.

## 2. Minimal implementation

- [x] 2.1 Extend pending-call state with the expected output type while retaining existing ordinary-function compatibility.
- [x] 2.2 Generalize output detection and interrupted-output synthesis across ordinary, custom, and apply-patch call types.
- [x] 2.3 Use the generalized tracking in both direct WebSocket and HTTP-bridge upstream event handling.
- [x] 2.4 Retry pre-response missing-output corruption once from a safe full transcript while retaining fail-closed behavior for unsafe short continuations.

## 3. Verification and portable closeout

- [x] 3.1 Run only the focused RED/GREEN tests and neighboring continuity tests, plus Ruff and scoped `ty`.
- [x] 3.2 Strictly validate the change and stable specs, then archive it.
- [x] 3.3 Mirror touched backend files to both portable Python locations and verify hashes/compile.
- [x] 3.4 Update the implementation tracker and handover; do not restart Codex Desktop or Electron.
