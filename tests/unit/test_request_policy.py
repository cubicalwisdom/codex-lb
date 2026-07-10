from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from app.core.exceptions import ProxyModelNotAllowed
from app.core.openai.requests import ResponsesRequest
from app.modules.api_keys.service import ApiKeyData
from app.modules.proxy.request_policy import apply_api_key_enforcement, validate_model_access


@pytest.mark.parametrize(
    ("alias", "canonical", "expected_effort", "expected_service_tier"),
    [
        ("gpt-5-extra", "gpt-5", "high", None),
        ("gpt-5.1-low", "gpt-5.1", "low", None),
        ("gpt-5.2-medium-fast", "gpt-5.2", "medium", "priority"),
        ("gpt-5.3-priority", "gpt-5.3", None, "priority"),
        ("gpt-5.4-xhigh", "gpt-5.4", "high", None),
        ("gpt-5.4-mini-high", "gpt-5.4-mini", "high", None),
        ("gpt-5.3-codex-fast", "gpt-5.3-codex", None, "priority"),
        ("gpt-5.1-codex-mini-extra-fast", "gpt-5.1-codex-mini", "high", "priority"),
        ("gpt-5.1-codex-max-fast", "gpt-5.1-codex-max", None, "priority"),
        ("gpt-5.5-extra", "gpt-5.5", "high", None),
        ("gpt-5.5-extra-high-fast", "gpt-5.5", "high", "priority"),
        ("gpt-5.6-sol-extra-high-fast", "gpt-5.6-sol", "high", "priority"),
        ("gpt-5.6-sol-xhigh", "gpt-5.6-sol", "high", None),
        ("gpt-5.6-terra-extra-high-fast", "gpt-5.6-terra", "high", "priority"),
        ("gpt-5.6-terra-medium", "gpt-5.6-terra", "medium", None),
        ("gpt-5.6-luna-extra-high-fast", "gpt-5.6-luna", "high", "priority"),
        ("gpt-5.6-luna-low-fast", "gpt-5.6-luna", "low", "priority"),
    ],
)
def test_gpt5_cursor_aliases_target_canonical_models(
    alias: str,
    canonical: str,
    expected_effort: str | None,
    expected_service_tier: str | None,
) -> None:
    request = ResponsesRequest.model_validate(
        {
            "model": alias,
            "instructions": "",
            "input": [],
            "reasoning": {"effort": "low"},
        }
    )

    apply_api_key_enforcement(request, None)

    assert request.model == canonical
    if expected_effort is not None:
        assert request.reasoning is not None
        assert request.reasoning.effort == expected_effort
    assert request.service_tier == expected_service_tier


def test_minimal_reasoning_alias_uses_upstream_safe_fallback() -> None:
    request = ResponsesRequest.model_validate(
        {
            "model": "gpt-5.1-minimal",
            "instructions": "",
            "input": [],
        }
    )

    apply_api_key_enforcement(request, None)

    assert request.model == "gpt-5.1"
    assert request.reasoning is not None
    assert request.reasoning.effort == "low"


def test_unknown_gpt5_suffix_is_not_rewritten() -> None:
    request = ResponsesRequest.model_validate(
        {
            "model": "gpt-5.5-preview",
            "instructions": "",
            "input": [],
        }
    )

    apply_api_key_enforcement(request, None)

    assert request.model == "gpt-5.5-preview"
    assert request.reasoning is None
    assert request.service_tier is None


def test_gpt56_max_and_ultra_suffixes_are_not_rewritten() -> None:
    for model in ("gpt-5.6-sol-ultra", "gpt-5.6-sol-max"):
        request = ResponsesRequest.model_validate(
            {
                "model": model,
                "instructions": "",
                "input": [],
            }
        )

        apply_api_key_enforcement(request, None)

        assert request.model == model
        assert request.reasoning is None
        assert request.service_tier is None


@pytest.mark.parametrize(
    ("requested_effort", "expected_effort"),
    [("ultra", "max"), ("max", "max"), ("xhigh", "xhigh")],
)
def test_reasoning_effort_is_normalized_for_upstream_wire(
    requested_effort: str,
    expected_effort: str,
) -> None:
    request = ResponsesRequest.model_validate(
        {
            "model": "gpt-5.6-sol",
            "instructions": "",
            "input": [],
            "reasoning": {"effort": requested_effort},
        }
    )

    apply_api_key_enforcement(request, None)

    assert request.reasoning is not None
    assert request.reasoning.effort == expected_effort


def test_api_key_enforced_ultra_is_normalized_for_upstream_wire() -> None:
    request = ResponsesRequest.model_validate(
        {
            "model": "gpt-5.6-sol",
            "instructions": "",
            "input": [],
            "reasoning": {"effort": "low"},
        }
    )
    api_key = cast(
        ApiKeyData,
        SimpleNamespace(
            id="key-ultra",
            enforced_model=None,
            enforced_reasoning_effort="ultra",
            enforced_service_tier=None,
        ),
    )

    apply_api_key_enforcement(request, api_key)

    assert request.reasoning is not None
    assert request.reasoning.effort == "max"


def test_model_access_accepts_allowed_canonical_model_alias() -> None:
    api_key = cast(ApiKeyData, SimpleNamespace(allowed_models=frozenset({"gpt-5.5"})))

    validate_model_access(api_key, "gpt-5.5-extra-high-fast")


def test_model_access_accepts_allowed_qualified_canonical_model_alias() -> None:
    api_key = cast(ApiKeyData, SimpleNamespace(allowed_models=frozenset({"gpt-5.4-mini"})))

    validate_model_access(api_key, "gpt-5.4-mini-high")


def test_model_access_accepts_allowed_cursor_alias_for_canonical_model() -> None:
    api_key = cast(ApiKeyData, SimpleNamespace(allowed_models=frozenset({"gpt-5.4-mini-high"})))

    validate_model_access(api_key, "gpt-5.4-mini")


def test_model_access_rejects_alias_when_canonical_model_not_allowed() -> None:
    api_key = cast(ApiKeyData, SimpleNamespace(allowed_models=frozenset({"gpt-5.2"})))

    with pytest.raises(ProxyModelNotAllowed):
        validate_model_access(api_key, "gpt-5.5-extra")
