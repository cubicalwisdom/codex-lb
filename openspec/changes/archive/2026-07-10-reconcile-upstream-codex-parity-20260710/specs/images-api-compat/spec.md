## ADDED Requirements

### Requirement: Native Codex image aliases reuse the Images API pipeline

The native Codex base MUST expose hidden POST aliases for `images/generations` and `images/edits`. Generation MUST delegate to the existing generation handler. Native edits MUST accept JSON `images[].image_url` base64 data URLs, validate the existing edit form, decode every image, and delegate to the existing edit pipeline without changing the public multipart `/v1/images/edits` contract.

#### Scenario: Native reference-image edit reaches the shared pipeline

- **GIVEN** a native Codex edit request contains a valid prompt and one or more image data URLs
- **WHEN** it posts to `/backend-api/codex/images/edits`
- **THEN** the proxy decodes the images and invokes the same edit pipeline used by `/v1/images/edits`
- **AND** invalid JSON, missing images, malformed data URLs, and invalid UTF-8 return OpenAI-shaped 400 responses rather than 405
