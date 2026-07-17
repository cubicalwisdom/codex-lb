## Why

Anthropic permits client `tool_result.content` to contain ordered `text`, `image`, `document`, and `search_result` blocks. The current Messages translator accepts text and the separately implemented `tool_reference` lifecycle, but rejects every image, document, and search-result block before the request reaches Responses. That breaks Claude Desktop tools which return screenshots, fetched PDFs or documents, and RAG/search results.

## What Changes

- Preserve ordered text and image tool output inside the matching Responses `function_call_output` using the native Responses multimodal output shape.
- Reuse the existing bounded attachment validators and local PDF/plain-text/CSV extraction for document results, including Anthropic's documented inline `source.type: text` form.
- Preserve validated search-result metadata and text as deterministic compact JSON in the matching output rather than fabricating hosted-search results or citations.
- Keep string, text-only, empty, and `tool_reference` behavior unchanged and continue rejecting unrelated block types locally.
- Add converter, request-model, route, and historical-capacity regressions plus portable-runtime parity checks.

## Impact

- Changes the Anthropic Messages translator and the response-create historical image slimming needed by its new output shape.
- Changes the OpenAI Responses output TypedDict to reflect the already documented array contract; ordinary OpenAI and Chat Completions tool messages keep their existing string normalization.
- Updates tests, portable mirrors, OpenSpec records, and CodexNeo tracking documents.
- Adds no external dependency and does not fetch remote documents, perform OCR, upload hosted files, or synthesize citations.
