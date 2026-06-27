import { act, fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "@/features/auth/hooks/use-auth";
import { renderWithProviders } from "@/test/utils";

import { CodexNeoPage } from "./codexneo-page";

const hookMocks = vi.hoisted(() => ({
  useCodexNeo: vi.fn(),
}));

vi.mock("@/features/codexneo/hooks/use-codexneo", () => hookMocks);

function createMutationMock() {
  return {
    isPending: false,
    error: null as Error | null,
    mutateAsync: vi.fn().mockResolvedValue({ success: true, message: "ok" }),
  };
}

function renderCodexNeoPage({
  canWrite = true,
  mutationErrors = {},
  healthOverride,
}: {
  canWrite?: boolean;
  mutationErrors?: Record<string, Error>;
  healthOverride?: Partial<{
    overallStatus: string;
    items: Array<{
      key: string;
      label: string;
      status: string;
      message: string;
      detail?: string;
      copyValue?: string;
    }>;
  }>;
} = {}) {
  const settings = {
    codexApiBaseUrl: "http://127.0.0.1:2455/v1",
    codexgoApiBaseUrl: "https://codexgo.eu/api/codex-auth",
    codexgoAutoRefreshEnabled: true,
    codexgoAutoRefreshIntervalMinutes: 30,
    openaiActivityLogEnabled: true,
    managementActivityLogEnabled: false,
    codexHomeAutoRefreshEnabled: false,
    codexHomeAutoRefreshIntervalSeconds: 30,
    codexHomeAutoSyncEnabled: false,
    minimizeToTrayEnabled: false,
    startWithWindowsEnabled: false,
    buyerTokenSaved: true,
  };
  const accounts = {
    accounts: [
      {
        accountKey: "acct-active",
        email: "t01.036252.89@gmail.com",
        plan: "Pro",
        active: true,
        usage: {
          primary: { usedPercent: 98, remainingPercent: 2, resetsAt: "2026-06-22T18:23:00Z", windowMinutes: 300 },
          secondary: { usedPercent: 49, remainingPercent: 51, resetsAt: "2026-06-28T11:54:00Z", windowMinutes: 10080 },
        },
        codex: true,
        backup: true,
        api: true,
        apiHourCount: 2,
        apiDayCount: 7,
        availability: "Ready",
        status: "Fresh / just now",
      },
      {
        accountKey: "acct-backup",
        email: "backup@example.com",
        plan: "Plus",
        active: false,
        usage: {},
        codex: false,
        backup: true,
        api: true,
        apiHourCount: 0,
        apiDayCount: 0,
        availability: "Backup",
        status: "Stored / just now",
      },
      {
        accountKey: "acct-unknown",
        email: "unknown@example.com",
        plan: "Team",
        active: false,
        usage: {
          primary: { usedPercent: 11, remainingPercent: 89, resetsAt: "2026-06-22T18:23:00Z", windowMinutes: 300 },
          secondary: { usedPercent: 2, remainingPercent: 98, resetsAt: "2026-06-28T11:54:00Z", windowMinutes: 10080 },
        },
        codex: true,
        backup: false,
        api: true,
        apiHourCount: 0,
        apiDayCount: 0,
        availability: "Temp off",
        status: "Unknown / 3m ago",
      },
    ],
    activeAccountKey: "acct-active",
    registryPath: "C:\\Users\\rcgok\\.codex\\accounts\\registry.json",
    message: "Loaded 3 account(s) from Codex registry",
    codexAllEnabled: false,
    backupAllEnabled: true,
  };
  const health = {
    overallStatus: "ok",
    items: [
      {
        key: "codex_home",
        label: "Codex Home",
        status: "ok",
        message: "Detected",
        detail: "C:\\Users\\rcgok\\.codex",
        copyValue: "C:\\Users\\rcgok\\.codex",
      },
      {
        key: "accounts_sync",
        label: "Accounts sync",
        status: "error",
        message: "Mismatch",
        detail: "3 CodexNeo account(s), 1 Codex IB account(s)",
      },
      {
        key: "openai_bridge",
        label: "OpenAI bridge",
        status: "ok",
        message: "Configured",
        detail: "http://127.0.0.1:2455/v1",
        copyValue: "http://127.0.0.1:2455/v1",
      },
    ],
    ...healthOverride,
  };
  const mutations = {
    updateSettingsMutation: createMutationMock(),
    testApiMutation: createMutationMock(),
    setApiMutation: createMutationMock(),
    revertApiMutation: createMutationMock(),
    useAuthMutation: createMutationMock(),
    refreshAuthMutation: createMutationMock(),
    clearActivityLogMutation: createMutationMock(),
    saveCodexHomeMutation: createMutationMock(),
    resetCodexHomeMutation: createMutationMock(),
    selectCodexHomeMutation: createMutationMock(),
    openCodexHomeMutation: createMutationMock(),
    openDataFolderMutation: createMutationMock(),
    restartCodexMutation: createMutationMock(),
    importFileMutation: createMutationMock(),
    importFolderMutation: createMutationMock(),
    importFileUploadMutation: createMutationMock(),
    importFolderUploadMutation: createMutationMock(),
    exportAllMutation: createMutationMock(),
    exportSelectedMutation: createMutationMock(),
    markTempUnavailableMutation: createMutationMock(),
    markAvailableMutation: createMutationMock(),
    refreshSelectedMutation: createMutationMock(),
    syncAccountsMutation: createMutationMock(),
    setValidityDateMutation: createMutationMock(),
    clearValidityDateMutation: createMutationMock(),
    switchAccountMutation: createMutationMock(),
    deleteAccountsMutation: createMutationMock(),
    setAccountLocationMutation: createMutationMock(),
    setBulkLocationMutation: createMutationMock(),
  };
  for (const [name, error] of Object.entries(mutationErrors)) {
    if (name in mutations) {
      mutations[name as keyof typeof mutations].error = error;
    }
  }
  const accountsRefetch = vi.fn().mockResolvedValue({});
  const healthRefetch = vi.fn().mockResolvedValue({});
  hookMocks.useCodexNeo.mockReturnValue({
    settingsQuery: {
      data: settings,
      error: null,
      isPending: false,
      isFetching: false,
      refetch: vi.fn(),
    },
    activityLogQuery: {
      data: {
        contents:
          "[14:27:57] OpenAI API POST /v1/responses -> 200; model=gpt-5.5; account=t01.036.319.551@gmail.com; 8355ms.\n" +
          "[14:30:41] Management API POST /v1alpha/search -> 404; 0ms.\n",
      },
      error: null,
      isPending: false,
      isFetching: false,
      refetch: vi.fn(),
    },
    accountsQuery: {
      data: accounts,
      error: null,
      isPending: false,
      isFetching: false,
      refetch: accountsRefetch,
    },
    healthQuery: {
      data: health,
      error: null,
      isPending: false,
      isFetching: false,
      refetch: healthRefetch,
    },
    codexHomeQuery: {
      data: {
        codexHome: "C:\\Users\\rcgok\\.codex",
        defaultCodexHome: "C:\\Users\\rcgok\\.codex",
        dataDir: "H:\\Opencode IDE\\codex-ib\\codex-lb\\.data",
        customCodexHome: false,
        exists: true,
      },
      error: null,
      isPending: false,
      isFetching: false,
      refetch: vi.fn(),
    },
    ...mutations,
  });
  useAuthStore.setState({ canWrite });

  renderWithProviders(<CodexNeoPage />);

  return { settings, mutations, accountsRefetch, healthRefetch };
}

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({ canWrite: true });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("CodexNeoPage", () => {
  it("renders API auth and CodexGO controls without exposing a saved buyer token", () => {
    renderCodexNeoPage();

    expect(screen.getByRole("heading", { name: "CodexNeo" })).toBeInTheDocument();
    expect(screen.getByLabelText("Codex API URL")).toHaveValue("http://127.0.0.1:2455/v1");
    expect(screen.getByRole("button", { name: "Auth->API Test" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Auth->API Set" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Auth->API Revert" })).toBeInTheDocument();
    expect(screen.getByLabelText("CodexGO API refresh")).toBeChecked();
    expect(screen.getByLabelText("OpenAI log")).toBeChecked();
    expect(screen.getByLabelText("Management log")).not.toBeChecked();
    expect(screen.getByLabelText("Every (min)")).toHaveValue(30);
    expect(screen.getByLabelText("Buyer token")).toHaveValue("");
    expect(screen.getByText("Saved")).toBeInTheDocument();
    expect(screen.getByLabelText("URL")).toHaveValue("https://codexgo.eu/api/codex-auth");
    expect(screen.getByRole("button", { name: "Use auth" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh auth" })).toBeInTheDocument();
  });

  it("renders safe CodexNeo health diagnostics with copy actions", async () => {
    renderCodexNeoPage();

    const panel = screen.getByRole("region", { name: "Health diagnostics" });
    expect(within(panel).getByRole("heading", { name: "Health diagnostics" })).toBeInTheDocument();
    expect(within(panel).getByText("Codex Home")).toBeInTheDocument();
    expect(within(panel).getByText("Detected")).toBeInTheDocument();
    expect(within(panel).getByText("Accounts sync")).toBeInTheDocument();
    expect(within(panel).getByText("Mismatch")).toBeInTheDocument();
    expect(within(panel).getByText("3 CodexNeo account(s), 1 Codex IB account(s)")).toBeInTheDocument();
    expect(within(panel).getByText("OpenAI bridge")).toBeInTheDocument();
    expect(within(panel).queryByText(/token/i)).not.toBeInTheDocument();

    const copyButton = screen.getByRole("button", { name: "Copy Codex Home" });
    expect(copyButton).toHaveAttribute("data-copy-value", "C:\\Users\\rcgok\\.codex");
  });

  it("does not show stale action errors as a persistent page load error", () => {
    renderCodexNeoPage({
      mutationErrors: {
        exportSelectedMutation: new Error("Unexpected error"),
      },
    });

    expect(screen.queryByText("Unexpected error")).not.toBeInTheDocument();
    expect(screen.getByText("Loaded 3 account(s) from Codex registry")).toBeInTheDocument();
  });

  it("renders the Codex home accounts table with usage and safe status fields", () => {
    renderCodexNeoPage();

    expect(screen.getByRole("heading", { name: "Codex Home Accounts" })).toBeInTheDocument();
    expect(screen.getByText("Loaded 3 account(s) from Codex registry")).toBeInTheDocument();
    expect(screen.getByText("t01.036252.89@gmail.com")).toBeInTheDocument();
    expect(screen.getByText("backup@example.com")).toBeInTheDocument();
    expect(screen.getByText("unknown@example.com")).toBeInTheDocument();
    expect(screen.getByText("2%")).toBeInTheDocument();
    expect(screen.getByText("51%")).toBeInTheDocument();
    expect(screen.getByText("Fresh / just now")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "API" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "API h" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "API d" })).not.toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Avail" })).toBeInTheDocument();
    expect(within(screen.getByRole("row", { name: /t01\.036252\.89@gmail\.com/ })).getByText("Ready")).toBeInTheDocument();
    expect(within(screen.getByRole("row", { name: /backup@example\.com/ })).getByText("Backup")).toBeInTheDocument();
    expect(screen.queryByText("secret-access")).not.toBeInTheDocument();
  });

  it("renders activity log contents and clears through the clear button", async () => {
    const user = userEvent.setup();
    const { mutations } = renderCodexNeoPage();

    expect(screen.getByRole("heading", { name: "Activity log" })).toBeInTheDocument();
    expect(screen.getByText(/OpenAI API POST \/v1\/responses -> 200/)).toBeInTheDocument();
    expect(screen.getByText(/Management API POST \/v1alpha\/search -> 404/)).toBeInTheDocument();
    expect(screen.getByTestId("codexneo-activity-log")).toHaveClass("max-h-80");
    expect(screen.getByTestId("codexneo-activity-log")).toHaveClass("overflow-auto");

    await user.click(screen.getByRole("button", { name: "Clear" }));

    expect(mutations.clearActivityLogMutation.mutateAsync).toHaveBeenCalledTimes(1);
  });

  it("renders Codex home and import/export controls", async () => {
    const user = userEvent.setup();
    const { mutations } = renderCodexNeoPage();

    expect(screen.getByLabelText("Codex home")).toHaveValue("C:\\Users\\rcgok\\.codex");
    expect(screen.getByRole("button", { name: "Select Codex home" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reset Codex home" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Data folder" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Import file" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Import folder" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Export all" })).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Codex home"));
    await user.type(screen.getByLabelText("Codex home"), "D:\\CodexHome");
    await user.click(screen.getByRole("button", { name: "Save Codex home" }));
    await user.click(screen.getByRole("button", { name: "Export all" }));

    expect(mutations.saveCodexHomeMutation.mutateAsync).toHaveBeenCalledWith({ codexHome: "D:\\CodexHome" });
    expect(mutations.exportAllMutation.mutateAsync).toHaveBeenCalledWith({ path: "" });
  });

  it("uses browser file inputs for empty-path import buttons", async () => {
    const user = userEvent.setup();
    const { mutations } = renderCodexNeoPage();
    const file = new File(['{"tokens":{}}'], "auth.json", { type: "application/json" });

    await user.click(screen.getByRole("button", { name: "Import file" }));
    await user.upload(screen.getByLabelText("Choose import file"), file);

    expect(mutations.importFileUploadMutation.mutateAsync).toHaveBeenCalledWith({ file });
    expect(mutations.importFileMutation.mutateAsync).not.toHaveBeenCalled();

    const folderFile = new File(['{"tokens":{}}'], "folder-auth.json", { type: "application/json" });
    Object.defineProperty(folderFile, "webkitRelativePath", { value: "accounts/folder-auth.json" });

    await user.click(screen.getByRole("button", { name: "Import folder" }));
    await user.upload(screen.getByLabelText("Choose import folder"), folderFile);

    expect(mutations.importFolderUploadMutation.mutateAsync).toHaveBeenCalledWith({ files: [folderFile] });
    expect(mutations.importFolderMutation.mutateAsync).not.toHaveBeenCalled();
  });

  it("runs remaining selected account actions without browser confirmations", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    const { mutations, accountsRefetch } = renderCodexNeoPage();

    await user.click(screen.getByLabelText("Select t01.036252.89@gmail.com"));
    expect(screen.queryByRole("button", { name: "Use API" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Temp unavailable" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark available" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Switch" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Switch & Restart" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Refresh selected" }));
    await user.click(screen.getByRole("button", { name: "Delete selected" }));

    expect(accountsRefetch).not.toHaveBeenCalled();
    expect(mutations.refreshSelectedMutation.mutateAsync).toHaveBeenCalledWith({ accountKeys: ["acct-active"] });
    expect(mutations.markTempUnavailableMutation.mutateAsync).not.toHaveBeenCalled();
    expect(mutations.markAvailableMutation.mutateAsync).not.toHaveBeenCalled();
    expect(mutations.setValidityDateMutation.mutateAsync).not.toHaveBeenCalled();
    expect(mutations.clearValidityDateMutation.mutateAsync).not.toHaveBeenCalled();
    expect(mutations.switchAccountMutation.mutateAsync).not.toHaveBeenCalled();
    expect(mutations.deleteAccountsMutation.mutateAsync).toHaveBeenCalledWith({ accountKeys: ["acct-active"] });
    expect(confirmSpy).not.toHaveBeenCalled();
  });

  it("organizes Codex Home account controls in the requested order", () => {
    renderCodexNeoPage();

    const groups = Array.from(screen.getByTestId("codex-home-account-controls").children).map((element) =>
      element.textContent?.replace(/\s+/g, " ").trim() ?? "",
    );

    expect(groups).toHaveLength(7);
    expect(groups[0]).toContain("Auto refresh Codex Home");
    expect(groups[0]).toContain("Every (sec)");
    expect(groups[1]).toContain("Codex home");
    expect(groups[1]).toContain("Mismatch");
    expect(groups[2]).toContain("Auto sync Codex IB");
    expect(groups[3]).toContain("Codex IB");
    expect(groups[3]).toContain("Refresh");
    expect(groups[3]).toContain("Sync");
    expect(groups[4]).toContain("Minimize to tray");
    expect(groups[5]).toContain("Start with Windows");
    expect(groups[6]).toContain("Minimize all");
  });

  it("selects every visible account row without changing location checkboxes", async () => {
    const user = userEvent.setup();
    const { mutations } = renderCodexNeoPage();

    await user.click(screen.getByRole("button", { name: "Select all" }));

    expect(screen.getByLabelText("Select t01.036252.89@gmail.com")).toBeChecked();
    expect(screen.getByLabelText("Select backup@example.com")).toBeChecked();
    expect(screen.getByRole("button", { name: "Export selected" })).toBeEnabled();
    expect(screen.getByLabelText("Codex t01.036252.89@gmail.com")).toBeChecked();
    expect(screen.getByLabelText("Codex backup@example.com")).not.toBeChecked();
    expect(mutations.setAccountLocationMutation.mutateAsync).not.toHaveBeenCalled();
    expect(mutations.setBulkLocationMutation.mutateAsync).not.toHaveBeenCalled();
  });

  it("uses Select all as an Unselect all toggle when all visible rows are selected", async () => {
    const user = userEvent.setup();
    renderCodexNeoPage();

    await user.click(screen.getByRole("button", { name: "Select all" }));
    expect(screen.getByRole("button", { name: "Unselect all" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Unselect all" }));

    expect(screen.getByLabelText("Select t01.036252.89@gmail.com")).not.toBeChecked();
    expect(screen.getByLabelText("Select backup@example.com")).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Export selected" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Select all" })).toBeInTheDocument();
  });

  it("keeps sortable headers compact without visible sort-state labels", async () => {
    const user = userEvent.setup();
    renderCodexNeoPage();

    expect(screen.queryByText("SORT")).not.toBeInTheDocument();
    expect(screen.queryByText("ASC")).not.toBeInTheDocument();
    expect(screen.queryByText("DESC")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Sort by #" }));

    expect(screen.queryByText("SORT")).not.toBeInTheDocument();
    expect(screen.queryByText("ASC")).not.toBeInTheDocument();
    expect(screen.queryByText("DESC")).not.toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "#" })).toHaveAttribute("aria-sort", "ascending");
  });

  it("sorts account rows by number, plan, usage, availability, and status without clearing selection", async () => {
    const user = userEvent.setup();
    renderCodexNeoPage();

    const rowEmails = () =>
      screen
        .getAllByRole("row")
        .slice(1)
        .map((row) => within(row).getAllByRole("cell")[2].textContent);

    expect(screen.getByRole("columnheader", { name: "#" })).toBeInTheDocument();

    await user.click(screen.getByLabelText("Select backup@example.com"));
    await user.click(screen.getByRole("button", { name: "Sort by #" }));
    await user.click(screen.getByRole("button", { name: "Sort by #" }));
    expect(rowEmails()).toEqual(["unknown@example.com", "backup@example.com", "t01.036252.89@gmail.com"]);
    expect(screen.getByLabelText("Select backup@example.com")).toBeChecked();

    await user.click(screen.getByRole("button", { name: "Sort by Plan" }));
    expect(rowEmails()).toEqual(["backup@example.com", "t01.036252.89@gmail.com", "unknown@example.com"]);

    await user.click(screen.getByRole("button", { name: "Sort by 5h" }));
    expect(rowEmails()).toEqual(["backup@example.com", "t01.036252.89@gmail.com", "unknown@example.com"]);

    await user.click(screen.getByRole("button", { name: "Sort by Weekly" }));
    expect(rowEmails()).toEqual(["backup@example.com", "t01.036252.89@gmail.com", "unknown@example.com"]);

    await user.click(screen.getByRole("button", { name: "Sort by Avail" }));
    expect(rowEmails()).toEqual(["t01.036252.89@gmail.com", "backup@example.com", "unknown@example.com"]);

    await user.click(screen.getByRole("button", { name: "Sort by Status / Last" }));
    expect(rowEmails()).toEqual(["t01.036252.89@gmail.com", "backup@example.com", "unknown@example.com"]);
  });

  it("shows feedback when the Codex home accounts refresh button is clicked", async () => {
    const user = userEvent.setup();
    const { accountsRefetch, healthRefetch } = renderCodexNeoPage();

    await user.click(screen.getByRole("button", { name: "Refresh" }));

    expect(accountsRefetch).toHaveBeenCalledTimes(1);
    expect(healthRefetch).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Last refreshed just now")).toBeInTheDocument();
  });

  it("auto-refreshes Codex home accounts and diagnostics on the configured seconds interval", async () => {
    vi.useFakeTimers();
    const { accountsRefetch, healthRefetch } = renderCodexNeoPage();

    expect(screen.getByLabelText("Codex Home refresh seconds")).toHaveValue(30);
    fireEvent.click(screen.getByLabelText("Auto refresh Codex Home"));
    await act(async () => {
      vi.advanceTimersByTime(30_000);
    });

    expect(accountsRefetch).toHaveBeenCalledTimes(1);
    expect(healthRefetch).toHaveBeenCalledTimes(1);
  });

  it("persists Codex home refresh and sync preferences as they change", async () => {
    const user = userEvent.setup();
    const { mutations } = renderCodexNeoPage();

    await user.click(screen.getByLabelText("Auto refresh Codex Home"));
    await user.clear(screen.getByLabelText("Codex Home refresh seconds"));
    await user.type(screen.getByLabelText("Codex Home refresh seconds"), "45");
    fireEvent.blur(screen.getByLabelText("Codex Home refresh seconds"));
    await user.click(screen.getByLabelText("Auto sync Codex IB"));

    expect(mutations.updateSettingsMutation.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ codexHomeAutoRefreshEnabled: true }),
    );
    expect(mutations.updateSettingsMutation.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ codexHomeAutoRefreshIntervalSeconds: 45 }),
    );
    expect(mutations.updateSettingsMutation.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ codexHomeAutoSyncEnabled: true }),
    );
  });

  it("renders a persisted minimize to tray preference and sends an Electron minimize request", async () => {
    const user = userEvent.setup();
    const minimizeToTray = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(window, "codexIbElectron", {
      configurable: true,
      value: { minimizeToTray },
    });
    const { mutations } = renderCodexNeoPage();

    await user.click(screen.getByLabelText("Minimize to tray"));
    await user.click(screen.getByRole("button", { name: "Minimize all" }));

    expect(mutations.updateSettingsMutation.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ minimizeToTrayEnabled: true }),
    );
    expect(minimizeToTray).toHaveBeenCalledWith({ toTray: true });
  });

  it("persists Start with Windows and registers it through Electron", async () => {
    const user = userEvent.setup();
    const setStartWithWindowsEnabled = vi.fn().mockResolvedValue(true);
    Object.defineProperty(window, "codexIbElectron", {
      configurable: true,
      value: { setStartWithWindowsEnabled },
    });
    const { mutations } = renderCodexNeoPage();

    await user.click(screen.getByLabelText("Start with Windows"));

    expect(mutations.updateSettingsMutation.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ startWithWindowsEnabled: true }),
    );
    expect(setStartWithWindowsEnabled).toHaveBeenCalledWith(true);
  });

  it("runs explicit two-way sync from the Codex Home Accounts toolbar", async () => {
    const user = userEvent.setup();
    const { mutations } = renderCodexNeoPage();

    await user.click(screen.getByRole("button", { name: "Sync" }));

    expect(mutations.syncAccountsMutation.mutateAsync).toHaveBeenCalledWith();
  });

  it("runs automatic sync when enabled and the diagnostics show an account mismatch", async () => {
    const user = userEvent.setup();
    const { mutations } = renderCodexNeoPage({
      healthOverride: {
        overallStatus: "error",
        items: [
          {
            key: "accounts_sync",
            label: "Accounts sync",
            status: "error",
            message: "Mismatch",
            detail: "3 CodexNeo account(s), 1 Codex IB account(s)",
          },
        ],
      },
    });

    expect(screen.getAllByText("Mismatch").length).toBeGreaterThanOrEqual(1);

    await user.click(screen.getByLabelText("Auto sync Codex IB"));

    expect(mutations.syncAccountsMutation.mutateAsync).toHaveBeenCalledTimes(1);
  });

  it("keeps selected actions and account row actions in stable layout groups", () => {
    renderCodexNeoPage();

    expect(screen.getByTestId("codexneo-account-actions")).toHaveClass("flex");
    expect(screen.getByTestId("codexneo-accounts-table")).toHaveClass("min-w-[72rem]");
    expect(screen.getByTestId("account-row-actions-acct-active")).toHaveClass("flex-nowrap");
    expect(screen.getByTestId("account-row-actions-acct-backup")).toHaveClass("flex-nowrap");
  });

  it("does not render selected-account validity controls", () => {
    renderCodexNeoPage();

    expect(screen.queryByLabelText("Validity date")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Set validity date" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Clear validity date" })).not.toBeInTheDocument();
  });

  it("renders Codex and Backup location checkboxes with bulk toggles", async () => {
    const user = userEvent.setup();
    const { mutations } = renderCodexNeoPage();

    const activeRow = screen.getByRole("row", { name: /t01\.036252\.89@gmail\.com/ });
    const backupRow = screen.getByRole("row", { name: /backup@example\.com/ });

    expect(screen.getByLabelText("Codex all")).not.toBeChecked();
    expect(screen.getByLabelText("Backup all")).toBeChecked();
    expect(within(activeRow).getByLabelText("Codex t01.036252.89@gmail.com")).toBeChecked();
    expect(within(activeRow).getByLabelText("Backup t01.036252.89@gmail.com")).toBeChecked();
    expect(within(backupRow).getByLabelText("Codex backup@example.com")).not.toBeChecked();
    expect(within(backupRow).getByLabelText("Backup backup@example.com")).toBeChecked();

    await user.click(within(activeRow).getByLabelText("Backup t01.036252.89@gmail.com"));
    await user.click(screen.getByLabelText("Codex all"));

    expect(mutations.setAccountLocationMutation.mutateAsync).toHaveBeenCalledWith({
      accountKeys: ["acct-active"],
      location: "backup",
      present: false,
    });
    expect(mutations.setBulkLocationMutation.mutateAsync).toHaveBeenCalledWith({
      location: "codex",
      present: true,
    });
  });

  it("runs per-row account actions with the row account key", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    const { mutations } = renderCodexNeoPage();

    const backupRow = screen.getByRole("row", { name: /backup@example\.com/ });
    await user.click(within(backupRow).getByRole("button", { name: "Switch backup@example.com" }));
    await user.click(within(backupRow).getByRole("button", { name: "Switch & Restart backup@example.com" }));

    expect(within(backupRow).queryByRole("button", { name: "Use API backup@example.com" })).not.toBeInTheDocument();
    expect(mutations.switchAccountMutation.mutateAsync).toHaveBeenCalledWith({
      accountKey: "acct-backup",
      restart: false,
    });
    expect(mutations.switchAccountMutation.mutateAsync).toHaveBeenCalledWith({
      accountKey: "acct-backup",
      restart: true,
    });
    expect(confirmSpy).not.toHaveBeenCalled();
  });

  it("runs Restart Codex directly without a browser confirmation", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    const { mutations } = renderCodexNeoPage();

    await user.click(screen.getByRole("button", { name: "Restart Codex" }));

    expect(mutations.restartCodexMutation.mutateAsync).toHaveBeenCalledTimes(1);
    expect(confirmSpy).not.toHaveBeenCalled();
  });

  it("calls the CodexGO mutations from the action buttons", async () => {
    const user = userEvent.setup();
    const { mutations } = renderCodexNeoPage();

    await user.click(screen.getByRole("button", { name: "Use auth" }));
    await user.click(screen.getByRole("button", { name: "Refresh auth" }));

    expect(mutations.useAuthMutation.mutateAsync).toHaveBeenCalledTimes(1);
    expect(mutations.refreshAuthMutation.mutateAsync).toHaveBeenCalledTimes(1);
  });

  it("disables mutating controls for read-only users", () => {
    renderCodexNeoPage({ canWrite: false });

    expect(screen.getByText("You are viewing the dashboard with read-only guest access.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Auth->API Test" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Auth->API Set" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Auth->API Revert" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Use auth" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Refresh auth" })).toBeDisabled();
    expect(screen.getByLabelText("Buyer token")).toBeDisabled();
  });
});
