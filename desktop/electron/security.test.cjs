"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { assertTrustedIpcSender, isAllowedAppUrl, isSafeExternalUrl } = require("./security.cjs");

const BASE_URL = "http://127.0.0.1:2455";

test("allows renderer navigation only within the configured app origin", () => {
  assert.equal(isAllowedAppUrl("http://127.0.0.1:2455/codexneo", BASE_URL), true);
  assert.equal(isAllowedAppUrl("http://127.0.0.1:2456/codexneo", BASE_URL), false);
  assert.equal(isAllowedAppUrl("file:///C:/secret", BASE_URL), false);
});

test("allows only web URLs to be opened externally", () => {
  assert.equal(isSafeExternalUrl("https://example.com/help"), true);
  assert.equal(isSafeExternalUrl("javascript:alert(1)"), false);
  assert.equal(isSafeExternalUrl("file:///C:/secret"), false);
});

test("rejects IPC from a renderer outside the app origin", () => {
  assert.throws(
    () => assertTrustedIpcSender({ senderFrame: { url: "https://evil.example/" } }, BASE_URL),
    /untrusted renderer origin/,
  );
  assert.doesNotThrow(() =>
    assertTrustedIpcSender({ senderFrame: { url: "http://127.0.0.1:2455/codexneo" } }, BASE_URL),
  );
});
