## Context

Codex Desktop is a packaged Windows application whose visible shell is `ChatGPT.exe`; its `codex.exe app-server` process is a child. Killing only the child produces the Desktop crash page instead of a clean restart. Separately, Codex-native personality data arrives through `model_messages`, but the model fetcher removes that one field before storing the upstream snapshot.

The ChatGPT-backed Responses upstream does not provide the public background lifecycle surface and rejects or ignores several public OpenAI controls. Accepting those fields locally and then deleting them creates a false-success contract.

## Decisions

### Restart the package, not a process name

The restart script will discover processes by the installed `OpenAI.Codex` WindowsApps path. It will ask the `ChatGPT.exe` shell to close first, then refresh discovery and force-stop only remaining processes from that package. A bare `codex.exe` process outside the package, such as a CLI or another agent runtime, will not be targeted.

### Preserve model catalogue data by default

The model fetcher will retain a shallow copy of the complete upstream model object in `UpstreamModel.raw`. The native model response already filters duplicate typed fields and allows JSON-compatible extras, so new upstream keys will pass through without requiring a field-by-field allowlist.

### Normalize input-less continuations to empty input

An OpenAI-compatible request may omit `input` and `messages` when it supplies exactly one non-empty continuity key: `previous_response_id` or `conversation`. The internal request remains valid by normalizing omitted instructions to an empty string and omitted input to an empty list. Requests with neither new input nor a continuity key remain invalid, and the two continuity keys remain mutually exclusive.

### Fail explicitly for unsupported controls

The standard Responses HTTP surfaces will reject `background=true`, `store=true`, and controls currently removed before the ChatGPT-backed upstream (`max_output_tokens`, `metadata`, `prompt_cache_retention`/`promptCacheRetention`, `safety_identifier`, `temperature`, `top_p`, `truncation`, and `user`). The response will identify the exact parameter with `code=unsupported_parameter`. `background=false`, `store=false`, and omitted controls remain valid; `background=false` is removed before forwarding.

This pass deliberately does not pretend to implement background jobs. Full parity can later replace these rejections only when the required create/get/cancel/delete/input-items lifecycle is implemented and tested end to end.

For `truncation`, this decision supersedes only the accept-and-strip behavior documented by the older `fix-api-key-null-models-and-truncation` change. That change's unrelated API-key null-model filtering remains intact.

## Verification

- Unit-test restart script targeting without executing it.
- Unit-test upstream model parsing with `model_messages` and an unknown future field.
- Integration-test native model catalogue pass-through and GPT-5.6 bootstrap expectations.
- Unit/integration-test continuation-only normalization and exact unsupported-control errors on both `/v1/responses` and `/backend-api/codex/responses`.
- Run focused pytest, Ruff, OpenSpec validation, and diff checks without restarting Codex Desktop.
