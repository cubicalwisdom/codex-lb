import { z } from "zod";

export const CodexNeoSettingsSchema = z.object({
  codexApiBaseUrl: z.string().trim().min(1),
  codexgoApiBaseUrl: z.string().trim().min(1),
  codexgoAutoRefreshEnabled: z.boolean(),
  codexgoAutoRefreshIntervalMinutes: z.number().int().min(5).max(1440),
  openaiActivityLogEnabled: z.boolean(),
  managementActivityLogEnabled: z.boolean(),
  codexHomeAutoRefreshEnabled: z.boolean(),
  codexHomeAutoRefreshIntervalSeconds: z.number().int().min(5).max(3600),
  codexHomeAutoSyncEnabled: z.boolean(),
  minimizeToTrayEnabled: z.boolean(),
  buyerTokenSaved: z.boolean(),
});

export const CodexNeoSettingsUpdateRequestSchema = z.object({
  codexApiBaseUrl: z.string().trim().min(1).optional(),
  codexgoApiBaseUrl: z.string().trim().min(1).optional(),
  codexgoAutoRefreshEnabled: z.boolean().optional(),
  codexgoAutoRefreshIntervalMinutes: z.number().int().min(5).max(1440).optional(),
  openaiActivityLogEnabled: z.boolean().optional(),
  managementActivityLogEnabled: z.boolean().optional(),
  codexHomeAutoRefreshEnabled: z.boolean().optional(),
  codexHomeAutoRefreshIntervalSeconds: z.number().int().min(5).max(3600).optional(),
  codexHomeAutoSyncEnabled: z.boolean().optional(),
  minimizeToTrayEnabled: z.boolean().optional(),
  buyerToken: z.string().optional(),
  clearBuyerToken: z.boolean().optional(),
});

export const CodexNeoApiUrlRequestSchema = z.object({
  codexApiBaseUrl: z.string().trim().min(1).optional(),
});

export const CodexNeoActionResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  configPath: z.string().nullable().optional(),
  authPath: z.string().nullable().optional(),
  backupPath: z.string().nullable().optional(),
  restartAttempted: z.boolean().optional(),
  restartSucceeded: z.boolean().nullable().optional(),
  restartOutput: z.string().nullable().optional(),
});

export const CodexNeoPathResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  path: z.string().nullable().optional(),
});

export const CodexNeoCodexHomeResponseSchema = z.object({
  codexHome: z.string(),
  defaultCodexHome: z.string(),
  dataDir: z.string(),
  customCodexHome: z.boolean(),
  exists: z.boolean(),
});

export const CodexNeoCodexHomeUpdateRequestSchema = z.object({
  codexHome: z.string().trim().min(1),
});

export const CodexNeoPathRequestSchema = z.object({
  path: z.string().optional(),
});

export const CodexNeoAccountKeysRequestSchema = z.object({
  accountKeys: z.array(z.string().trim().min(1)).min(1),
});

export const CodexNeoLocationRequestSchema = z.object({
  accountKeys: z.array(z.string().trim().min(1)).min(1),
  location: z.enum(["codex", "backup"]),
  present: z.boolean(),
});

export const CodexNeoBulkLocationRequestSchema = z.object({
  location: z.enum(["codex", "backup"]),
  present: z.boolean(),
});

export const CodexNeoValidityDateRequestSchema = z.object({
  accountKeys: z.array(z.string().trim().min(1)).min(1),
  validityDate: z.string().trim().min(1),
});

export const CodexNeoSwitchRequestSchema = z.object({
  accountKey: z.string().trim().min(1),
  restart: z.boolean(),
});

export const CodexNeoActivityLogResponseSchema = z.object({
  contents: z.string(),
});

export const CodexNeoHealthItemSchema = z.object({
  key: z.string(),
  label: z.string(),
  status: z.enum(["ok", "warning", "error"]),
  message: z.string(),
  detail: z.string().nullable().optional(),
  copyValue: z.string().nullable().optional(),
});

export const CodexNeoHealthResponseSchema = z.object({
  overallStatus: z.enum(["ok", "warning", "error"]),
  items: z.array(CodexNeoHealthItemSchema),
});

export const CodexNeoAccountUsageWindowSchema = z.object({
  usedPercent: z.number().int().nullable().optional(),
  resetsAt: z.string().nullable().optional(),
  windowMinutes: z.number().int().nullable().optional(),
});

export const CodexNeoAccountUsageSchema = z.object({
  primary: CodexNeoAccountUsageWindowSchema.nullable().optional(),
  secondary: CodexNeoAccountUsageWindowSchema.nullable().optional(),
});

export const CodexNeoAccountRowSchema = z.object({
  accountKey: z.string(),
  selector: z.string().nullable().optional(),
  email: z.string().nullable().optional(),
  alias: z.string().nullable().optional(),
  accountName: z.string().nullable().optional(),
  plan: z.string().nullable().optional(),
  authMode: z.string().nullable().optional(),
  active: z.boolean(),
  lastUsageAt: z.string().nullable().optional(),
  usage: CodexNeoAccountUsageSchema,
  codex: z.boolean(),
  backup: z.boolean(),
  api: z.boolean(),
  apiHourCount: z.number().int(),
  apiDayCount: z.number().int(),
  availability: z.string().nullable().optional(),
  status: z.string().nullable().optional(),
});

export const CodexNeoAccountsResponseSchema = z.object({
  accounts: z.array(CodexNeoAccountRowSchema),
  activeAccountKey: z.string().nullable().optional(),
  registryPath: z.string().nullable().optional(),
  message: z.string(),
  codexAllEnabled: z.boolean().optional(),
  backupAllEnabled: z.boolean().optional(),
});

export type CodexNeoSettings = z.infer<typeof CodexNeoSettingsSchema>;
export type CodexNeoSettingsUpdateRequest = z.infer<typeof CodexNeoSettingsUpdateRequestSchema>;
export type CodexNeoApiUrlRequest = z.infer<typeof CodexNeoApiUrlRequestSchema>;
export type CodexNeoLocationRequest = z.infer<typeof CodexNeoLocationRequestSchema>;
export type CodexNeoBulkLocationRequest = z.infer<typeof CodexNeoBulkLocationRequestSchema>;
export type CodexNeoActionResponse = z.infer<typeof CodexNeoActionResponseSchema>;
export type CodexNeoPathResponse = z.infer<typeof CodexNeoPathResponseSchema>;
export type CodexNeoCodexHomeResponse = z.infer<typeof CodexNeoCodexHomeResponseSchema>;
export type CodexNeoActivityLogResponse = z.infer<typeof CodexNeoActivityLogResponseSchema>;
export type CodexNeoHealthItem = z.infer<typeof CodexNeoHealthItemSchema>;
export type CodexNeoHealthResponse = z.infer<typeof CodexNeoHealthResponseSchema>;
export type CodexNeoAccountRow = z.infer<typeof CodexNeoAccountRowSchema>;
export type CodexNeoAccountsResponse = z.infer<typeof CodexNeoAccountsResponseSchema>;
