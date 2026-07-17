# Anthropic Multimodal Tool Results Implementation Plan

**Goal:** Translate documented image, document, and search-result content returned by Claude client tools without losing pairing, order, validation, or historical-capacity recovery.

**Architecture:** Extend the existing tool-result converter to return a string for text-only converted output and an ordered Responses content array when an image is present. Reuse existing attachment helpers, add strict search-result validation, and teach response-create historical slimming to inspect output arrays.

## Constraints

- Preserve the existing archive closeout work already dirty in the worktree.
- Remain on `codexneo-portable-windows`; do not stage, commit, push, merge, or modify another repository.
- Keep changes limited to the translator, necessary request contract/recovery helpers, focused tests, portable mirrors, and tracking files.
- Restart only Codex LB after drain and verification; do not restart Claude Desktop.

## Task 1: Specify and prove the gap

- Add converter tests for ordered text/image output, document extraction, inline text documents, search-result preservation, unchanged text/reference behavior, and malformed/unknown rejection.
- Add a route test proving the multimodal history reaches the Responses collection path.
- Add a request-model test proving a native function output array survives validation.
- Run the focused tests RED before implementation.

## Task 2: Implement the translation

- Extend `_tool_result_output` to validate and convert documented nested blocks.
- Reuse `_image_input` and `_document_input`; add bounded `source.type: text` document support.
- Validate and canonicalize search-result blocks.
- Widen `FunctionCallOutputInputItem.output` to the documented Responses array shape.
- Keep all-text and `tool_reference` output stable.

## Task 3: Preserve historical recovery

- Slim inline `input_image` parts inside historical function output arrays in both response-create helper locations.
- Add focused regression coverage for old-versus-recent output images.

## Task 4: Verify and deliver

- Run focused and full Anthropic/request/proxy tests, Ruff, scoped ty, strict OpenSpec validation, compilation, and `git diff --check`.
- Mirror every changed runtime source into both portable Python roots and verify SHA-256 parity.
- Update implementation/handover tracking with exact evidence.
- Drain and restart Codex LB once, verify health/readiness, and run safe local converter/HTTP acceptance without restarting Claude Desktop.
