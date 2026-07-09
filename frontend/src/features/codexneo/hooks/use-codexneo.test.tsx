import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type PropsWithChildren } from "react";
import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";

import { useCodexNeo } from "@/features/codexneo/hooks/use-codexneo";

const apiMocks = vi.hoisted(() => ({
  autoDeleteCodexNeoFreeReauthAccounts: vi.fn(),
  autoDeleteCodexNeoQuotaExceededAccounts: vi.fn(),
  clearCodexNeoActivityLog: vi.fn(),
  clearCodexNeoValidityDate: vi.fn(),
  deleteCodexNeoAccounts: vi.fn(),
  exportCodexNeoAll: vi.fn(),
  exportCodexNeoSelected: vi.fn(),
  getCodexNeoAccounts: vi.fn(),
  getCodexNeoActivityLog: vi.fn(),
  getCodexNeoCodexHome: vi.fn(),
  getCodexNeoHealth: vi.fn(),
  getCodexNeoSettings: vi.fn(),
  importCodexNeoFile: vi.fn(),
  importCodexNeoFileUpload: vi.fn(),
  importCodexNeoFolder: vi.fn(),
  importCodexNeoFolderUpload: vi.fn(),
  markCodexNeoAvailable: vi.fn(),
  markCodexNeoTempUnavailable: vi.fn(),
  openCodexNeoCodexHome: vi.fn(),
  openCodexNeoDataFolder: vi.fn(),
  refreshCodexNeoSelected: vi.fn(),
  refreshCodexGoAuth: vi.fn(),
  resetCodexNeoCodexHome: vi.fn(),
  revertCodexNeoApi: vi.fn(),
  restartCodexNeoCodex: vi.fn(),
  saveCodexNeoCodexHome: vi.fn(),
  selectCodexNeoCodexHome: vi.fn(),
  setCodexNeoAccountLocation: vi.fn(),
  setCodexNeoApi: vi.fn(),
  setCodexNeoBulkLocation: vi.fn(),
  setCodexNeoValidityDate: vi.fn(),
  syncCodexNeoAccounts: vi.fn(),
  switchCodexNeoAccount: vi.fn(),
  testCodexNeoApi: vi.fn(),
  updateCodexNeoSettings: vi.fn(),
  useCodexGoAuth: vi.fn(),
}));

vi.mock("@/features/codexneo/api", () => apiMocks);
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: PropsWithChildren) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

function setupApiMocks() {
  apiMocks.getCodexNeoSettings.mockResolvedValue({
    codexApiBaseUrl: "http://127.0.0.1:2455/backend-api/codex",
    codexgoApiBaseUrl: "https://codexgo.eu/api/codex-auth",
    codexgoAutoRefreshEnabled: false,
    codexgoAutoRefreshIntervalMinutes: 30,
    openaiActivityLogEnabled: false,
    managementActivityLogEnabled: false,
    codexHomeAutoRefreshEnabled: false,
    codexHomeAutoRefreshIntervalSeconds: 30,
    codexHomeAutoSyncEnabled: false,
    minimizeToTrayEnabled: false,
    startWithWindowsEnabled: false,
    autoDeleteFreeReauthAccountsEnabled: false,
    autoDeleteQuotaExceededAccountsEnabled: false,
    buyerTokenSaved: false,
  });
  apiMocks.getCodexNeoActivityLog.mockResolvedValue({ contents: "" });
  apiMocks.getCodexNeoAccounts.mockResolvedValue({
    accounts: [],
    activeAccountKey: null,
    registryPath: null,
    message: "Loaded 0 account(s) from Codex registry",
    codexAllEnabled: false,
    backupAllEnabled: false,
  });
  apiMocks.getCodexNeoCodexHome.mockResolvedValue({
    codexHome: "C:\\Users\\rcgok\\.codex",
    defaultCodexHome: "C:\\Users\\rcgok\\.codex",
    dataDir: "H:\\Opencode IDE\\codex-ib\\codex-lb\\.data",
    customCodexHome: false,
    exists: true,
  });
  apiMocks.getCodexNeoHealth.mockResolvedValue({
    overallStatus: "ok",
    items: [],
  });
  apiMocks.useCodexGoAuth.mockResolvedValue({ success: true, message: "use ok" });
  apiMocks.refreshCodexGoAuth.mockResolvedValue({ success: true, message: "refresh ok" });
  apiMocks.refreshCodexNeoSelected.mockResolvedValue({ success: true, message: "selected refresh ok" });
  apiMocks.syncCodexNeoAccounts.mockResolvedValue({ success: true, message: "sync ok" });
  apiMocks.autoDeleteCodexNeoFreeReauthAccounts.mockResolvedValue({ success: true, message: "auto delete ok" });
  apiMocks.autoDeleteCodexNeoQuotaExceededAccounts.mockResolvedValue({
    success: true,
    message: "quota auto delete ok",
  });
  apiMocks.deleteCodexNeoAccounts.mockResolvedValue({ success: true, message: "delete ok" });
}

describe("useCodexNeo", () => {
  it("invalidates CodexNeo and Accounts queries after CodexGO auth actions", async () => {
    setupApiMocks();
    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useCodexNeo(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.settingsQuery.data).toBeTruthy());
    await result.current.useAuthMutation.mutateAsync();
    await result.current.refreshAuthMutation.mutateAsync();

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["codexneo", "accounts"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["accounts", "list"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["accounts", "trends"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["codexneo", "activity-log"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["codexneo", "health"] });
  });

  it("invalidates CodexNeo and Accounts queries after selected refresh", async () => {
    setupApiMocks();
    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useCodexNeo(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.settingsQuery.data).toBeTruthy());
    await result.current.refreshSelectedMutation.mutateAsync({ accountKeys: ["acct-1"] });

    expect(apiMocks.refreshCodexNeoSelected.mock.calls[0]?.[0]).toEqual({ accountKeys: ["acct-1"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["codexneo", "accounts"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["accounts", "list"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["accounts", "trends"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["codexneo", "activity-log"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["codexneo", "health"] });
  });

  it("invalidates CodexNeo and Accounts queries after explicit account sync", async () => {
    setupApiMocks();
    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useCodexNeo(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.settingsQuery.data).toBeTruthy());
    await result.current.syncAccountsMutation.mutateAsync();

    expect(apiMocks.syncCodexNeoAccounts).toHaveBeenCalledWith();
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["codexneo", "accounts"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["accounts", "list"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["accounts", "trends"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["codexneo", "activity-log"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["codexneo", "health"] });
  });

  it("invalidates dashboard queries after selected account delete", async () => {
    setupApiMocks();
    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useCodexNeo(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.settingsQuery.data).toBeTruthy());
    await result.current.deleteAccountsMutation.mutateAsync({ accountKeys: ["acct-1"] });

    expect(apiMocks.deleteCodexNeoAccounts.mock.calls[0]?.[0]).toEqual({ accountKeys: ["acct-1"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["codexneo", "accounts"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["accounts", "list"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["accounts", "trends"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["dashboard", "overview"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["dashboard", "projections"] });
  });

  it("shows an error toast when selected account delete fails", async () => {
    setupApiMocks();
    apiMocks.deleteCodexNeoAccounts.mockRejectedValue(new Error("delete failed"));
    const queryClient = createTestQueryClient();

    const { result } = renderHook(() => useCodexNeo(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.settingsQuery.data).toBeTruthy());
    await expect(result.current.deleteAccountsMutation.mutateAsync({ accountKeys: ["acct-1"] })).rejects.toThrow(
      "delete failed",
    );

    expect(toast.error).toHaveBeenCalledWith("delete failed");
  });
});
