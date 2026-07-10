# Responses Lite embedded tool preservation

## Purpose and scope

This change fixes the GPT-5.6 Sol failure where Codex receives an ordinary text response claiming that no shell/filesystem tool is available. The fix is limited to preserving the Responses Lite wire contract; it does not replace Responses Lite with the legacy top-level-tools request shape.

## Data flow and decision

Native Codex 0.144.0 and later may send a Responses request whose first input item is an `additional_tools` protocol object. Although that object uses `role: "developer"`, it is not a developer message and has no `content` field. It must reach upstream unchanged.

The request-model normalizer identifies the wire contract before performing ordinary compatibility normalization:

1. Inspect the input array for an item with `type: "additional_tools"`.
2. If present, return the entire request envelope unchanged from instruction lifting. Responses Lite deliberately keeps base developer instructions in the next developer message inside `input`.
3. If absent, apply the existing system/developer instruction extraction only to message-like items.
4. Preserve all other input items, including matched `custom_tool_call` and `custom_tool_call_output` items, in order.

This special case is intentionally exact. General non-Lite developer messages still move into the top-level `instructions` field, and the proxy does not manufacture a top-level `tools` field.

The same normalizer is shared by full and compact Responses request models. The protocol-item bypass therefore applies consistently to both validation paths, even though GPT-5.6 Sol tool execution uses the full Responses transports covered by the endpoint regressions.

The marker is accepted only from a native Codex identity. It is stripped from the generic inbound-header set, then reconstructed for upstream HTTP/compact requests when the native request selected Lite. For upstream WebSocket requests, the proxy writes the equivalent `ws_request_header_x_openai_internal_codex_responses_lite` key into `client_metadata` and keeps the HTTP-only marker out of the WebSocket handshake. The same conversion covers HTTP-to-WebSocket bridge requests and WebSocket-to-HTTP fallback.

## Constraints

- Preserve the complete `additional_tools` mapping, including grammar-format fields unknown to the current schema.
- Preserve relative ordering between `additional_tools`, the following developer instruction message, ordinary input messages, tool calls, and `custom_tool_call_output` items.
- Do not honor the internal Lite marker from a generic SDK or other non-native client identity.
- Keep the fix transport-neutral so the same validated payload is used by raw HTTP, the HTTP Responses bridge, and WebSocket `response.create` forwarding.
- Do not log embedded tool grammars or request content as part of this fix.
- Do not restart Codex Desktop. Only the explicitly authorized portable Codex IB/CodexNeo runtime may be restarted.

## Failure modes

- If `additional_tools` is dropped, GPT-5.6 Sol can complete normally but has no executable tools; this is a silent capability loss rather than a filesystem exception.
- If the item is converted into text instructions, the tool schema remains unusable and could leak structured grammar into the prompt.
- If the marker is omitted from HTTP or encoded as a handshake header instead of WebSocket `client_metadata`, upstream may not select the intended Responses Lite handling even when the payload is otherwise intact.

## Example

Inbound and forwarded input must retain this first item unchanged:

```json
{
  "type": "additional_tools",
  "role": "developer",
  "tools": [
    {
      "type": "custom",
      "name": "exec",
      "format": {"type": "grammar", "syntax": "lark", "definition": "start: /.+/"}
    }
  ]
}
```

The next developer message and a later matched `custom_tool_call` / `custom_tool_call_output` pair must remain later in the same input array. The forwarded request must not gain a top-level `tools` bundle merely because this embedded item exists.

## Verification strategy

- Full and compact request-model regressions prove the exact object and input ordering survive their shared validation and serialization path.
- An HTTP regression captures the exact upstream body, native-only Lite header, and HTTP fallback behavior.
- WebSocket regressions capture the upstream `response.create` metadata and prove the HTTP-only Lite header is absent from the upstream handshake.
- Portable verification imports and serializes through the mirrored runtime before and after restart, then checks the restarted service health and model endpoints.
