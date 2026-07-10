## Context

The ChatGPT-backed Codex endpoint executes Responses requests but does not expose the public OpenAI stored-response and conversation resource APIs. Codex-LB therefore has to own those resource records while continuing to use its existing request routing, API-key enforcement, accounting, and stream normalization for model execution.

## Decisions

### Scope resources by downstream API key

Stored responses and conversations are keyed by the authenticated Codex-LB API-key id. When API-key authentication is disabled, they use one explicit local scope. A resource created in one scope is returned as not found from another scope.

### Store complete JSON envelopes

The database stores normalized request/input JSON and the terminal public response JSON. This preserves unknown future response item fields and avoids a second lossy ORM representation of the Responses schema. Resource ids, scope, lifecycle status, timestamps, and the upstream response id remain indexed columns.

### Run background work in owned application tasks

`background=true` creates the durable queued record before spawning one application-owned task. Retrieve observes queued/in-progress/terminal status. Cancel is accepted only for an active background response. Shutdown cancels and awaits owned tasks; startup marks stranded queued/in-progress records failed because a local task cannot survive process loss.

### Keep public ids stable while retaining upstream continuity

Locally managed background work receives a public `resp_*` id immediately. The terminal payload is rewritten to that stable public id while the original upstream id is retained separately. A later local `previous_response_id` is translated back to the upstream id after ownership validation.

### Conversations expand locally

Before execution, existing conversation items are prepended to new request input and the public `conversation` field is removed from the private upstream payload. After a successful terminal response, new input items followed by output items are appended atomically to the conversation. Conversation item ids are assigned once and remain stable across list/retrieve calls.

### Token counts are compatibility estimates, not billing claims

The private upstream does not expose a verified public input-token-count contract. Codex-LB returns a deterministic tokenizer-based count for locally visible text/tool JSON. Requests containing file/image references or opaque previous-response context fail explicitly because an exact local count is impossible. The context document and response header identify this limitation; usage billing continues to use actual upstream response usage.

## Failure handling

- Missing or cross-scope resources return OpenAI-style `not_found` errors.
- Unsupported cancellation states return a stable `invalid_request_error`.
- Failed background execution stores a terminal failed response envelope that remains retrievable.
- Conversation mutation is committed only after the corresponding database write succeeds.
- Unsupported upstream generation controls remain 400 errors and are never silently discarded.

## Example

An SDK creates `background=true`, receives `resp_local123` with `status=queued`, polls `responses.retrieve("resp_local123")`, and eventually receives the complete terminal response with the same id. If that response was attached to `conv_123`, listing the conversation later returns the user input followed by the model output.
