from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.modules.codexneo import api as codexneo_api
from app.modules.codexneo.schemas import CodexNeoPathResponse

pytestmark = pytest.mark.integration


class FakeImportExportService:
    def __init__(self) -> None:
        self.imported_files: list[tuple[str, bytes]] = []
        self.imported_folders: list[tuple[str, list[str]]] = []
        self.selected_exports: list[tuple[list[str], str | None]] = []

    async def import_file(self, path):
        source = Path(path)
        self.imported_files.append((source.name, source.read_bytes()))
        return CodexNeoPathResponse(success=True, message="file imported", path=str(source))

    async def import_folder(self, path):
        source = Path(path)
        self.imported_folders.append((source.name, sorted(item.name for item in source.glob("*.json"))))
        return CodexNeoPathResponse(success=True, message="folder imported", path=str(source))

    async def export_selected(self, account_keys, destination=None):
        self.selected_exports.append((account_keys, destination))
        return CodexNeoPathResponse(success=True, message="selected exported", path=destination)


@pytest.mark.asyncio
async def test_codexneo_import_file_upload_saves_temp_file_and_imports(app_instance) -> None:
    service = FakeImportExportService()
    app_instance.dependency_overrides[codexneo_api.get_import_export_service] = lambda: service

    async with app_instance.router.lifespan_context(app_instance):
        transport = ASGITransport(app=app_instance)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/codexneo/import/file-upload",
                files={"auth_json": ("auth.json", b'{"tokens":{"access_token":"secret"}}', "application/json")},
            )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert service.imported_files == [("auth.json", b'{"tokens":{"access_token":"secret"}}')]


@pytest.mark.asyncio
async def test_codexneo_import_folder_upload_saves_temp_folder_and_imports(app_instance) -> None:
    service = FakeImportExportService()
    app_instance.dependency_overrides[codexneo_api.get_import_export_service] = lambda: service

    async with app_instance.router.lifespan_context(app_instance):
        transport = ASGITransport(app=app_instance)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/codexneo/import/folder-upload",
                files=[
                    ("files", ("one.auth.json", b'{"one": true}', "application/json")),
                    ("files", ("nested/two.auth.json", b'{"two": true}', "application/json")),
                    ("files", ("notes.txt", b"skip", "text/plain")),
                ],
            )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert service.imported_folders == [("codexneo-upload-folder", ["one.auth.json", "two.auth.json"])]


@pytest.mark.asyncio
async def test_codexneo_export_selected_passes_explicit_destination(app_instance) -> None:
    service = FakeImportExportService()
    app_instance.dependency_overrides[codexneo_api.get_import_export_service] = lambda: service

    async with app_instance.router.lifespan_context(app_instance):
        transport = ASGITransport(app=app_instance)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/codexneo/export/selected",
                json={"accountKeys": ["acct-1", "acct-2"], "path": "D:\\CodexExports"},
            )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert service.selected_exports == [(["acct-1", "acct-2"], "D:\\CodexExports")]
