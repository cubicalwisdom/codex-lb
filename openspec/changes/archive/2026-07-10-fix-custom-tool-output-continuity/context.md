## Invariant

A model tool-call item and its output are a typed pair keyed by `call_id`:

- `function_call` -> `function_call_output`
- `custom_tool_call` -> `custom_tool_call_output`
- `apply_patch_call` -> `apply_patch_call_output`

When a completed response leaves one of these calls pending and the client continues that exact response without the output, codex-lb closes only the missing pair with a synthetic interrupted-output item of the correct type. If the client supplied the output, it is forwarded unchanged and no duplicate is added.

The proxy does not execute the tool or claim that a side effect is safe to repeat. Its responsibility is only to keep the upstream Responses protocol structurally valid.

If upstream nevertheless rejects an anchored request for a missing output before `response.created`, the proxy may replay once only when request preparation retained a safe full transcript that is complete without the upstream anchor. That replay removes `previous_response_id`; short continuations without a complete transcript remain fail-closed. The proxy re-sends recorded input and does not execute a tool itself.
