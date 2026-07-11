from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TARGET = "test-codex-parity-smoke"
EXPECTED_RECIPE = (
    "uv sync --dev --frozen",
    "PYTHONFAULTHANDLER=1 uv run pytest $(PYTEST_ARGS) --strict-markers -m codex_parity_smoke",
)


def _assert_codex_parity_smoke_make_contract(makefile: str) -> None:
    phony_targets = {
        target for declaration in re.findall(r"(?m)^\.PHONY:\s*(.*)$", makefile) for target in declaration.split()
    }
    assert TARGET in phony_targets, f"{TARGET} must be declared .PHONY"

    match = re.search(
        rf"(?m)^{re.escape(TARGET)}:(?P<prerequisites>[^\n]*)\n"
        r"(?P<body>(?:\t[^\n]*(?:\n|$))+)",
        makefile,
    )
    assert match is not None, f"missing Make target: {TARGET}"
    assert not match.group("prerequisites").strip(), f"{TARGET} must not have prerequisites"

    recipe = tuple(line.removeprefix("\t").strip() for line in match.group("body").splitlines())
    assert recipe == EXPECTED_RECIPE


def test_codex_parity_smoke_workflow_contract() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    markers = pyproject["tool"]["pytest"]["ini_options"]["markers"]
    assert any(marker.startswith("codex_parity_smoke:") for marker in markers)

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "make test-codex-parity-smoke" in makefile
    _assert_codex_parity_smoke_make_contract(makefile)


def test_codex_parity_smoke_workflow_rejects_prerequisites() -> None:
    makefile = """\
.PHONY: test-codex-parity-smoke
test-codex-parity-smoke: ci-fast
\tuv sync --dev --frozen
\tPYTHONFAULTHANDLER=1 uv run pytest $(PYTEST_ARGS) --strict-markers -m codex_parity_smoke
"""

    with pytest.raises(AssertionError, match="must not have prerequisites"):
        _assert_codex_parity_smoke_make_contract(makefile)
