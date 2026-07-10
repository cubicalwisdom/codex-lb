## 1. Contract and regression coverage

- [x] 1.1 Add full and compact request-model regressions that preserve the complete Responses Lite input envelope, including developer instructions and a matched `custom_tool_call` / `custom_tool_call_output` pair.
- [x] 1.2 Run the request-model regression before implementation and confirm it fails because `additional_tools` is missing.
- [x] 1.3 Add a production-default HTTP Responses bridge regression that captures the forwarded embedded tool item and `x-openai-internal-codex-responses-lite: true` marker at the fake upstream boundary.
- [x] 1.4 Add WebSocket forwarding regressions for the embedded tool item, native-only marker conversion into `client_metadata`, omitted upstream handshake header, and matched custom tool call/output sequence.
- [x] 1.5 Run both transport regressions before implementation and confirm they fail at the payload-preservation assertion.

## 2. Native Responses Lite fix

- [x] 2.1 Update the Responses instruction normalizer to bypass all instruction lifting for a Responses Lite input envelope and implement native-only HTTP/WebSocket marker transport.
- [x] 2.2 Run the focused unit, HTTP, and WebSocket regressions and confirm they pass.
- [x] 2.3 Run the broader Responses request and proxy regression suites plus lint/type checks applicable to the touched files.

## 3. Portable runtime and continuity

- [x] 3.1 Mirror all corrected Responses Lite source files into the active Electron portable runtime and verify source/runtime hashes match.
- [x] 3.2 Update the main Responses compatibility spec/context, root handover, and CodexNeo implementation tracker with the verified behavior.
- [x] 3.3 Restart the explicitly authorized portable runtime and verify health, model discovery, request serialization, and Responses Lite HTTP/WebSocket behavior without applying the model-catalog workaround.

## 4. Final verification

- [x] 4.1 Validate `preserve-responses-lite-additional-tools` with strict OpenSpec validation and validate the full spec set.
- [x] 4.2 Review the final diff for unrelated changes, secrets, generated caches, and portable drift.
- [x] 4.3 Independently review the implementation and report any residual GPT-5.6 risks outside this change.
