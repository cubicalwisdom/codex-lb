from __future__ import annotations

from typing import Literal

from app.modules.shared.schemas import DashboardModel


class CodexNeoSettingsResponse(DashboardModel):
    codex_api_base_url: str
    codexgo_api_base_url: str
    codexgo_auto_refresh_enabled: bool
    codexgo_auto_refresh_interval_minutes: int
    openai_activity_log_enabled: bool
    management_activity_log_enabled: bool
    codex_home_auto_refresh_enabled: bool
    codex_home_auto_refresh_interval_seconds: int
    codex_home_auto_sync_enabled: bool
    minimize_to_tray_enabled: bool
    start_with_windows_enabled: bool
    auto_delete_free_reauth_accounts_enabled: bool
    auto_delete_quota_exceeded_accounts_enabled: bool
    buyer_token_saved: bool


class CodexNeoSettingsUpdateRequest(DashboardModel):
    codex_api_base_url: str | None = None
    codexgo_api_base_url: str | None = None
    codexgo_auto_refresh_enabled: bool | None = None
    codexgo_auto_refresh_interval_minutes: int | None = None
    openai_activity_log_enabled: bool | None = None
    management_activity_log_enabled: bool | None = None
    codex_home_auto_refresh_enabled: bool | None = None
    codex_home_auto_refresh_interval_seconds: int | None = None
    codex_home_auto_sync_enabled: bool | None = None
    minimize_to_tray_enabled: bool | None = None
    start_with_windows_enabled: bool | None = None
    auto_delete_free_reauth_accounts_enabled: bool | None = None
    auto_delete_quota_exceeded_accounts_enabled: bool | None = None
    buyer_token: str | None = None
    clear_buyer_token: bool = False


class CodexNeoApiUrlRequest(DashboardModel):
    codex_api_base_url: str | None = None


class CodexNeoActionResponse(DashboardModel):
    success: bool
    message: str
    config_path: str | None = None
    auth_path: str | None = None
    backup_path: str | None = None
    restart_attempted: bool = False
    restart_succeeded: bool | None = None
    restart_output: str | None = None


class CodexNeoPathResponse(DashboardModel):
    success: bool
    message: str
    path: str | None = None


class CodexNeoCodexHomeResponse(DashboardModel):
    codex_home: str
    default_codex_home: str
    data_dir: str
    custom_codex_home: bool
    exists: bool


class CodexNeoCodexHomeUpdateRequest(DashboardModel):
    codex_home: str


class CodexNeoPathRequest(DashboardModel):
    path: str | None = None


class CodexNeoAccountKeysRequest(DashboardModel):
    account_keys: list[str]


class CodexNeoLocationRequest(DashboardModel):
    account_keys: list[str]
    location: Literal["codex", "backup"]
    present: bool


class CodexNeoBulkLocationRequest(DashboardModel):
    location: Literal["codex", "backup"]
    present: bool


class CodexNeoValidityDateRequest(DashboardModel):
    account_keys: list[str]
    validity_date: str


class CodexNeoSwitchRequest(DashboardModel):
    account_key: str
    restart: bool = False


class CodexNeoActivityLogResponse(DashboardModel):
    contents: str


class CodexNeoHealthItem(DashboardModel):
    key: str
    label: str
    status: str
    message: str
    detail: str | None = None
    copy_value: str | None = None


class CodexNeoHealthResponse(DashboardModel):
    overall_status: str
    items: list[CodexNeoHealthItem]


class CodexNeoAccountUsageWindow(DashboardModel):
    used_percent: int | None = None
    remaining_percent: int | None = None
    resets_at: str | None = None
    window_minutes: int | None = None


class CodexNeoAccountUsage(DashboardModel):
    primary: CodexNeoAccountUsageWindow | None = None
    secondary: CodexNeoAccountUsageWindow | None = None


class CodexNeoAccountRow(DashboardModel):
    account_key: str
    selector: str | None = None
    email: str | None = None
    alias: str | None = None
    account_name: str | None = None
    plan: str | None = None
    auth_mode: str | None = None
    active: bool = False
    last_usage_at: str | None = None
    usage: CodexNeoAccountUsage = CodexNeoAccountUsage()
    codex: bool = False
    backup: bool = False
    api: bool = False
    api_hour_count: int = 0
    api_day_count: int = 0
    availability: str | None = None
    status: str | None = None
    codex_ib_account_id: str | None = None
    codex_ib_status: str | None = None
    codex_ib_status_reason: str | None = None
    codex_ib_routable: bool | None = None


class CodexNeoAccountsResponse(DashboardModel):
    accounts: list[CodexNeoAccountRow]
    active_account_key: str | None = None
    registry_path: str | None = None
    message: str
    codex_all_enabled: bool = False
    backup_all_enabled: bool = False
