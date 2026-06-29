from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.auth.dependencies import (
    require_dashboard_write_access,
    set_dashboard_error_format,
    validate_dashboard_session,
)
from app.db.session import get_background_session
from app.modules.accounts.repository import AccountsRepository
from app.modules.codexneo.account_actions import CodexNeoAccountActionService
from app.modules.codexneo.accounts import CodexHomeAccountService
from app.modules.codexneo.activity_log import CodexNeoActivityLogService
from app.modules.codexneo.health import CodexNeoHealthService
from app.modules.codexneo.home import CodexHomeService, codexneo_data_dir, resolve_configured_codex_home
from app.modules.codexneo.import_export import CodexNeoImportExportService
from app.modules.codexneo.locations import CodexNeoAccountLocationService
from app.modules.codexneo.schemas import (
    CodexNeoAccountKeysRequest,
    CodexNeoAccountsResponse,
    CodexNeoActionResponse,
    CodexNeoActivityLogResponse,
    CodexNeoApiUrlRequest,
    CodexNeoBulkLocationRequest,
    CodexNeoCodexHomeResponse,
    CodexNeoCodexHomeUpdateRequest,
    CodexNeoHealthResponse,
    CodexNeoLocationRequest,
    CodexNeoPathRequest,
    CodexNeoPathResponse,
    CodexNeoSettingsResponse,
    CodexNeoSettingsUpdateRequest,
    CodexNeoSwitchRequest,
    CodexNeoValidityDateRequest,
)
from app.modules.codexneo.service import CodexGoAction, CodexNeoService, restart_codex_desktop
from app.modules.codexneo.sync import CodexNeoAccountsSyncService

router = APIRouter(
    prefix="/api/codexneo",
    tags=["dashboard"],
    dependencies=[Depends(validate_dashboard_session), Depends(set_dashboard_error_format)],
)


def get_codexneo_service() -> CodexNeoService:
    codex_home = resolve_configured_codex_home()
    data_dir = codexneo_data_dir()
    return CodexNeoService(
        codex_home=codex_home,
        account_sync=CodexNeoAccountsSyncService(codex_home=codex_home, data_dir=data_dir),
    )


def get_activity_log_service() -> CodexNeoActivityLogService:
    return CodexNeoActivityLogService()


def get_account_service() -> CodexHomeAccountService:
    return CodexHomeAccountService()


def get_health_service() -> CodexNeoHealthService:
    async def accounts_count() -> int:
        async with get_background_session() as session:
            return len(await AccountsRepository(session).list_accounts())

    return CodexNeoHealthService(
        codex_home=resolve_configured_codex_home(),
        data_dir=codexneo_data_dir(),
        accounts_count_provider=accounts_count,
    )


def get_codex_home_service() -> CodexHomeService:
    return CodexHomeService()


def get_import_export_service() -> CodexNeoImportExportService:
    codex_home = resolve_configured_codex_home()
    data_dir = codexneo_data_dir()
    return CodexNeoImportExportService(
        codex_home=codex_home,
        data_dir=data_dir,
        account_sync=CodexNeoAccountsSyncService(codex_home=codex_home, data_dir=data_dir),
    )


def get_account_action_service() -> CodexNeoAccountActionService:
    codex_home = resolve_configured_codex_home()
    data_dir = codexneo_data_dir()
    return CodexNeoAccountActionService(
        codex_home=codex_home,
        data_dir=data_dir,
        restart_provider=restart_codex_desktop,
        account_sync=CodexNeoAccountsSyncService(codex_home=codex_home, data_dir=data_dir),
        location_service=CodexNeoAccountLocationService(codex_home=codex_home, data_dir=data_dir),
    )


def get_account_location_service() -> CodexNeoAccountLocationService:
    return CodexNeoAccountLocationService(codex_home=resolve_configured_codex_home(), data_dir=codexneo_data_dir())


def get_account_sync_service() -> CodexNeoAccountsSyncService:
    return CodexNeoAccountsSyncService(codex_home=resolve_configured_codex_home(), data_dir=codexneo_data_dir())


def _safe_upload_name(filename: str | None, fallback: str, used_names: set[str] | None = None) -> str:
    candidate = Path(filename or fallback).name.replace("\\", "_").strip()
    if not candidate:
        candidate = fallback
    if used_names is None:
        return candidate
    stem = Path(candidate).stem or "auth"
    suffix = "".join(Path(candidate).suffixes) or ".json"
    unique = candidate
    index = 2
    while unique.lower() in used_names:
        unique = f"{stem}-{index}{suffix}"
        index += 1
    used_names.add(unique.lower())
    return unique


@router.get("", response_model=CodexNeoSettingsResponse)
async def get_codexneo_settings(service: CodexNeoService = Depends(get_codexneo_service)) -> CodexNeoSettingsResponse:
    return await service.get_settings()


@router.put("", response_model=CodexNeoSettingsResponse)
async def update_codexneo_settings(
    payload: CodexNeoSettingsUpdateRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoService = Depends(get_codexneo_service),
) -> CodexNeoSettingsResponse:
    return await service.update_settings(
        codex_api_base_url=payload.codex_api_base_url,
        codexgo_api_base_url=payload.codexgo_api_base_url,
        codexgo_auto_refresh_enabled=payload.codexgo_auto_refresh_enabled,
        codexgo_auto_refresh_interval_minutes=payload.codexgo_auto_refresh_interval_minutes,
        openai_activity_log_enabled=payload.openai_activity_log_enabled,
        management_activity_log_enabled=payload.management_activity_log_enabled,
        codex_home_auto_refresh_enabled=payload.codex_home_auto_refresh_enabled,
        codex_home_auto_refresh_interval_seconds=payload.codex_home_auto_refresh_interval_seconds,
        codex_home_auto_sync_enabled=payload.codex_home_auto_sync_enabled,
        minimize_to_tray_enabled=payload.minimize_to_tray_enabled,
        start_with_windows_enabled=payload.start_with_windows_enabled,
        buyer_token=payload.buyer_token,
        clear_buyer_token=payload.clear_buyer_token,
    )


@router.get("/activity-log", response_model=CodexNeoActivityLogResponse)
async def get_activity_log(
    service: CodexNeoActivityLogService = Depends(get_activity_log_service),
) -> CodexNeoActivityLogResponse:
    return CodexNeoActivityLogResponse(contents=service.read())


@router.delete("/activity-log", response_model=CodexNeoActionResponse)
async def clear_activity_log(
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoActivityLogService = Depends(get_activity_log_service),
) -> CodexNeoActionResponse:
    service.clear()
    return CodexNeoActionResponse(success=True, message="CodexNeo activity log cleared")


@router.get("/accounts", response_model=CodexNeoAccountsResponse)
async def get_codex_home_accounts(
    service: CodexHomeAccountService = Depends(get_account_service),
) -> CodexNeoAccountsResponse:
    return await service.load_accounts_with_codex_ib_usage()


@router.get("/health", response_model=CodexNeoHealthResponse)
async def get_health(
    service: CodexNeoHealthService = Depends(get_health_service),
) -> CodexNeoHealthResponse:
    return await service.health()


@router.get("/codex-home", response_model=CodexNeoCodexHomeResponse)
async def get_codex_home(
    service: CodexHomeService = Depends(get_codex_home_service),
) -> CodexNeoCodexHomeResponse:
    return service.get_codex_home()


@router.put("/codex-home", response_model=CodexNeoCodexHomeResponse)
async def save_codex_home(
    payload: CodexNeoCodexHomeUpdateRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexHomeService = Depends(get_codex_home_service),
) -> CodexNeoCodexHomeResponse:
    return service.save_codex_home(payload.codex_home)


@router.post("/codex-home/reset", response_model=CodexNeoCodexHomeResponse)
async def reset_codex_home(
    _write_access=Depends(require_dashboard_write_access),
    service: CodexHomeService = Depends(get_codex_home_service),
) -> CodexNeoCodexHomeResponse:
    return service.reset_codex_home()


@router.post("/codex-home/select", response_model=CodexNeoPathResponse)
async def select_codex_home(
    _write_access=Depends(require_dashboard_write_access),
    service: CodexHomeService = Depends(get_codex_home_service),
) -> CodexNeoPathResponse:
    return service.select_codex_home()


@router.post("/codex-home/open", response_model=CodexNeoPathResponse)
async def open_codex_home(
    _write_access=Depends(require_dashboard_write_access),
    service: CodexHomeService = Depends(get_codex_home_service),
) -> CodexNeoPathResponse:
    return service.open_codex_home()


@router.post("/data-folder/open", response_model=CodexNeoPathResponse)
async def open_data_folder(
    _write_access=Depends(require_dashboard_write_access),
    service: CodexHomeService = Depends(get_codex_home_service),
) -> CodexNeoPathResponse:
    return service.open_data_folder()


@router.post("/app/restart", response_model=CodexNeoActionResponse)
async def restart_codex_app(
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoService = Depends(get_codexneo_service),
) -> CodexNeoActionResponse:
    return await service.restart_codex_app()


@router.post("/import/file", response_model=CodexNeoPathResponse)
async def import_file(
    payload: CodexNeoPathRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoImportExportService = Depends(get_import_export_service),
) -> CodexNeoPathResponse:
    return await service.import_file(payload.path or "")


@router.post("/import/file-upload", response_model=CodexNeoPathResponse)
async def import_file_upload(
    auth_json: UploadFile = File(...),
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoImportExportService = Depends(get_import_export_service),
) -> CodexNeoPathResponse:
    with tempfile.TemporaryDirectory(prefix="codexneo-upload-file-") as tmp_dir:
        target = Path(tmp_dir) / _safe_upload_name(auth_json.filename, "auth.json")
        target.write_bytes(await auth_json.read())
        return await service.import_file(target)


@router.post("/import/folder", response_model=CodexNeoPathResponse)
async def import_folder(
    payload: CodexNeoPathRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoImportExportService = Depends(get_import_export_service),
) -> CodexNeoPathResponse:
    return await service.import_folder(payload.path or "")


@router.post("/import/folder-upload", response_model=CodexNeoPathResponse)
async def import_folder_upload(
    files: list[UploadFile] = File(...),
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoImportExportService = Depends(get_import_export_service),
) -> CodexNeoPathResponse:
    with tempfile.TemporaryDirectory(prefix="codexneo-upload-folder-") as tmp_dir:
        folder = Path(tmp_dir) / "codexneo-upload-folder"
        folder.mkdir()
        used_names: set[str] = set()
        for upload in files:
            if not (upload.filename or "").lower().endswith(".json"):
                continue
            target = folder / _safe_upload_name(upload.filename, "auth.json", used_names)
            target.write_bytes(await upload.read())
        return await service.import_folder(folder)


@router.post("/export/all", response_model=CodexNeoPathResponse)
async def export_all(
    payload: CodexNeoPathRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoImportExportService = Depends(get_import_export_service),
) -> CodexNeoPathResponse:
    return await service.export_all(payload.path)


@router.post("/export/selected", response_model=CodexNeoPathResponse)
async def export_selected(
    payload: CodexNeoAccountKeysRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoImportExportService = Depends(get_import_export_service),
) -> CodexNeoPathResponse:
    return await service.export_selected(payload.account_keys)


@router.post("/accounts/temp-unavailable", response_model=CodexNeoActionResponse)
async def mark_accounts_temporarily_unavailable(
    payload: CodexNeoAccountKeysRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoAccountActionService = Depends(get_account_action_service),
) -> CodexNeoActionResponse:
    return await service.mark_temporarily_unavailable(payload.account_keys)


@router.post("/accounts/mark-available", response_model=CodexNeoActionResponse)
async def mark_accounts_available(
    payload: CodexNeoAccountKeysRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoAccountActionService = Depends(get_account_action_service),
) -> CodexNeoActionResponse:
    return await service.mark_available(payload.account_keys)


@router.post("/accounts/validity-date", response_model=CodexNeoActionResponse)
async def set_accounts_validity_date(
    payload: CodexNeoValidityDateRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoAccountActionService = Depends(get_account_action_service),
) -> CodexNeoActionResponse:
    return await service.set_validity_date(payload.account_keys, payload.validity_date)


@router.post("/accounts/clear-validity-date", response_model=CodexNeoActionResponse)
async def clear_accounts_validity_date(
    payload: CodexNeoAccountKeysRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoAccountActionService = Depends(get_account_action_service),
) -> CodexNeoActionResponse:
    return await service.clear_validity_date(payload.account_keys)


@router.post("/accounts/refresh", response_model=CodexNeoActionResponse)
async def refresh_selected_accounts(
    payload: CodexNeoAccountKeysRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoAccountsSyncService = Depends(get_account_sync_service),
) -> CodexNeoActionResponse:
    result = await service.refresh_selected_account_usage(payload.account_keys)
    return CodexNeoActionResponse(success=result.success, message=result.message)


@router.post("/accounts/sync", response_model=CodexNeoActionResponse)
async def sync_accounts(
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoAccountsSyncService = Depends(get_account_sync_service),
) -> CodexNeoActionResponse:
    result = await service.sync_all_accounts()
    return CodexNeoActionResponse(success=result.success, message=result.message)


@router.post("/accounts/location", response_model=CodexNeoActionResponse)
async def set_account_location(
    payload: CodexNeoLocationRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoAccountLocationService = Depends(get_account_location_service),
) -> CodexNeoActionResponse:
    return service.set_location(payload.account_keys, location=payload.location, present=payload.present)


@router.post("/accounts/location/default", response_model=CodexNeoActionResponse)
async def set_bulk_account_location(
    payload: CodexNeoBulkLocationRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoAccountLocationService = Depends(get_account_location_service),
) -> CodexNeoActionResponse:
    return service.set_bulk_default(location=payload.location, present=payload.present)


@router.post("/accounts/switch", response_model=CodexNeoActionResponse)
async def switch_account(
    payload: CodexNeoSwitchRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoAccountActionService = Depends(get_account_action_service),
) -> CodexNeoActionResponse:
    return await service.switch_account(payload.account_key, restart=payload.restart)


@router.post("/accounts/delete", response_model=CodexNeoActionResponse)
async def delete_accounts(
    payload: CodexNeoAccountKeysRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoAccountActionService = Depends(get_account_action_service),
) -> CodexNeoActionResponse:
    return await service.delete_accounts(payload.account_keys)


@router.post("/api-test", response_model=CodexNeoActionResponse)
async def test_api_provider(
    payload: CodexNeoApiUrlRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoService = Depends(get_codexneo_service),
) -> CodexNeoActionResponse:
    return await service.test_api_provider(payload.codex_api_base_url)


@router.post("/api-set", response_model=CodexNeoActionResponse)
async def set_api_provider(
    payload: CodexNeoApiUrlRequest,
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoService = Depends(get_codexneo_service),
) -> CodexNeoActionResponse:
    return await service.set_api_provider(payload.codex_api_base_url)


@router.post("/api-revert", response_model=CodexNeoActionResponse)
async def revert_api_provider(
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoService = Depends(get_codexneo_service),
) -> CodexNeoActionResponse:
    return await service.revert_api_provider()


@router.post("/codexgo/use", response_model=CodexNeoActionResponse)
async def use_codexgo_auth(
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoService = Depends(get_codexneo_service),
) -> CodexNeoActionResponse:
    return await service.apply_codexgo_auth(CodexGoAction.USE)


@router.post("/codexgo/refresh", response_model=CodexNeoActionResponse)
async def refresh_codexgo_auth(
    _write_access=Depends(require_dashboard_write_access),
    service: CodexNeoService = Depends(get_codexneo_service),
) -> CodexNeoActionResponse:
    return await service.apply_codexgo_auth(CodexGoAction.REFRESH)
