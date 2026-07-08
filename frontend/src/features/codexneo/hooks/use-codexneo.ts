import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { invalidateAccountRelatedQueries } from "@/features/accounts/query-invalidation";
import {
  autoDeleteCodexNeoFreeReauthAccounts,
  autoDeleteCodexNeoQuotaExceededAccounts,
  clearCodexNeoActivityLog,
  clearCodexNeoValidityDate,
  deleteCodexNeoAccounts,
  exportCodexNeoAll,
  exportCodexNeoSelected,
  getCodexNeoAccounts,
  getCodexNeoActivityLog,
  getCodexNeoCodexHome,
  getCodexNeoHealth,
  getCodexNeoSettings,
  importCodexNeoFile,
  importCodexNeoFileUpload,
  importCodexNeoFolder,
  importCodexNeoFolderUpload,
  markCodexNeoAvailable,
  markCodexNeoTempUnavailable,
  openCodexNeoCodexHome,
  openCodexNeoDataFolder,
  refreshCodexNeoSelected,
  refreshCodexGoAuth,
  resetCodexNeoCodexHome,
  revertCodexNeoApi,
  restartCodexNeoCodex,
  saveCodexNeoCodexHome,
  setCodexNeoAccountLocation,
  selectCodexNeoCodexHome,
  setCodexNeoApi,
  setCodexNeoBulkLocation,
  setCodexNeoValidityDate,
  syncCodexNeoAccounts,
  switchCodexNeoAccount,
  testCodexNeoApi,
  updateCodexNeoSettings,
  useCodexGoAuth,
} from "@/features/codexneo/api";
import type { CodexNeoApiUrlRequest, CodexNeoSettingsUpdateRequest } from "@/features/codexneo/schemas";

const SETTINGS_QUERY_KEY = ["codexneo", "settings"] as const;
const ACTIVITY_LOG_QUERY_KEY = ["codexneo", "activity-log"] as const;
const ACCOUNTS_QUERY_KEY = ["codexneo", "accounts"] as const;
const CODEX_HOME_QUERY_KEY = ["codexneo", "codex-home"] as const;
const HEALTH_QUERY_KEY = ["codexneo", "health"] as const;

function toastActionResult(result: { success: boolean; message: string }, fallback: string) {
  if (result.success) {
    toast.success(result.message || fallback);
  } else {
    toast.error(result.message || fallback);
  }
}

export function useCodexNeo() {
  const queryClient = useQueryClient();

  const { data, error, isFetching, isPending, refetch } = useQuery({
    queryKey: SETTINGS_QUERY_KEY,
    queryFn: getCodexNeoSettings,
  });
  const settingsQuery = { data, error, isFetching, isPending, refetch };
  const activityLogQueryResult = useQuery({
    queryKey: ACTIVITY_LOG_QUERY_KEY,
    queryFn: getCodexNeoActivityLog,
  });
  const activityLogQuery = {
    data: activityLogQueryResult.data,
    error: activityLogQueryResult.error,
    isFetching: activityLogQueryResult.isFetching,
    isPending: activityLogQueryResult.isPending,
    refetch: activityLogQueryResult.refetch,
  };
  const accountsQueryResult = useQuery({
    queryKey: ACCOUNTS_QUERY_KEY,
    queryFn: getCodexNeoAccounts,
  });
  const accountsQuery = {
    data: accountsQueryResult.data,
    error: accountsQueryResult.error,
    isFetching: accountsQueryResult.isFetching,
    isPending: accountsQueryResult.isPending,
    refetch: accountsQueryResult.refetch,
  };
  const codexHomeQueryResult = useQuery({
    queryKey: CODEX_HOME_QUERY_KEY,
    queryFn: getCodexNeoCodexHome,
  });
  const codexHomeQuery = {
    data: codexHomeQueryResult.data,
    error: codexHomeQueryResult.error,
    isFetching: codexHomeQueryResult.isFetching,
    isPending: codexHomeQueryResult.isPending,
    refetch: codexHomeQueryResult.refetch,
  };
  const healthQueryResult = useQuery({
    queryKey: HEALTH_QUERY_KEY,
    queryFn: getCodexNeoHealth,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
  const healthQuery = {
    data: healthQueryResult.data,
    error: healthQueryResult.error,
    isFetching: healthQueryResult.isFetching,
    isPending: healthQueryResult.isPending,
    refetch: healthQueryResult.refetch,
  };

  const updateSettingsMutation = useMutation({
    mutationFn: (payload: CodexNeoSettingsUpdateRequest) => updateCodexNeoSettings(payload),
    onSuccess: () => {
      toast.success("CodexNeo settings saved");
      void queryClient.invalidateQueries({ queryKey: SETTINGS_QUERY_KEY });
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to save CodexNeo settings");
    },
  });

  const invalidateCodexHome = () => {
    void queryClient.invalidateQueries({ queryKey: CODEX_HOME_QUERY_KEY });
    void queryClient.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY });
    void queryClient.invalidateQueries({ queryKey: SETTINGS_QUERY_KEY });
    void queryClient.invalidateQueries({ queryKey: HEALTH_QUERY_KEY });
  };
  const invalidateAccounts = () => {
    void queryClient.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY });
    invalidateAccountRelatedQueries(queryClient);
    void queryClient.invalidateQueries({ queryKey: ACTIVITY_LOG_QUERY_KEY });
    void queryClient.invalidateQueries({ queryKey: HEALTH_QUERY_KEY });
  };

  const testApiMutation = useMutation({
    mutationFn: (payload: CodexNeoApiUrlRequest) => testCodexNeoApi(payload),
    onSuccess: (result) => toastActionResult(result, "Codex API test finished"),
    onError: (error: Error) => toast.error(error.message || "Codex API test failed"),
  });

  const setApiMutation = useMutation({
    mutationFn: (payload: CodexNeoApiUrlRequest) => setCodexNeoApi(payload),
    onSuccess: (result) => {
      toastActionResult(result, "Codex API provider set");
      void queryClient.invalidateQueries({ queryKey: SETTINGS_QUERY_KEY });
    },
    onError: (error: Error) => toast.error(error.message || "Codex API set failed"),
  });

  const revertApiMutation = useMutation({
    mutationFn: revertCodexNeoApi,
    onSuccess: (result) => toastActionResult(result, "Codex API provider reverted"),
    onError: (error: Error) => toast.error(error.message || "Codex API revert failed"),
  });

  const useAuthMutation = useMutation({
    mutationFn: useCodexGoAuth,
    onSuccess: (result) => {
      toastActionResult(result, "CodexGO auth applied");
      invalidateAccounts();
    },
    onError: (error: Error) => toast.error(error.message || "CodexGO use auth failed"),
  });

  const refreshAuthMutation = useMutation({
    mutationFn: refreshCodexGoAuth,
    onSuccess: (result) => {
      toastActionResult(result, "CodexGO auth refreshed");
      invalidateAccounts();
    },
    onError: (error: Error) => toast.error(error.message || "CodexGO refresh failed"),
  });

  const clearActivityLogMutation = useMutation({
    mutationFn: clearCodexNeoActivityLog,
    onSuccess: (result) => {
      toastActionResult(result, "CodexNeo activity log cleared");
      void queryClient.invalidateQueries({ queryKey: ACTIVITY_LOG_QUERY_KEY });
    },
    onError: (error: Error) => toast.error(error.message || "Failed to clear CodexNeo activity log"),
  });

  const saveCodexHomeMutation = useMutation({
    mutationFn: saveCodexNeoCodexHome,
    onSuccess: (result) => {
      toast.success("Codex Home saved");
      invalidateCodexHome();
      return result;
    },
    onError: (error: Error) => toast.error(error.message || "Failed to save Codex Home"),
  });
  const resetCodexHomeMutation = useMutation({
    mutationFn: resetCodexNeoCodexHome,
    onSuccess: () => {
      toast.success("Codex Home reset");
      invalidateCodexHome();
    },
    onError: (error: Error) => toast.error(error.message || "Failed to reset Codex Home"),
  });
  const selectCodexHomeMutation = useMutation({
    mutationFn: selectCodexNeoCodexHome,
    onSuccess: (result) => toastActionResult(result, "Codex Home selected"),
    onError: (error: Error) => toast.error(error.message || "Failed to select Codex Home"),
  });
  const openCodexHomeMutation = useMutation({
    mutationFn: openCodexNeoCodexHome,
    onSuccess: (result) => toastActionResult(result, "Codex Home opened"),
    onError: (error: Error) => toast.error(error.message || "Failed to open Codex Home"),
  });
  const openDataFolderMutation = useMutation({
    mutationFn: openCodexNeoDataFolder,
    onSuccess: (result) => toastActionResult(result, "Data folder opened"),
    onError: (error: Error) => toast.error(error.message || "Failed to open data folder"),
  });
  const restartCodexMutation = useMutation({
    mutationFn: restartCodexNeoCodex,
    onSuccess: (result) => toastActionResult(result, "Codex restarted"),
    onError: (error: Error) => toast.error(error.message || "Failed to restart Codex"),
  });
  const importFileMutation = useMutation({
    mutationFn: importCodexNeoFile,
    onSuccess: (result) => {
      toastActionResult(result, "Import file finished");
      invalidateAccounts();
    },
    onError: (error: Error) => toast.error(error.message || "Import file failed"),
  });
  const importFileUploadMutation = useMutation({
    mutationFn: importCodexNeoFileUpload,
    onSuccess: (result) => {
      toastActionResult(result, "Import file finished");
      invalidateAccounts();
    },
    onError: (error: Error) => toast.error(error.message || "Import file failed"),
  });
  const importFolderMutation = useMutation({
    mutationFn: importCodexNeoFolder,
    onSuccess: (result) => {
      toastActionResult(result, "Import folder finished");
      invalidateAccounts();
    },
    onError: (error: Error) => toast.error(error.message || "Import folder failed"),
  });
  const importFolderUploadMutation = useMutation({
    mutationFn: importCodexNeoFolderUpload,
    onSuccess: (result) => {
      toastActionResult(result, "Import folder finished");
      invalidateAccounts();
    },
    onError: (error: Error) => toast.error(error.message || "Import folder failed"),
  });
  const exportAllMutation = useMutation({
    mutationFn: exportCodexNeoAll,
    onSuccess: (result) => toastActionResult(result, "Export all finished"),
    onError: (error: Error) => toast.error(error.message || "Export all failed"),
  });
  const exportSelectedMutation = useMutation({
    mutationFn: exportCodexNeoSelected,
    onSuccess: (result) => toastActionResult(result, "Export selected finished"),
    onError: (error: Error) => toast.error(error.message || "Export selected failed"),
  });
  const markTempUnavailableMutation = useMutation({
    mutationFn: markCodexNeoTempUnavailable,
    onSuccess: (result) => {
      toastActionResult(result, "Marked temporarily unavailable");
      invalidateAccounts();
    },
  });
  const markAvailableMutation = useMutation({
    mutationFn: markCodexNeoAvailable,
    onSuccess: (result) => {
      toastActionResult(result, "Marked available");
      invalidateAccounts();
    },
  });
  const setValidityDateMutation = useMutation({
    mutationFn: setCodexNeoValidityDate,
    onSuccess: (result) => {
      toastActionResult(result, "Validity date set");
      invalidateAccounts();
    },
  });
  const clearValidityDateMutation = useMutation({
    mutationFn: clearCodexNeoValidityDate,
    onSuccess: (result) => {
      toastActionResult(result, "Validity date cleared");
      invalidateAccounts();
    },
  });
  const refreshSelectedMutation = useMutation({
    mutationFn: refreshCodexNeoSelected,
    onSuccess: (result) => {
      toastActionResult(result, "Selected accounts refreshed");
      invalidateAccounts();
    },
    onError: (error: Error) => toast.error(error.message || "Selected account refresh failed"),
  });
  const syncAccountsMutation = useMutation({
    mutationFn: () => syncCodexNeoAccounts(),
    onSuccess: (result) => {
      toastActionResult(result, "Accounts synced");
      invalidateAccounts();
    },
    onError: (error: Error) => toast.error(error.message || "Accounts sync failed"),
  });
  const autoDeleteFreeReauthAccountsMutation = useMutation({
    mutationFn: () => autoDeleteCodexNeoFreeReauthAccounts(),
    onSuccess: (result) => {
      toastActionResult(result, "Auto delete free/auth required finished");
      invalidateAccounts();
    },
    onError: (error: Error) => toast.error(error.message || "Auto delete free/auth required failed"),
  });
  const autoDeleteQuotaExceededAccountsMutation = useMutation({
    mutationFn: () => autoDeleteCodexNeoQuotaExceededAccounts(),
    onSuccess: (result) => {
      toastActionResult(result, "Auto delete quota exceeded finished");
      invalidateAccounts();
    },
    onError: (error: Error) => toast.error(error.message || "Auto delete quota exceeded failed"),
  });
  const switchAccountMutation = useMutation({
    mutationFn: switchCodexNeoAccount,
    onSuccess: (result) => {
      toastActionResult(result, "Switch finished");
      invalidateAccounts();
    },
    onError: (error: Error) => toast.error(error.message || "Switch failed"),
  });
  const deleteAccountsMutation = useMutation({
    mutationFn: deleteCodexNeoAccounts,
    onSuccess: (result) => {
      toastActionResult(result, "Delete finished");
      invalidateAccounts();
    },
    onError: (error: Error) => toast.error(error.message || "Delete selected failed"),
  });
  const setAccountLocationMutation = useMutation({
    mutationFn: setCodexNeoAccountLocation,
    onSuccess: (result) => {
      toastActionResult(result, "Account location updated");
      invalidateAccounts();
    },
  });
  const setBulkLocationMutation = useMutation({
    mutationFn: setCodexNeoBulkLocation,
    onSuccess: (result) => {
      toastActionResult(result, "Account location default updated");
      invalidateAccounts();
    },
  });

  return {
    settingsQuery,
    activityLogQuery,
    accountsQuery,
    codexHomeQuery,
    healthQuery,
    updateSettingsMutation,
    testApiMutation,
    setApiMutation,
    revertApiMutation,
    useAuthMutation,
    refreshAuthMutation,
    clearActivityLogMutation,
    saveCodexHomeMutation,
    resetCodexHomeMutation,
    selectCodexHomeMutation,
    openCodexHomeMutation,
    openDataFolderMutation,
    restartCodexMutation,
    importFileMutation,
    importFileUploadMutation,
    importFolderMutation,
    importFolderUploadMutation,
    exportAllMutation,
    exportSelectedMutation,
    markTempUnavailableMutation,
    markAvailableMutation,
    setValidityDateMutation,
    clearValidityDateMutation,
    refreshSelectedMutation,
    syncAccountsMutation,
    autoDeleteFreeReauthAccountsMutation,
    autoDeleteQuotaExceededAccountsMutation,
    switchAccountMutation,
    deleteAccountsMutation,
    setAccountLocationMutation,
    setBulkLocationMutation,
  };
}
