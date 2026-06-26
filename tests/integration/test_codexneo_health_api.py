from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.modules.codexneo import api as codexneo_api

pytestmark = pytest.mark.integration


class FakeHealthService:
    async def health(self):
        return SimpleNamespace(
            overall_status="ok",
            items=[
                {
                    "key": "codex_home",
                    "label": "Codex Home",
                    "status": "ok",
                    "message": "Detected",
                    "detail": "C:\\Users\\rcgok\\.codex",
                    "copy_value": "C:\\Users\\rcgok\\.codex",
                }
            ],
        )


@pytest.mark.asyncio
async def test_codexneo_health_endpoint_returns_safe_badges(app_instance) -> None:
    app_instance.dependency_overrides[codexneo_api.get_health_service] = lambda: FakeHealthService()

    async with app_instance.router.lifespan_context(app_instance):
        transport = ASGITransport(app=app_instance)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/codexneo/health")

    assert response.status_code == 200
    data = response.json()
    assert data["overallStatus"] == "ok"
    assert data["items"][0]["key"] == "codex_home"
    assert "token" not in json.dumps(data).lower()
