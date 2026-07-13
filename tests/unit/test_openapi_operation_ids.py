from __future__ import annotations

from app.main import app


def test_openapi_operation_ids_are_unique() -> None:
    operation_ids: list[str] = []
    for path_item in app.openapi()["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and isinstance(operation.get("operationId"), str):
                operation_ids.append(operation["operationId"])

    assert len(operation_ids) == len(set(operation_ids))
