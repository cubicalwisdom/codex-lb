"use strict";

function parsedUrl(value) {
  try {
    return new URL(value);
  } catch {
    return null;
  }
}

function isAllowedAppUrl(candidate, baseUrl) {
  const requested = parsedUrl(candidate);
  const allowed = parsedUrl(baseUrl);
  return Boolean(requested && allowed && requested.origin === allowed.origin && ["http:", "https:"].includes(requested.protocol));
}

function isSafeExternalUrl(candidate) {
  const requested = parsedUrl(candidate);
  return Boolean(requested && ["http:", "https:"].includes(requested.protocol));
}

function assertTrustedIpcSender(event, baseUrl) {
  const senderUrl = event?.senderFrame?.url || event?.sender?.getURL?.() || "";
  if (!isAllowedAppUrl(senderUrl, baseUrl)) {
    throw new Error("Rejected IPC request from an untrusted renderer origin");
  }
}

module.exports = { assertTrustedIpcSender, isAllowedAppUrl, isSafeExternalUrl };
