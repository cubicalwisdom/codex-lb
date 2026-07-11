from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _make_target_body(makefile: str, target: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(target)}:[^\n]*\n(?P<body>(?:\t[^\n]*(?:\n|$))+)",
        makefile,
    )
    assert match is not None, f"missing Make target: {target}"
    return match.group("body")


def test_codex_parity_smoke_workflow_contract() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    markers = pyproject["tool"]["pytest"]["ini_options"]["markers"]
    assert any(marker.startswith("codex_parity_smoke:") for marker in markers)

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "make test-codex-parity-smoke" in makefile
    body = _make_target_body(makefile, "test-codex-parity-smoke")
    assert "uv sync --dev --frozen" in body
    assert "$(PYTEST_ARGS)" in body
    assert "--strict-markers" in body
    assert "-m codex_parity_smoke" in body
    assert not any(
        broad_target in body
        for broad_target in (
            "frontend-build",
            "test-unit",
            "test-integration-core",
            "test-integration-bridge",
            "test-e2e",
            "package",
        )
    )
