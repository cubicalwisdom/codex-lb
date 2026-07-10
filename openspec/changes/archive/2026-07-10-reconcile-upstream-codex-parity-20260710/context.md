## Reconciliation decisions

This change ports final behavior from merged upstream PRs #1160, #1161, #1163, #1172, #1175, and #1176. It does not replace local files from upstream because the portable branch has substantial independent Responses lifecycle, pricing, provider, and continuity work.

Responses Lite is determined from the normalized request body. An inbound internal header or WebSocket metadata marker is never sufficient by itself. After a full Lite request for an effective model reaches `response.created`, a marker-only incremental request for that same accepted model may retain Lite continuity. Fresh replay and model rewrites must reclassify the marker instead of inheriting stale trust.

Non-message system/developer objects are protocol directives, not prompt text. They remain byte-identical through instruction lifting, sanitizer passes, omitted-instructions defaulting, and compact trimming. For example, a future `developer_state` object with opaque `reasoning_content` stays in `input` instead of being hoisted or stripped.

Interrupted outputs are typed by `call_id`: `function_call_output`, `custom_tool_call_output`, or `apply_patch_call_output` with `status: failed`. HTTP bridge injection occurs before request preparation so byte limits, fingerprints, stored context, and API-key usage budgets describe the actual upstream payload. CN-060 additionally retains its one-shot fresh full-transcript recovery when upstream reports a hidden orphan call that cannot be reconstructed locally.

Owner-forward failover has one bounded gap. If the remote owner relay fails before yielding downstream bytes, the local worker rebinds a local bridge session and injects interrupted outputs only when that rebound session still has the pending call state. The durable bridge store does not persist call ids, so a fresh local session without pending state resubmits the anchored request unchanged; any resulting upstream missing-output rejection is masked as a retryable continuity failure instead of exposing the raw 400 or call id.

The GPT-5.6 bootstrap is a degraded-startup fallback, not pricing authority. It mirrors Codex 0.144.1 model metadata, while live refreshed catalog data remains authoritative. The 372,000-token catalog window does not enable long-context, Flex, or Priority pricing. `model_messages` and unknown live fields continue to pass through unchanged.

Native image aliases reuse the existing local image pipeline. `/backend-api/codex/images/edits` accepts JSON `images[].image_url` data URLs, decodes them, validates the existing edit form, and delegates without changing `/v1/images/edits` multipart behavior. The local branch does not import unrelated upstream image observability infrastructure.

`/v1/models` remains OpenAI-compatible unless `client_version` is non-empty. A Codex client that supplies the parameter receives the same native catalog shape as `/backend-api/codex/models`; an absent or empty parameter still returns `{object: list, data: [...]}`.
