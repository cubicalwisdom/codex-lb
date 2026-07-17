## Context

Anthropic documents nested `tool_result` content as `text`, `image`, `document`, or `search_result`. OpenAI Responses documents `function_call_output.output` as either a string or an ordered array of `input_text`, `input_image`, and `input_file` content. Most reviewed adapters still join text and drop or stringify other blocks. CLIProxyAPI implements the reverse mapping from Responses arrays to Anthropic image/document blocks, while `caozhiyuan/copilot-api` keeps attachments inside tool results for its Copilot transport.

The active Codex upstream accepts image input, but this project intentionally converts inline PDF/plain-text/CSV documents to bounded text because raw inline file transport has not been established for the ChatGPT-backed route. The same proven boundary applies to document tool results.

## Goals

- Accept every documented client tool-result content family used by Claude Desktop.
- Keep content attached to its original tool call and preserve block order.
- Reuse existing attachment validation, extraction, and identifier mapping.
- Prevent large historical inline result images from defeating the existing response-create recovery path.
- Preserve all existing string, text-only, and ToolSearch reference behavior.

## Non-Goals

- Emulate Anthropic server-tool result blocks or citation semantics.
- Fetch document URLs, run OCR, upload files, or add a Files API.
- Relax existing media type, base64 size, PDF page/content, extracted-character, URL, or encryption limits.
- Change ordinary OpenAI/Chat tool-message normalization.
- Restart Claude Desktop.

## Decisions

### Preserve the tool-result trust boundary

Converted content remains inside the matching `function_call_output.output`. It is never promoted into system instructions or an ordinary user message. This follows Anthropic's prompt-injection guidance and retains the original call ID.

### Use native image output and local document extraction

An image block is validated by the existing `_image_input` path and becomes an `input_image` item in the ordered output array. A document block is validated by `_document_input`; base64 PDF/plain/CSV sources are locally extracted using the current bounds, and Anthropic's documented inline text source is accepted as bounded UTF-8 text. The resulting labelled `input_text` content is used instead of an unproven upstream `input_file` wire shape.

If conversion yields only text items, the translator returns one string so existing response-create tool-output slimming continues to apply. The translator uses an output array only when a native image must be retained, with adjacent text/document/search items kept in their original order.

### Preserve search results without fabricating citations

A `search_result` must contain non-empty `source` and `title` strings plus a non-empty array of non-empty text blocks. Optional `citations` and `cache_control` values are preserved with all other supplied metadata in canonical compact JSON. That JSON becomes `input_text` inside the same function output. The adapter does not create `web_search_call`, hosted search outputs, or citation annotations because the client tool, not the upstream hosted tool, produced the result.

### Keep ToolSearch reference behavior stable

Reference-only ToolSearch pairs continue through native `tool_search_call`/`tool_search_output`. Any other result containing `tool_reference` continues through the existing canonical whole-array JSON fallback. This change does not reinterpret mixed reference results.

### Slim historical images in output arrays

The existing pre-stream recovery pass already replaces old inline user images. It will apply the same omission marker to inline `input_image` items inside historical `function_call_output.output` arrays while leaving the recent suffix intact. Both the decomposed service helper and the compatibility facade copy remain aligned.

## Failure Modes

- Malformed image, document, or search-result fields return Anthropic `invalid_request_error` with the nested parameter path.
- Unsupported block types remain local 400 errors and never reach upstream execution.
- Scanned/image-only, encrypted, oversized, or excessive-page PDFs retain their current explicit errors.
- Document URLs remain rejected because the adapter does not perform network fetches.

## References

- https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls
- https://platform.claude.com/docs/en/build-with-claude/search-results
- https://developers.openai.com/api/reference/resources/responses/methods/create
- https://github.com/router-for-me/CLIProxyAPI/blob/main/internal/translator/claude/openai/responses/claude_openai-responses_request.go
- https://github.com/caozhiyuan/copilot-api/blob/dev/src/routes/messages/preprocess.ts
