## ADDED Requirements

### Requirement: Native tool-call continuations preserve typed output pairing

Native Codex continuation handling MUST track completed `function_call`, `custom_tool_call`, and `apply_patch_call` items by `call_id` together with their required output item type. When a request continues the just-completed response and omits a pending output, the proxy MUST add one synthetic interrupted output of the matching type before forwarding. It MUST NOT add a duplicate when the matching output is already present and MUST NOT execute or retry the tool itself.

#### Scenario: Custom tool output is missing from a continuation

- **GIVEN** a completed native response emitted `custom_tool_call` with call id `call_custom`
- **WHEN** the next request continues that response without a matching output
- **THEN** the forwarded input begins with one `custom_tool_call_output` for `call_custom`
- **AND** the upstream request is not rejected for a missing custom tool output

#### Scenario: Custom tool output is already present

- **GIVEN** a completed native response emitted `custom_tool_call` with call id `call_custom`
- **WHEN** the continuation already contains `custom_tool_call_output` for `call_custom`
- **THEN** the client output is forwarded unchanged
- **AND** no synthetic duplicate is added

#### Scenario: Upstream reports custom missing-output corruption

- **WHEN** upstream reports `No tool output found for custom tool call call_*`
- **THEN** the proxy classifies it as missing-output continuity corruption
- **AND** does not expose the raw call id downstream

#### Scenario: Safe full transcript repairs a rejected anchored continuation

- **GIVEN** an anchored continuation has not produced `response.created`
- **AND** request preparation retained a safe full transcript that is complete without the upstream anchor
- **WHEN** upstream rejects the anchor for a missing tool output
- **THEN** the proxy reconnects and replays that full transcript once without `previous_response_id`
- **AND** the proxy does not execute a tool while replaying the recorded transcript

#### Scenario: Short continuation cannot be repaired safely

- **GIVEN** a continuation depends on `previous_response_id` and has no safe full transcript
- **WHEN** upstream rejects it for a missing tool output
- **THEN** the proxy fails closed without replaying the request
