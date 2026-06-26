import { del, get, post, put } from "@/lib/api-client";

import {
  CodexNeoActionResponseSchema,
  CodexNeoAccountKeysRequestSchema,
  CodexNeoAccountsResponseSchema,
  CodexNeoActivityLogResponseSchema,
  CodexNeoApiUrlRequestSchema,
  CodexNeoBulkLocationRequestSchema,
  CodexNeoCodexHomeResponseSchema,
  CodexNeoCodexHomeUpdateRequestSchema,
  CodexNeoHealthResponseSchema,
  CodexNeoLocationRequestSchema,
  CodexNeoPathRequestSchema,
  CodexNeoPathResponseSchema,
  CodexNeoSettingsSchema,
  CodexNeoSettingsUpdateRequestSchema,
  CodexNeoSwitchRequestSchema,
  CodexNeoValidityDateRequestSchema,
} from "@/features/codexneo/schemas";

const CODEXNEO_PATH = "/api/codexneo";

export function getCodexNeoSettings() {
  return get(CODEXNEO_PATH, CodexNeoSettingsSchema);
}

export function updateCodexNeoSettings(payload: unknown) {
  const validated = CodexNeoSettingsUpdateRequestSchema.parse(payload);
  return put(CODEXNEO_PATH, CodexNeoSettingsSchema, { body: validated });
}

export function getCodexNeoActivityLog() {
  return get(CODEXNEO_PATH + "/activity-log", CodexNeoActivityLogResponseSchema);
}

export function clearCodexNeoActivityLog() {
  return del(CODEXNEO_PATH + "/activity-log", CodexNeoActionResponseSchema);
}

export function getCodexNeoAccounts() {
  return get(CODEXNEO_PATH + "/accounts", CodexNeoAccountsResponseSchema);
}

export function getCodexNeoHealth() {
  return get(CODEXNEO_PATH + "/health", CodexNeoHealthResponseSchema);
}

export function getCodexNeoCodexHome() {
  return get(CODEXNEO_PATH + "/codex-home", CodexNeoCodexHomeResponseSchema);
}

export function saveCodexNeoCodexHome(payload: unknown) {
  const validated = CodexNeoCodexHomeUpdateRequestSchema.parse(payload);
  return put(CODEXNEO_PATH + "/codex-home", CodexNeoCodexHomeResponseSchema, { body: validated });
}

export function resetCodexNeoCodexHome() {
  return post(CODEXNEO_PATH + "/codex-home/reset", CodexNeoCodexHomeResponseSchema, { body: {} });
}

export function selectCodexNeoCodexHome() {
  return post(CODEXNEO_PATH + "/codex-home/select", CodexNeoPathResponseSchema, { body: {} });
}

export function openCodexNeoCodexHome() {
  return post(CODEXNEO_PATH + "/codex-home/open", CodexNeoPathResponseSchema, { body: {} });
}

export function openCodexNeoDataFolder() {
  return post(CODEXNEO_PATH + "/data-folder/open", CodexNeoPathResponseSchema, { body: {} });
}

export function restartCodexNeoCodex() {
  return post(CODEXNEO_PATH + "/app/restart", CodexNeoActionResponseSchema, { body: {} });
}

export function importCodexNeoFile(payload: unknown) {
  const validated = CodexNeoPathRequestSchema.parse(payload);
  return post(CODEXNEO_PATH + "/import/file", CodexNeoPathResponseSchema, { body: validated });
}

export function importCodexNeoFileUpload(payload: { file: File }) {
  const formData = new FormData();
  formData.append("auth_json", payload.file, payload.file.name);
  return post(CODEXNEO_PATH + "/import/file-upload", CodexNeoPathResponseSchema, { body: formData });
}

export function importCodexNeoFolder(payload: unknown) {
  const validated = CodexNeoPathRequestSchema.parse(payload);
  return post(CODEXNEO_PATH + "/import/folder", CodexNeoPathResponseSchema, { body: validated });
}

export function importCodexNeoFolderUpload(payload: { files: File[] }) {
  const formData = new FormData();
  for (const file of payload.files) {
    const relativePath = "webkitRelativePath" in file ? String(file.webkitRelativePath) : "";
    formData.append("files", file, relativePath || file.name);
  }
  return post(CODEXNEO_PATH + "/import/folder-upload", CodexNeoPathResponseSchema, { body: formData });
}

export function exportCodexNeoAll(payload: unknown) {
  const validated = CodexNeoPathRequestSchema.parse(payload);
  return post(CODEXNEO_PATH + "/export/all", CodexNeoPathResponseSchema, { body: validated });
}

export function exportCodexNeoSelected(payload: unknown) {
  const validated = CodexNeoAccountKeysRequestSchema.parse(payload);
  return post(CODEXNEO_PATH + "/export/selected", CodexNeoPathResponseSchema, { body: validated });
}

export function markCodexNeoTempUnavailable(payload: unknown) {
  const validated = CodexNeoAccountKeysRequestSchema.parse(payload);
  return post(CODEXNEO_PATH + "/accounts/temp-unavailable", CodexNeoActionResponseSchema, { body: validated });
}

export function markCodexNeoAvailable(payload: unknown) {
  const validated = CodexNeoAccountKeysRequestSchema.parse(payload);
  return post(CODEXNEO_PATH + "/accounts/mark-available", CodexNeoActionResponseSchema, { body: validated });
}

export function setCodexNeoValidityDate(payload: unknown) {
  const validated = CodexNeoValidityDateRequestSchema.parse(payload);
  return post(CODEXNEO_PATH + "/accounts/validity-date", CodexNeoActionResponseSchema, { body: validated });
}

export function clearCodexNeoValidityDate(payload: unknown) {
  const validated = CodexNeoAccountKeysRequestSchema.parse(payload);
  return post(CODEXNEO_PATH + "/accounts/clear-validity-date", CodexNeoActionResponseSchema, { body: validated });
}

export function refreshCodexNeoSelected(payload: unknown) {
  const validated = CodexNeoAccountKeysRequestSchema.parse(payload);
  return post(CODEXNEO_PATH + "/accounts/refresh", CodexNeoActionResponseSchema, { body: validated });
}

export function syncCodexNeoAccounts() {
  return post(CODEXNEO_PATH + "/accounts/sync", CodexNeoActionResponseSchema, { body: {} });
}

export function setCodexNeoAccountLocation(payload: unknown) {
  const validated = CodexNeoLocationRequestSchema.parse(payload);
  return post(CODEXNEO_PATH + "/accounts/location", CodexNeoActionResponseSchema, { body: validated });
}

export function setCodexNeoBulkLocation(payload: unknown) {
  const validated = CodexNeoBulkLocationRequestSchema.parse(payload);
  return post(CODEXNEO_PATH + "/accounts/location/default", CodexNeoActionResponseSchema, { body: validated });
}

export function switchCodexNeoAccount(payload: unknown) {
  const validated = CodexNeoSwitchRequestSchema.parse(payload);
  return post(CODEXNEO_PATH + "/accounts/switch", CodexNeoActionResponseSchema, { body: validated });
}

export function deleteCodexNeoAccounts(payload: unknown) {
  const validated = CodexNeoAccountKeysRequestSchema.parse(payload);
  return post(CODEXNEO_PATH + "/accounts/delete", CodexNeoActionResponseSchema, { body: validated });
}

export function testCodexNeoApi(payload: unknown) {
  const validated = CodexNeoApiUrlRequestSchema.parse(payload);
  return post(`${CODEXNEO_PATH}/api-test`, CodexNeoActionResponseSchema, { body: validated });
}

export function setCodexNeoApi(payload: unknown) {
  const validated = CodexNeoApiUrlRequestSchema.parse(payload);
  return post(`${CODEXNEO_PATH}/api-set`, CodexNeoActionResponseSchema, { body: validated });
}

export function revertCodexNeoApi() {
  return post(`${CODEXNEO_PATH}/api-revert`, CodexNeoActionResponseSchema, { body: {} });
}

export function useCodexGoAuth() {
  return post(`${CODEXNEO_PATH}/codexgo/use`, CodexNeoActionResponseSchema, { body: {} });
}

export function refreshCodexGoAuth() {
  return post(`${CODEXNEO_PATH}/codexgo/refresh`, CodexNeoActionResponseSchema, { body: {} });
}
