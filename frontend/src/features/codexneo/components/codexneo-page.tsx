import {
  CircleAlert,
  CircleCheck,
  CircleHelp,
  Copy,
  ListChecks,
  RefreshCw,
  RotateCcw,
  Save,
  ShieldCheck,
  TestTubeDiagonal,
  Minus,
  Zap,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type MouseEvent,
  type PointerEvent,
} from "react";
import { toast } from "sonner";

import { AlertMessage } from "@/components/alert-message";
import { CodexLogo } from "@/components/brand/codex-logo";
import { LoadingOverlay } from "@/components/layout/loading-overlay";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useAuthStore } from "@/features/auth/hooks/use-auth";
import { useCodexNeo } from "@/features/codexneo/hooks/use-codexneo";
import type {
  CodexNeoAccountRow,
  CodexNeoHealthItem,
  CodexNeoSettingsUpdateRequest,
} from "@/features/codexneo/schemas";
import { getErrorMessageOrNull } from "@/utils/errors";

import { applyAccountSelectionRange } from "./account-selection";
import { CodexNeoActivityPage } from "./codexneo-activity-page";

const DEFAULT_INTERVAL_MINUTES = 30;
const DEFAULT_CODEX_HOME_REFRESH_SECONDS = 30;
const MIN_CODEX_HOME_REFRESH_SECONDS = 5;
const MAX_CODEX_HOME_REFRESH_SECONDS = 3600;
type AccountSortKey = "number" | "plan" | "fiveHour" | "weekly" | "availability" | "status";
type AccountSortDirection = "asc" | "desc";
type AccountSortState = { key: AccountSortKey; direction: AccountSortDirection } | null;
type AccountTableRow = { account: CodexNeoAccountRow; sourceNumber: number };
type CodexNeoView = "accounts" | "activity";

export function CodexNeoPage() {
  const canWrite = useAuthStore((state) => state.canWrite);
  const {
    settingsQuery,
    updateSettingsMutation,
    testApiMutation,
    setApiMutation,
    revertApiMutation,
    useAuthMutation,
    refreshAuthMutation,
    activityLogQuery,
    accountsQuery,
    healthQuery,
    clearActivityLogMutation,
    codexHomeQuery,
    saveCodexHomeMutation,
    resetCodexHomeMutation,
    selectCodexHomeMutation,
    openCodexHomeMutation,
    openDataFolderMutation,
    restartCodexMutation,
    importFolderMutation,
    importFolderUploadMutation,
    exportSelectedMutation,
    refreshSelectedMutation,
    syncAccountsMutation,
    autoDeleteFreeReauthAccountsMutation,
    autoDeleteQuotaExceededAccountsMutation,
    switchAccountMutation,
    deleteAccountsMutation,
    setAccountLocationMutation,
    setBulkLocationMutation,
  } = useCodexNeo();
  const settings = settingsQuery.data;
  const activityLog = activityLogQuery.data;
  const accounts = accountsQuery.data;
  const health = healthQuery.data;
  const codexHome = codexHomeQuery.data;
  const [codexApiBaseUrlOverride, setCodexApiBaseUrlOverride] = useState<string | null>(null);
  const [codexgoApiBaseUrlOverride, setCodexgoApiBaseUrlOverride] = useState<string | null>(null);
  const [codexHomePathOverride, setCodexHomePathOverride] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<CodexNeoView>("accounts");
  const [importFolderPath, setImportFolderPath] = useState("");
  const [exportDestination, setExportDestination] = useState("");
  const [selectedAccountKeys, setSelectedAccountKeys] = useState<string[]>([]);
  const [autoRefreshEnabledOverride, setAutoRefreshEnabledOverride] = useState<boolean | null>(null);
  const [intervalMinutesOverride, setIntervalMinutesOverride] = useState<number | null>(null);
  const [buyerToken, setBuyerToken] = useState("");
  const [accountsRefreshFeedback, setAccountsRefreshFeedback] = useState<string | null>(null);
  const [accountSort, setAccountSort] = useState<AccountSortState>(null);
  const [codexHomeAutoRefreshEnabledOverride, setCodexHomeAutoRefreshEnabledOverride] = useState<boolean | null>(null);
  const [codexHomeRefreshSecondsOverride, setCodexHomeRefreshSecondsOverride] = useState<number | null>(null);
  const [codexHomeAutoSyncEnabledOverride, setCodexHomeAutoSyncEnabledOverride] = useState<boolean | null>(null);
  const [autoDeleteFreeReauthEnabledOverride, setAutoDeleteFreeReauthEnabledOverride] = useState<boolean | null>(null);
  const [autoDeleteQuotaExceededEnabledOverride, setAutoDeleteQuotaExceededEnabledOverride] = useState<boolean | null>(
    null,
  );
  const [minimizeToTrayEnabledOverride, setMinimizeToTrayEnabledOverride] = useState<boolean | null>(null);
  const [startWithWindowsEnabledOverride, setStartWithWindowsEnabledOverride] = useState<boolean | null>(null);
  const [autoSyncFeedback, setAutoSyncFeedback] = useState<string | null>(null);
  const [restartPending, setRestartPending] = useState(false);
  const importFolderInputRef = useRef<HTMLInputElement | null>(null);
  const lastSelectedAccountKeyRef = useRef<string | null>(null);
  const shiftRangeSelectActiveRef = useRef(false);
  const autoSyncSignatureRef = useRef<string | null>(null);
  const autoDeleteSignatureRef = useRef<string | null>(null);
  const autoDeleteQuotaExceededSignatureRef = useRef<string | null>(null);
  const codexApiBaseUrl = codexApiBaseUrlOverride ?? settings?.codexApiBaseUrl ?? "";
  const codexgoApiBaseUrl = codexgoApiBaseUrlOverride ?? settings?.codexgoApiBaseUrl ?? "";
  const codexHomePath = codexHomePathOverride ?? codexHome?.codexHome ?? "";
  const autoRefreshEnabled = autoRefreshEnabledOverride ?? settings?.codexgoAutoRefreshEnabled ?? false;
  const intervalMinutes = intervalMinutesOverride ?? settings?.codexgoAutoRefreshIntervalMinutes ?? DEFAULT_INTERVAL_MINUTES;
  const electronApi = typeof window === "undefined" ? undefined : window.codexIbElectron;
  const electronControlsAvailable = Boolean(electronApi?.minimizeToTray);
  const restartAvailable = Boolean(electronApi?.restartApp);
  const codexHomeAutoRefreshEnabled =
    codexHomeAutoRefreshEnabledOverride ?? settings?.codexHomeAutoRefreshEnabled ?? false;
  const codexHomeRefreshSeconds =
    codexHomeRefreshSecondsOverride ??
    settings?.codexHomeAutoRefreshIntervalSeconds ??
    DEFAULT_CODEX_HOME_REFRESH_SECONDS;
  const codexHomeAutoSyncEnabled = codexHomeAutoSyncEnabledOverride ?? settings?.codexHomeAutoSyncEnabled ?? false;
  const autoDeleteFreeReauthEnabled =
    autoDeleteFreeReauthEnabledOverride ?? settings?.autoDeleteFreeReauthAccountsEnabled ?? false;
  const autoDeleteQuotaExceededEnabled =
    autoDeleteQuotaExceededEnabledOverride ?? settings?.autoDeleteQuotaExceededAccountsEnabled ?? false;
  const minimizeToTrayEnabled = minimizeToTrayEnabledOverride ?? settings?.minimizeToTrayEnabled ?? false;
  const startWithWindowsEnabled = startWithWindowsEnabledOverride ?? settings?.startWithWindowsEnabled ?? false;

  const busy =
    settingsQuery.isPending ||
    activityLogQuery.isPending ||
    accountsQuery.isPending ||
    codexHomeQuery.isPending ||
    updateSettingsMutation.isPending ||
    testApiMutation.isPending ||
    setApiMutation.isPending ||
    revertApiMutation.isPending ||
    useAuthMutation.isPending ||
    refreshAuthMutation.isPending ||
    clearActivityLogMutation.isPending ||
    saveCodexHomeMutation.isPending ||
    resetCodexHomeMutation.isPending ||
    selectCodexHomeMutation.isPending ||
    openCodexHomeMutation.isPending ||
    openDataFolderMutation.isPending ||
    restartCodexMutation.isPending ||
    importFolderMutation.isPending ||
    importFolderUploadMutation.isPending ||
    exportSelectedMutation.isPending ||
    refreshSelectedMutation.isPending ||
    syncAccountsMutation.isPending ||
    autoDeleteFreeReauthAccountsMutation.isPending ||
    autoDeleteQuotaExceededAccountsMutation.isPending ||
    switchAccountMutation.isPending ||
    deleteAccountsMutation.isPending ||
    setAccountLocationMutation.isPending ||
    setBulkLocationMutation.isPending;
  const controlsDisabled = busy || !canWrite;
  const error =
    getErrorMessageOrNull(settingsQuery.error) ||
    getErrorMessageOrNull(activityLogQuery.error) ||
    getErrorMessageOrNull(accountsQuery.error) ||
    getErrorMessageOrNull(codexHomeQuery.error);
  const updatePayload = useMemo<CodexNeoSettingsUpdateRequest>(() => {
    const payload: CodexNeoSettingsUpdateRequest = {
      codexApiBaseUrl,
      codexgoApiBaseUrl,
      codexgoAutoRefreshEnabled: autoRefreshEnabled,
      codexgoAutoRefreshIntervalMinutes: intervalMinutes,
      codexHomeAutoRefreshEnabled,
      codexHomeAutoRefreshIntervalSeconds: clampCodexHomeRefreshSeconds(codexHomeRefreshSeconds),
      codexHomeAutoSyncEnabled,
      autoDeleteFreeReauthAccountsEnabled: autoDeleteFreeReauthEnabled,
      autoDeleteQuotaExceededAccountsEnabled: autoDeleteQuotaExceededEnabled,
      minimizeToTrayEnabled,
      startWithWindowsEnabled,
    };
    if (buyerToken.trim()) {
      payload.buyerToken = buyerToken.trim();
    }
    return payload;
  }, [
    autoRefreshEnabled,
    buyerToken,
    codexApiBaseUrl,
    codexHomeAutoRefreshEnabled,
    codexHomeAutoSyncEnabled,
    autoDeleteFreeReauthEnabled,
    autoDeleteQuotaExceededEnabled,
    codexHomeRefreshSeconds,
    codexgoApiBaseUrl,
    intervalMinutes,
    minimizeToTrayEnabled,
    startWithWindowsEnabled,
  ]);

  const saveSettings = async () => {
    await updateSettingsMutation.mutateAsync(updatePayload);
    setBuyerToken("");
  };

  const runCodexGoAction = async (action: "use" | "refresh") => {
    await updateSettingsMutation.mutateAsync(updatePayload);
    setBuyerToken("");
    if (action === "use") {
      await useAuthMutation.mutateAsync();
      return;
    }
    await refreshAuthMutation.mutateAsync();
  };
  useEffect(() => {
    void electronApi?.setMinimizeToTrayEnabled?.(minimizeToTrayEnabled);
  }, [electronApi, minimizeToTrayEnabled]);
  useEffect(() => {
    void electronApi?.setStartWithWindowsEnabled?.(startWithWindowsEnabled);
  }, [electronApi, startWithWindowsEnabled]);
  const persistCodexNeoSetting = (payload: CodexNeoSettingsUpdateRequest) => {
    void updateSettingsMutation.mutateAsync(payload);
  };
  const setPersistentCodexHomeAutoRefreshEnabled = (checked: boolean) => {
    setCodexHomeAutoRefreshEnabledOverride(checked);
    persistCodexNeoSetting({ codexHomeAutoRefreshEnabled: checked });
  };
  const setPersistentCodexHomeAutoSyncEnabled = (checked: boolean) => {
    setCodexHomeAutoSyncEnabledOverride(checked);
    persistCodexNeoSetting({ codexHomeAutoSyncEnabled: checked });
  };
  const setPersistentAutoDeleteFreeReauthEnabled = (checked: boolean) => {
    setAutoDeleteFreeReauthEnabledOverride(checked);
    persistCodexNeoSetting({ autoDeleteFreeReauthAccountsEnabled: checked });
  };
  const setPersistentAutoDeleteQuotaExceededEnabled = (checked: boolean) => {
    setAutoDeleteQuotaExceededEnabledOverride(checked);
    persistCodexNeoSetting({ autoDeleteQuotaExceededAccountsEnabled: checked });
  };
  const saveCodexHomeRefreshSeconds = () => {
    const clamped = clampCodexHomeRefreshSeconds(codexHomeRefreshSeconds);
    setCodexHomeRefreshSecondsOverride(clamped);
    persistCodexNeoSetting({ codexHomeAutoRefreshIntervalSeconds: clamped });
  };
  const setPersistentMinimizeToTrayEnabled = (checked: boolean) => {
    setMinimizeToTrayEnabledOverride(checked);
    void electronApi?.setMinimizeToTrayEnabled?.(checked);
    persistCodexNeoSetting({ minimizeToTrayEnabled: checked });
  };
  const setPersistentStartWithWindowsEnabled = (checked: boolean) => {
    setStartWithWindowsEnabledOverride(checked);
    void electronApi?.setStartWithWindowsEnabled?.(checked);
    persistCodexNeoSetting({ startWithWindowsEnabled: checked });
  };
  const minimizeWindow = () => {
    void electronApi?.minimizeToTray({ toTray: minimizeToTrayEnabled });
  };
  const accountRows = useMemo<AccountTableRow[]>(
    () => (accounts?.accounts ?? []).map((account, index) => ({ account, sourceNumber: index + 1 })),
    [accounts?.accounts],
  );
  const sortedAccountRows = useMemo(
    () => sortAccountRows(accountRows, accountSort),
    [accountRows, accountSort],
  );
  const autoDeleteSignature = useMemo(
    () =>
      (accounts?.accounts ?? [])
        .map((account) => `${account.accountKey}:${account.plan ?? ""}:${account.codexIbStatus ?? ""}`)
        .sort()
        .join("|"),
    [accounts?.accounts],
  );
  const autoDeleteQuotaExceededSignature = useMemo(
    () =>
      (accounts?.accounts ?? [])
        .map((account) => {
          const weeklyRemaining = account.usage.secondary?.remainingPercent ?? "";
          return `${account.accountKey}:${account.codexIbStatus ?? ""}:${account.backup}:${weeklyRemaining}`;
        })
        .sort()
        .join("|"),
    [accounts?.accounts],
  );
  const visibleAccountKeys = useMemo(
    () => sortedAccountRows.map(({ account }) => account.accountKey),
    [sortedAccountRows],
  );
  const selectedAccounts = useMemo(
    () => selectedAccountKeys.filter((key) => visibleAccountKeys.includes(key)),
    [selectedAccountKeys, visibleAccountKeys],
  );
  const allVisibleAccountsSelected =
    visibleAccountKeys.length > 0 && visibleAccountKeys.every((key) => selectedAccounts.includes(key));
  const accountsSyncDiagnostic = health?.items.find((item) => item.key === "accounts_sync");
  const accountsSyncMismatch = accountsSyncDiagnostic?.status === "error";
  const accountsSyncSignature = `${accountsSyncDiagnostic?.message ?? ""}|${accountsSyncDiagnostic?.detail ?? ""}`;
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Shift") shiftRangeSelectActiveRef.current = true;
    };
    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.key === "Shift") shiftRangeSelectActiveRef.current = false;
    };
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("keyup", handleKeyUp);
      shiftRangeSelectActiveRef.current = false;
    };
  }, []);
  const toggleAccount = (accountKey: string, checked: boolean, rangeSelect = false) => {
    const anchorKey = lastSelectedAccountKeyRef.current;
    const shouldRangeSelect = rangeSelect || shiftRangeSelectActiveRef.current;
    setSelectedAccountKeys((current) => {
      return applyAccountSelectionRange({
        current,
        visible: visibleAccountKeys,
        accountKey,
        checked,
        rangeSelect: shouldRangeSelect,
        anchorKey,
      });
    });
    lastSelectedAccountKeyRef.current = accountKey;
  };
  const runImportFolder = async () => {
    if (importFolderPath.trim()) {
      await importFolderMutation.mutateAsync({ path: importFolderPath });
      return;
    }
    importFolderInputRef.current?.click();
  };
  const handleImportFolderSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.currentTarget.files ?? []).filter((file) => {
      const relativePath = "webkitRelativePath" in file ? String(file.webkitRelativePath) : "";
      return file.name.toLowerCase().endsWith(".json") || relativePath.toLowerCase().endsWith(".json");
    });
    event.currentTarget.value = "";
    if (files.length === 0) return;
    await importFolderUploadMutation.mutateAsync({ files });
  };
  const directoryInputAttributes = { directory: "", webkitdirectory: "" } as Record<string, string>;
  const refreshAccounts = useCallback(async () => {
    setAccountsRefreshFeedback("Refreshing accounts...");
    try {
      await Promise.all([accountsQuery.refetch(), healthQuery.refetch()]);
      setAccountsRefreshFeedback("Last refreshed just now");
    } catch (error) {
      setAccountsRefreshFeedback("Refresh failed");
      throw error;
    }
  }, [accountsQuery, healthQuery]);
  useEffect(() => {
    if (!codexHomeAutoRefreshEnabled) return;
    const refreshSeconds = clampCodexHomeRefreshSeconds(codexHomeRefreshSeconds);
    const intervalId = window.setInterval(() => {
      void refreshAccounts();
    }, refreshSeconds * 1000);
    return () => window.clearInterval(intervalId);
  }, [codexHomeAutoRefreshEnabled, codexHomeRefreshSeconds, refreshAccounts]);
  useEffect(() => {
    if (!accountsSyncMismatch) {
      autoSyncSignatureRef.current = null;
      return;
    }
    if (!codexHomeAutoSyncEnabled || syncAccountsMutation.isPending || !canWrite) return;
    if (autoSyncSignatureRef.current === accountsSyncSignature) return;
    autoSyncSignatureRef.current = accountsSyncSignature;
    setAutoSyncFeedback("Auto sync running...");
    void syncAccountsMutation
      .mutateAsync()
      .then(() => setAutoSyncFeedback("Auto sync completed just now"))
      .catch(() => setAutoSyncFeedback("Auto sync failed"));
  }, [
    accountsSyncMismatch,
    accountsSyncSignature,
    canWrite,
    codexHomeAutoSyncEnabled,
    syncAccountsMutation,
  ]);
  useEffect(() => {
    if (
      !autoDeleteFreeReauthEnabled ||
      autoDeleteFreeReauthAccountsMutation.isPending ||
      !canWrite ||
      !accounts ||
      !autoDeleteSignature
    ) {
      return;
    }
    if (autoDeleteSignatureRef.current === autoDeleteSignature) {
      return;
    }
    autoDeleteSignatureRef.current = autoDeleteSignature;
    void autoDeleteFreeReauthAccountsMutation.mutateAsync();
  }, [
    accounts,
    autoDeleteFreeReauthAccountsMutation,
    autoDeleteFreeReauthEnabled,
    autoDeleteSignature,
    canWrite,
  ]);
  useEffect(() => {
    if (
      !autoDeleteQuotaExceededEnabled ||
      autoDeleteQuotaExceededAccountsMutation.isPending ||
      !canWrite ||
      !accounts ||
      !autoDeleteQuotaExceededSignature
    ) {
      return;
    }
    if (autoDeleteQuotaExceededSignatureRef.current === autoDeleteQuotaExceededSignature) {
      return;
    }
    autoDeleteQuotaExceededSignatureRef.current = autoDeleteQuotaExceededSignature;
    void autoDeleteQuotaExceededAccountsMutation.mutateAsync();
  }, [
    accounts,
    autoDeleteQuotaExceededAccountsMutation,
    autoDeleteQuotaExceededEnabled,
    autoDeleteQuotaExceededSignature,
    canWrite,
  ]);
  const toggleAccountSort = (key: AccountSortKey) => {
    setAccountSort((current) => {
      if (!current || current.key !== key) return { key, direction: "asc" };
      return { key, direction: current.direction === "asc" ? "desc" : "asc" };
    });
  };
  const restartCodexLb = useCallback(async () => {
    if (!electronApi?.restartApp || restartPending) return;
    setRestartPending(true);
    try {
      const result = await electronApi.restartApp();
      if (!result.success) toast.error(result.message);
    } catch (restartError) {
      toast.error(restartError instanceof Error ? restartError.message : "Failed to restart Codex LB");
    } finally {
      setRestartPending(false);
    }
  }, [electronApi, restartPending]);
  const restartCodex = useCallback(() => {
    void restartCodexMutation.mutateAsync();
  }, [restartCodexMutation]);

  if (activeView === "activity") {
    return (
      <div className="animate-fade-in-up space-y-6">
        <PageHeader
          restartAvailable={restartAvailable}
          restartPending={restartPending}
          restartCodexDisabled={controlsDisabled}
          restartCodexPending={restartCodexMutation.isPending}
          onRestart={restartCodexLb}
          onRestartCodex={restartCodex}
        />
        <CodexNeoTabs activeView={activeView} onChange={setActiveView} />
        {error ? <AlertMessage variant="error">{error}</AlertMessage> : null}
        <CodexNeoActivityPage
          contents={activityLog?.contents ?? ""}
          disabled={controlsDisabled}
          onRefresh={() => activityLogQuery.refetch()}
          onClear={() => clearActivityLogMutation.mutateAsync()}
        />
        <LoadingOverlay visible={busy} label="Refreshing CodexNeo activity..." />
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="animate-fade-in-up space-y-6">
        <PageHeader
          restartAvailable={restartAvailable}
          restartPending={restartPending}
          restartCodexDisabled={controlsDisabled}
          restartCodexPending={restartCodexMutation.isPending}
          onRestart={restartCodexLb}
          onRestartCodex={restartCodex}
        />
        <CodexNeoTabs activeView={activeView} onChange={setActiveView} />
        {error ? <AlertMessage variant="error">{error}</AlertMessage> : null}
        <LoadingOverlay visible label="Loading CodexNeo..." />
      </div>
    );
  }

  return (
    <div className="animate-fade-in-up space-y-6">
      <PageHeader
        restartAvailable={restartAvailable}
        restartPending={restartPending}
        restartCodexDisabled={controlsDisabled}
        restartCodexPending={restartCodexMutation.isPending}
        onRestart={restartCodexLb}
        onRestartCodex={restartCodex}
      />
      <CodexNeoTabs activeView={activeView} onChange={setActiveView} />

      {error ? <AlertMessage variant="error">{error}</AlertMessage> : null}
      {!canWrite ? (
        <div className="rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-xs font-medium text-foreground">
          You are viewing the dashboard with read-only guest access.
        </div>
      ) : null}

      <HealthDiagnostics items={health?.items ?? []} error={getErrorMessageOrNull(healthQuery.error)} />

      <section className="space-y-3 rounded-lg border border-border/70 bg-background/60 p-4">
        <div className="grid gap-3 xl:grid-cols-[1fr_auto_auto_auto_auto_auto] xl:items-end">
          <div className="space-y-1.5">
            <Label htmlFor="codex-home-path">Codex home</Label>
            <Input
              id="codex-home-path"
              value={codexHomePath}
              disabled={controlsDisabled}
              onChange={(event) => setCodexHomePathOverride(event.target.value)}
              placeholder="%USERPROFILE%\\.codex"
            />
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={controlsDisabled}
            onClick={() => saveCodexHomeMutation.mutateAsync({ codexHome: codexHomePath })}
          >
            Save Codex home
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={controlsDisabled}
            onClick={async () => {
              const result = await selectCodexHomeMutation.mutateAsync();
              if (result.success && result.path) setCodexHomePathOverride(result.path);
            }}
          >
            Select Codex home
          </Button>
          <Button type="button" variant="outline" disabled={controlsDisabled} onClick={() => openCodexHomeMutation.mutateAsync()}>
            Codex home
          </Button>
          <Button type="button" variant="outline" disabled={controlsDisabled} onClick={() => resetCodexHomeMutation.mutateAsync()}>
            Reset Codex home
          </Button>
          <Button type="button" variant="outline" disabled={controlsDisabled} onClick={() => openDataFolderMutation.mutateAsync()}>
            Data folder
          </Button>
        </div>
        {codexHome ? (
          <span className="text-xs text-muted-foreground">
            {codexHome.exists ? "Codex Home detected" : "Codex Home folder not found"}
          </span>
        ) : null}
      </section>

      <section className="space-y-4 rounded-lg border border-border/70 bg-background/60 p-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
          <h2 className="text-base font-semibold">Auth to API</h2>
        </div>
        <div className="grid gap-3 md:grid-cols-[1fr_auto_auto_auto] md:items-end">
          <div className="space-y-1.5">
            <Label htmlFor="codex-api-url">Codex API URL</Label>
            <Input
              id="codex-api-url"
              value={codexApiBaseUrl}
              disabled={controlsDisabled}
              onChange={(event) => setCodexApiBaseUrlOverride(event.target.value)}
              placeholder="http://127.0.0.1:2455/backend-api/codex"
            />
          </div>
          <Button
            type="button"
            disabled={controlsDisabled}
            onClick={() => testApiMutation.mutateAsync({ codexApiBaseUrl })}
            className="gap-2"
          >
            <TestTubeDiagonal className="h-4 w-4" aria-hidden="true" />
            Auth-&gt;API Test
          </Button>
          <Button
            type="button"
            disabled={controlsDisabled}
            onClick={() => setApiMutation.mutateAsync({ codexApiBaseUrl })}
            className="gap-2 bg-emerald-600 text-white hover:bg-emerald-700"
          >
            <Zap className="h-4 w-4" aria-hidden="true" />
            Auth-&gt;API Set
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={controlsDisabled}
            onClick={() => revertApiMutation.mutateAsync()}
            className="gap-2"
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            Auth-&gt;API Revert
          </Button>
        </div>
      </section>

      <section className="space-y-4 rounded-lg border border-border/70 bg-background/60 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <RefreshCw className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">CodexGO Auth</h2>
          </div>
          {settings.buyerTokenSaved ? <Badge variant="secondary">Saved</Badge> : null}
        </div>
        <div className="grid gap-3 xl:grid-cols-[auto_7rem_minmax(14rem,1fr)_minmax(18rem,1.4fr)_auto_auto_auto] xl:items-end">
          <div className="flex h-10 items-center gap-2">
            <Switch
              id="codexgo-refresh-enabled"
              checked={autoRefreshEnabled}
              disabled={controlsDisabled}
              onCheckedChange={setAutoRefreshEnabledOverride}
            />
            <Label htmlFor="codexgo-refresh-enabled" className="whitespace-nowrap">
              CodexGO API refresh
            </Label>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="codexgo-interval">Every (min)</Label>
            <Input
              id="codexgo-interval"
              type="number"
              min={5}
              max={1440}
              value={intervalMinutes}
              disabled={controlsDisabled}
              onChange={(event) => setIntervalMinutesOverride(Number(event.target.value))}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="codexgo-buyer-token">Buyer token</Label>
            <Input
              id="codexgo-buyer-token"
              value={buyerToken}
              type="password"
              autoComplete="off"
              disabled={controlsDisabled}
              onChange={(event) => setBuyerToken(event.target.value)}
              placeholder={settings.buyerTokenSaved ? "Saved token retained" : "cg_..."}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="codexgo-url">URL</Label>
            <Input
              id="codexgo-url"
              value={codexgoApiBaseUrl}
              disabled={controlsDisabled}
              onChange={(event) => setCodexgoApiBaseUrlOverride(event.target.value)}
              placeholder="https://codexgo.eu/api/codex-auth"
            />
          </div>
          <Button type="button" variant="outline" disabled={controlsDisabled} onClick={saveSettings} className="gap-2">
            <Save className="h-4 w-4" aria-hidden="true" />
            Save settings
          </Button>
          <Button
            type="button"
            disabled={controlsDisabled}
            onClick={() => runCodexGoAction("use")}
            className="h-10 min-w-28 px-4"
          >
            Use auth
          </Button>
          <Button
            type="button"
            disabled={controlsDisabled}
            onClick={() => runCodexGoAction("refresh")}
            className="h-10 min-w-28 px-4"
          >
            Refresh auth
          </Button>
        </div>
      </section>

      <section className="space-y-4 rounded-lg border border-border/70 bg-background/60 p-4">
        <div className="flex items-center gap-2">
          <ListChecks className="h-4 w-4 text-primary" aria-hidden="true" />
          <div>
            <h2 className="text-base font-semibold">Shared account pool</h2>
            <p className="text-xs text-muted-foreground">The same canonical accounts used by Codex LB routing.</p>
          </div>
        </div>
        <div
          data-testid="codex-home-account-controls"
          className="grid gap-4 xl:grid-cols-[minmax(16rem,auto)_minmax(14rem,1fr)_minmax(12rem,auto)_auto_minmax(11rem,auto)_minmax(12rem,auto)_auto] xl:items-end"
        >
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex h-10 items-center gap-2">
              <Switch
                id="codex-home-auto-refresh-enabled"
                checked={codexHomeAutoRefreshEnabled}
                disabled={controlsDisabled}
                onCheckedChange={setPersistentCodexHomeAutoRefreshEnabled}
              />
              <Label htmlFor="codex-home-auto-refresh-enabled" className="whitespace-nowrap">
                Auto refresh Codex Home
              </Label>
            </div>
            <div className="w-24 space-y-1.5">
              <Label htmlFor="codex-home-refresh-seconds">Every (sec)</Label>
              <Input
                id="codex-home-refresh-seconds"
                aria-label="Codex Home refresh seconds"
                type="number"
                min={MIN_CODEX_HOME_REFRESH_SECONDS}
                max={MAX_CODEX_HOME_REFRESH_SECONDS}
                value={codexHomeRefreshSeconds}
                disabled={controlsDisabled}
                onBlur={saveCodexHomeRefreshSeconds}
                onChange={(event) => setCodexHomeRefreshSecondsOverride(Number(event.target.value))}
              />
            </div>
          </div>
          <div className="min-w-0 space-y-1.5">
            <span className="text-xs font-medium text-muted-foreground">Codex home</span>
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              {accounts?.registryPath ? (
                <span className="max-w-full truncate text-xs text-muted-foreground">{accounts.registryPath}</span>
              ) : (
                <span className="text-xs text-muted-foreground">Registry path unavailable</span>
              )}
              {accountsSyncDiagnostic ? (
                <Badge variant={accountsSyncMismatch ? "destructive" : "outline"}>
                  {accountsSyncMismatch ? "Mismatch" : "Aligned"}
                </Badge>
              ) : null}
            </div>
          </div>
          <div className="flex h-10 items-center gap-2">
            <Switch
              id="codex-home-auto-sync-enabled"
              checked={codexHomeAutoSyncEnabled}
              disabled={controlsDisabled}
              onCheckedChange={setPersistentCodexHomeAutoSyncEnabled}
            />
            <Label htmlFor="codex-home-auto-sync-enabled" className="whitespace-nowrap">
              Auto sync Codex IB
            </Label>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <span className="pb-2 text-sm font-medium text-muted-foreground">Codex IB</span>
            <Button type="button" variant="outline" disabled={controlsDisabled} onClick={refreshAccounts}>
              {accountsQuery.isFetching ? "Refreshing..." : "Refresh"}
            </Button>
            <Button type="button" variant="outline" disabled={controlsDisabled} onClick={() => syncAccountsMutation.mutateAsync()}>
              {syncAccountsMutation.isPending ? "Syncing..." : "Sync"}
            </Button>
          </div>
          <div className="flex h-10 items-center gap-2">
            <Switch
              id="codexneo-minimize-to-tray-enabled"
              checked={minimizeToTrayEnabled}
              disabled={controlsDisabled}
              onCheckedChange={setPersistentMinimizeToTrayEnabled}
            />
            <Label htmlFor="codexneo-minimize-to-tray-enabled" className="whitespace-nowrap">
              Minimize to tray
            </Label>
          </div>
          <div className="flex h-10 items-center gap-2">
            <Switch
              id="codexneo-start-with-windows-enabled"
              checked={startWithWindowsEnabled}
              disabled={controlsDisabled}
              onCheckedChange={setPersistentStartWithWindowsEnabled}
            />
            <Label htmlFor="codexneo-start-with-windows-enabled" className="whitespace-nowrap">
              Start with Windows
            </Label>
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={controlsDisabled || !electronControlsAvailable}
            onClick={minimizeWindow}
            title={electronControlsAvailable ? "Minimize Codex IB" : "Available in the Electron app"}
            className="justify-self-start whitespace-nowrap xl:justify-self-end"
          >
            <Minus className="h-4 w-4" aria-hidden="true" />
            Minimize all
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">{accounts?.message ?? "Loading Codex accounts..."}</p>
        {accountsRefreshFeedback ? (
          <p className="text-xs text-muted-foreground" aria-live="polite">
            {accountsRefreshFeedback}
          </p>
        ) : null}
        {autoSyncFeedback ? (
          <p className="text-xs text-muted-foreground" aria-live="polite">
            {autoSyncFeedback}
          </p>
        ) : null}
        <div className="grid gap-3 rounded-md border border-border/70 p-3 xl:grid-cols-2 xl:items-end">
          <input
            ref={importFolderInputRef}
            aria-label="Choose import folder"
            type="file"
            multiple
            className="sr-only"
            onChange={handleImportFolderSelected}
            {...directoryInputAttributes}
          />
          <div className="space-y-1.5">
            <Label htmlFor="codexneo-import-folder-path">Import folder path</Label>
            <div className="flex gap-2">
              <Input
                id="codexneo-import-folder-path"
                value={importFolderPath}
                disabled={controlsDisabled}
                onChange={(event) => setImportFolderPath(event.target.value)}
                placeholder="Folder containing auth JSON files"
              />
              <Button type="button" variant="outline" disabled={controlsDisabled} onClick={runImportFolder}>
                Import folder
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Every valid JSON identity is ingested into the shared pool and receives a managed backup snapshot.
            </p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="codexneo-export-destination">Export destination</Label>
            <Input
              id="codexneo-export-destination"
              value={exportDestination}
              disabled={controlsDisabled}
              onChange={(event) => setExportDestination(event.target.value)}
              placeholder="Folder that will receive selected account files"
            />
            <p className="text-xs text-muted-foreground">
              Export selected writes one auth file for each checked pool account into a new timestamped folder here.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              aria-label="Codex all"
              type="checkbox"
              checked={accounts?.codexAllEnabled ?? false}
              disabled={controlsDisabled}
              onChange={(event) =>
                setBulkLocationMutation.mutateAsync({ location: "codex", present: event.target.checked })
              }
            />
            Codex all
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              aria-label="Backup all"
              type="checkbox"
              checked={accounts?.backupAllEnabled ?? false}
              disabled={controlsDisabled}
              onChange={(event) =>
                setBulkLocationMutation.mutateAsync({ location: "backup", present: event.target.checked })
              }
            />
            Backup all
          </label>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={controlsDisabled || visibleAccountKeys.length === 0 || allVisibleAccountsSelected}
            onClick={() => setSelectedAccountKeys(visibleAccountKeys)}
          >
            Select all
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={controlsDisabled || selectedAccounts.length === 0}
            onClick={() => setSelectedAccountKeys([])}
          >
            Clear selection
          </Button>
          <div className="flex h-9 items-center gap-2">
            <Switch
              id="codexneo-auto-delete-free-reauth"
              checked={autoDeleteFreeReauthEnabled}
              disabled={controlsDisabled}
              onCheckedChange={setPersistentAutoDeleteFreeReauthEnabled}
            />
            <Label htmlFor="codexneo-auto-delete-free-reauth" className="whitespace-nowrap text-sm">
              Auto delete free/auth required
            </Label>
          </div>
          <div className="flex h-9 items-center gap-2">
            <Switch
              id="codexneo-auto-delete-quota-exceeded"
              checked={autoDeleteQuotaExceededEnabled}
              disabled={controlsDisabled}
              onCheckedChange={setPersistentAutoDeleteQuotaExceededEnabled}
            />
            <Label htmlFor="codexneo-auto-delete-quota-exceeded" className="whitespace-nowrap text-sm">
              Auto delete when weekly remaining = 0%
            </Label>
          </div>
        </div>
        <div data-testid="codexneo-account-actions" className="flex flex-wrap items-end gap-2">
          <Button
            type="button"
            disabled={controlsDisabled || selectedAccounts.length === 0}
            onClick={() => refreshSelectedMutation.mutateAsync({ accountKeys: selectedAccounts })}
          >
            Refresh selected
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={controlsDisabled || selectedAccounts.length === 0}
            onClick={() => exportSelectedMutation.mutateAsync({
              accountKeys: selectedAccounts,
              path: exportDestination.trim() || undefined,
            })}
          >
            Export selected
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={controlsDisabled || selectedAccounts.length === 0}
            onClick={() => {
              const confirmed = window.confirm(
                `Delete ${selectedAccounts.length} selected account(s)? This removes only their managed credentials and snapshots; usage statistics remain.`,
              );
              if (confirmed) void deleteAccountsMutation.mutateAsync({ accountKeys: selectedAccounts });
            }}
          >
            Delete selected
          </Button>
        </div>
        <div className="overflow-x-auto rounded-md border border-border/70">
          <table data-testid="codexneo-accounts-table" className="w-full min-w-[72rem] text-sm">
            <thead className="bg-muted/60 text-xs text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Select</th>
                <SortableHeader label="#" sortKey="number" sort={accountSort} onSort={toggleAccountSort} />
                <th className="px-3 py-2 text-left font-medium">Email</th>
                <SortableHeader label="Plan" sortKey="plan" sort={accountSort} onSort={toggleAccountSort} />
                <SortableHeader label="5h" sortKey="fiveHour" sort={accountSort} onSort={toggleAccountSort} />
                <SortableHeader label="Weekly" sortKey="weekly" sort={accountSort} onSort={toggleAccountSort} />
                <th className="px-3 py-2 text-center font-medium">Codex</th>
                <th className="px-3 py-2 text-center font-medium">Backup</th>
                <SortableHeader label="Avail" sortKey="availability" sort={accountSort} onSort={toggleAccountSort} />
                <SortableHeader label="Status / Last" sortKey="status" sort={accountSort} onSort={toggleAccountSort} />
                <th className="px-3 py-2 text-left font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sortedAccountRows.map(({ account, sourceNumber }) => (
                <AccountRow
                  key={account.accountKey}
                  account={account}
                  sourceNumber={sourceNumber}
                  selected={selectedAccountKeys.includes(account.accountKey)}
                  onSelectedChange={(checked, rangeSelect) => toggleAccount(account.accountKey, checked, rangeSelect)}
                  disabled={controlsDisabled}
                  onSwitch={(accountKey) => switchAccountMutation.mutateAsync({ accountKey, restart: false })}
                  onSwitchRestart={(accountKey) => switchAccountMutation.mutateAsync({ accountKey, restart: true })}
                  onLocationChange={(accountKey, location, present) =>
                    setAccountLocationMutation.mutateAsync({ accountKeys: [accountKey], location, present })
                  }
                />
              ))}
              {accounts?.accounts.length === 0 ? (
                <tr>
                  <td className="px-3 py-6 text-center text-muted-foreground" colSpan={11}>
                    No Codex accounts found.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <LoadingOverlay visible={busy} label="Applying CodexNeo changes..." />
    </div>
  );
}

function PageHeader({
  restartAvailable,
  restartPending,
  restartCodexDisabled,
  restartCodexPending,
  onRestart,
  onRestartCodex,
}: {
  restartAvailable: boolean;
  restartPending: boolean;
  restartCodexDisabled: boolean;
  restartCodexPending: boolean;
  onRestart: () => void;
  onRestartCodex: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
        <CodexLogo size={24} />
        CodexNeo
      </h1>
      <div className="flex w-full flex-col items-stretch gap-2 sm:w-auto sm:items-end">
        <Button
          type="button"
          variant="destructive"
          className="min-w-44 justify-center gap-2"
          disabled={!restartAvailable || restartPending}
          title={
            restartAvailable
              ? "Restart the portable CodexNeo app and its backend"
              : "Available only in the portable CodexNeo app"
          }
          onClick={onRestart}
        >
          <RotateCcw className={restartPending ? "h-4 w-4 animate-spin" : "h-4 w-4"} aria-hidden="true" />
          {restartPending ? "Restarting..." : "Restart CodexNeo"}
        </Button>
        <Button
          type="button"
          variant="destructive"
          className="min-w-44 justify-center gap-2"
          disabled={restartCodexDisabled}
          title="Restart Codex Desktop"
          onClick={onRestartCodex}
        >
          <RotateCcw className={restartCodexPending ? "h-4 w-4 animate-spin" : "h-4 w-4"} aria-hidden="true" />
          {restartCodexPending ? "Restarting Codex..." : "Restart Codex"}
        </Button>
      </div>
    </div>
  );
}

function CodexNeoTabs({ activeView, onChange }: { activeView: CodexNeoView; onChange: (view: CodexNeoView) => void }) {
  return (
    <nav role="tablist" aria-label="CodexNeo pages" className="flex gap-2 border-b border-border/70 pb-3">
      {(["accounts", "activity"] as const).map((view) => (
        <Button
          key={view}
          type="button"
          role="tab"
          aria-selected={activeView === view}
          variant={activeView === view ? "default" : "outline"}
          onClick={() => onChange(view)}
        >
          {view === "accounts" ? "Accounts" : "Activity"}
        </Button>
      ))}
    </nav>
  );
}

function HealthDiagnostics({ items, error }: { items: CodexNeoHealthItem[]; error: string | null }) {
  return (
    <section aria-labelledby="codexneo-health-heading" className="space-y-3 rounded-lg border border-border/70 bg-background/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <CircleHelp className="h-4 w-4 text-primary" aria-hidden="true" />
          <h2 id="codexneo-health-heading" className="text-base font-semibold">Health diagnostics</h2>
        </div>
        {items.length ? <Badge variant="outline">{summaryLabel(items)}</Badge> : null}
      </div>
      {error ? <AlertMessage variant="error">{error}</AlertMessage> : null}
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        {items.map((item) => (
          <HealthBadge key={item.key} item={item} />
        ))}
        {!items.length && !error ? (
          <div className="rounded-md border border-dashed border-border/70 p-3 text-sm text-muted-foreground">
            Loading diagnostics...
          </div>
        ) : null}
      </div>
    </section>
  );
}

function HealthBadge({ item }: { item: CodexNeoHealthItem }) {
  const Icon = item.status === "ok" ? CircleCheck : item.status === "warning" ? CircleAlert : CircleAlert;
  const statusClass =
    item.status === "ok"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
      : item.status === "warning"
        ? "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
        : "border-destructive/30 bg-destructive/10 text-destructive";
  return (
    <div className={`min-w-0 rounded-md border p-3 ${statusClass}`}>
      <div className="flex min-w-0 items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">{item.label}</div>
            <div className="truncate text-xs">{item.message}</div>
          </div>
        </div>
        {item.copyValue ? (
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            aria-label={`Copy ${item.label}`}
            title={`Copy ${item.label}`}
            data-copy-value={item.copyValue}
            onClick={() => void navigator.clipboard?.writeText(item.copyValue ?? "")}
          >
            <Copy className="h-4 w-4" aria-hidden="true" />
          </Button>
        ) : null}
      </div>
      {item.detail ? <div className="mt-2 truncate text-xs opacity-80">{item.detail}</div> : null}
    </div>
  );
}

function summaryLabel(items: CodexNeoHealthItem[]) {
  if (items.some((item) => item.status === "error")) return "Needs attention";
  if (items.some((item) => item.status === "warning")) return "Warnings";
  return "Ready";
}

function SortableHeader({
  label,
  sortKey,
  sort,
  onSort,
}: {
  label: string;
  sortKey: AccountSortKey;
  sort: AccountSortState;
  onSort: (key: AccountSortKey) => void;
}) {
  const active = sort?.key === sortKey;
  const direction = active ? sort.direction : null;
  const ariaSort = active ? (direction === "asc" ? "ascending" : "descending") : "none";
  return (
    <th aria-label={label} aria-sort={ariaSort} className="px-3 py-2 text-left font-medium">
      <button
        type="button"
        aria-label={`Sort by ${label}`}
        className="inline-flex items-center gap-1 rounded-sm text-left hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        onClick={() => onSort(sortKey)}
      >
        <span>{label}</span>
      </button>
    </th>
  );
}

function AccountRow({
  account,
  sourceNumber,
  selected,
  onSelectedChange,
  disabled,
  onSwitch,
  onSwitchRestart,
  onLocationChange,
}: {
  account: CodexNeoAccountRow;
  sourceNumber: number;
  selected: boolean;
  onSelectedChange: (checked: boolean, rangeSelect: boolean) => void;
  disabled: boolean;
  onSwitch: (accountKey: string) => Promise<unknown>;
  onSwitchRestart: (accountKey: string) => Promise<unknown>;
  onLocationChange: (accountKey: string, location: "codex" | "backup", present: boolean) => Promise<unknown>;
}) {
  const label = account.email ?? account.selector ?? account.accountKey;
  const rangeSelectRef = useRef(false);
  return (
    <tr className={account.active ? "bg-primary/10 font-medium" : "border-t border-border/70"}>
      <td className="px-3 py-2">
        <input
          aria-label={`Select ${label}`}
          type="checkbox"
          checked={selected}
          onMouseDown={(event: MouseEvent<HTMLInputElement>) => {
            rangeSelectRef.current = event.shiftKey;
          }}
          onPointerDown={(event: PointerEvent<HTMLInputElement>) => {
            rangeSelectRef.current = event.shiftKey;
          }}
          onClick={(event: MouseEvent<HTMLInputElement>) => {
            onSelectedChange(event.currentTarget.checked, event.shiftKey || rangeSelectRef.current);
            rangeSelectRef.current = false;
          }}
          onChange={() => undefined}
        />
      </td>
      <td className="px-3 py-2 text-muted-foreground">{sourceNumber}</td>
      <td className="px-3 py-2 whitespace-nowrap">{label}</td>
      <td className="px-3 py-2">{account.plan ?? "-"}</td>
      <td className="px-3 py-2">{formatPercent(usageRemainingPercent(account.usage.primary))}</td>
      <td className="px-3 py-2">{formatPercent(usageRemainingPercent(account.usage.secondary))}</td>
      <td className="px-3 py-2 text-center">
        <input
          aria-label={`Codex ${label}`}
          type="checkbox"
          checked={account.codex}
          disabled={disabled}
          onChange={(event) => onLocationChange(account.accountKey, "codex", event.target.checked)}
        />
      </td>
      <td className="px-3 py-2 text-center">
        <input
          aria-label={`Backup ${label}`}
          type="checkbox"
          checked={account.backup}
          disabled={disabled}
          onChange={(event) => onLocationChange(account.accountKey, "backup", event.target.checked)}
        />
      </td>
      <td className="px-3 py-2">{account.availability ?? "-"}</td>
      <td className="px-3 py-2 whitespace-nowrap">{account.status ?? "-"}</td>
      <td className="px-3 py-2 whitespace-nowrap">
        <div data-testid={`account-row-actions-${account.accountKey}`} className="flex flex-nowrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={disabled}
            aria-label={`Switch ${label}`}
            onClick={() => onSwitch(account.accountKey)}
          >
            Switch
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={disabled}
            aria-label={`Switch & Restart ${label}`}
            onClick={() => onSwitchRestart(account.accountKey)}
          >
            Switch &amp; Restart
          </Button>
        </div>
      </td>
    </tr>
  );
}

function formatPercent(value: number | null | undefined) {
  return typeof value === "number" ? `${value}%` : "-";
}

function usageRemainingPercent(
  window: { remainingPercent?: number | null; usedPercent?: number | null } | null | undefined,
) {
  if (typeof window?.remainingPercent === "number") return clampPercent(window.remainingPercent);
  if (typeof window?.usedPercent === "number") return clampPercent(100 - window.usedPercent);
  return null;
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function clampCodexHomeRefreshSeconds(value: number) {
  if (!Number.isFinite(value)) return DEFAULT_CODEX_HOME_REFRESH_SECONDS;
  return Math.max(MIN_CODEX_HOME_REFRESH_SECONDS, Math.min(MAX_CODEX_HOME_REFRESH_SECONDS, Math.round(value)));
}

function sortAccountRows(rows: AccountTableRow[], sort: AccountSortState) {
  if (!sort) return rows;
  const direction = sort.direction === "asc" ? 1 : -1;
  return [...rows].sort((left, right) => {
    const compared = compareAccountRows(left, right, sort.key);
    if (compared !== 0) return compared * direction;
    return left.sourceNumber - right.sourceNumber;
  });
}

function compareAccountRows(left: AccountTableRow, right: AccountTableRow, key: AccountSortKey) {
  switch (key) {
    case "number":
      return left.sourceNumber - right.sourceNumber;
    case "plan":
      return compareText(left.account.plan, right.account.plan);
    case "fiveHour":
      return compareNumber(usageSortValue(usageRemainingPercent(left.account.usage.primary)), usageSortValue(usageRemainingPercent(right.account.usage.primary)));
    case "weekly":
      return compareNumber(usageSortValue(usageRemainingPercent(left.account.usage.secondary)), usageSortValue(usageRemainingPercent(right.account.usage.secondary)));
    case "availability":
      return compareNumber(availabilityPriority(left.account.availability), availabilityPriority(right.account.availability));
    case "status":
      return (
        compareNumber(statusPriority(left.account.status), statusPriority(right.account.status)) ||
        compareText(left.account.status, right.account.status)
      );
  }
}

function compareText(left: string | null | undefined, right: string | null | undefined) {
  return (left ?? "").localeCompare(right ?? "", undefined, { sensitivity: "base", numeric: true });
}

function compareNumber(left: number, right: number) {
  return left - right;
}

function usageSortValue(value: number | null | undefined) {
  return typeof value === "number" ? value : -1;
}

function availabilityPriority(value: string | null | undefined) {
  const normalized = (value ?? "").toLowerCase();
  if (normalized.includes("ready")) return 0;
  if (normalized.includes("backup")) return 1;
  if (normalized.includes("temp") || normalized.includes("unavailable")) return 2;
  return 3;
}

function statusPriority(value: string | null | undefined) {
  const normalized = (value ?? "").split("/")[0].trim().toLowerCase();
  if (normalized === "fresh") return 0;
  if (normalized === "stored") return 1;
  if (normalized === "unknown") return 2;
  if (normalized.includes("unavailable") || normalized.includes("temp")) return 3;
  if (normalized.includes("error") || normalized.includes("failed")) return 4;
  return 5;
}
