import { describe, expect, it } from "vitest";

import { CodexNeoSettingsSchema } from "@/features/codexneo/schemas";

describe("CodexNeoSettingsSchema", () => {
  it("defaults the auto-delete settings when an older backend omits them", () => {
    const parsed = CodexNeoSettingsSchema.parse({
      codexApiBaseUrl: "http://127.0.0.1:2455/backend-api/codex",
      codexgoApiBaseUrl: "https://codexgo.eu/api/codex-auth",
      codexgoAutoRefreshEnabled: true,
      codexgoAutoRefreshIntervalMinutes: 15,
      openaiActivityLogEnabled: true,
      managementActivityLogEnabled: true,
      codexHomeAutoRefreshEnabled: true,
      codexHomeAutoRefreshIntervalSeconds: 60,
      codexHomeAutoSyncEnabled: true,
      minimizeToTrayEnabled: true,
      startWithWindowsEnabled: true,
      buyerTokenSaved: true,
    });

    expect(parsed.autoDeleteFreeReauthAccountsEnabled).toBe(false);
    expect(parsed.autoDeleteQuotaExceededAccountsEnabled).toBe(false);
  });
});
