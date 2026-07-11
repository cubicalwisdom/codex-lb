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

    lines = makefile.splitlines()
    rules: list[tuple[str, tuple[str, ...]]] = []
    for index, line in enumerate(lines):
        if line.startswith("\t") or ":" not in line:
            continue

        target_list, prerequisites = line.split(":", maxsplit=1)
        if TARGET not in target_list.split():
            continue

        recipe: list[str] = []
        for body_line in lines[index + 1 :]:
            if not body_line.startswith("\t"):
                break
            command = body_line.removeprefix("\t").strip()
            if command:
                recipe.append(command)
        rules.append((prerequisites, tuple(recipe)))

    assert rules, f"missing Make target: {TARGET}"
    for prerequisites, _recipe in rules:
        assert not prerequisites.strip(), f"{TARGET} must not have prerequisites"

    recipes = tuple(recipe for _prerequisites, recipe in rules if recipe)
    assert recipes == (EXPECTED_RECIPE,)
    assert makefile.count(TARGET) == 3, f"{TARGET} must occur exactly three times"


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
test-codex-parity-smoke:
\tuv sync --dev --frozen
\tPYTHONFAULTHANDLER=1 uv run pytest $(PYTEST_ARGS) --strict-markers -m codex_parity_smoke
other-target test-codex-parity-smoke: ci-fast
"""

    with pytest.raises(AssertionError, match="must not have prerequisites"):
        _assert_codex_parity_smoke_make_contract(makefile)
