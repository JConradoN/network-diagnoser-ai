"""Tests for PRD acceptance criteria evaluator."""

from __future__ import annotations

from analyzer.acceptance_evaluator import AcceptanceEvaluator


def test_ca01_not_evaluated_without_expected_hosts() -> None:
    payload = {"devices": [{"ip": "192.168.0.10"}]}

    result = AcceptanceEvaluator().evaluate(payload, expected_active_hosts=None)

    assert result["criteria"]["CA01"]["status"] == "not_evaluated"


def test_ca01_passes_when_coverage_is_90_percent_or_more() -> None:
    payload = {"devices": [{"ip": "192.168.0.10"}, {"ip": "192.168.0.11"}, {"ip": "192.168.0.12"}]}

    result = AcceptanceEvaluator().evaluate(payload, expected_active_hosts=3)

    assert result["criteria"]["CA01"]["status"] == "passed"
    assert result["criteria"]["CA01"]["details"]["coverage_percent"] == 100.0


def test_ca02_ca03_ca05_pass_without_findings_if_capability_exists() -> None:
    payload = {
        "devices": [],
        "route": {"nat_multiple_suspected": False},
        "dhcp_servers": [],
        "findings": [],
    }

    result = AcceptanceEvaluator().evaluate(payload)

    assert result["criteria"]["CA02"]["status"] == "passed"
    assert result["criteria"]["CA03"]["status"] == "passed"
    assert result["criteria"]["CA05"]["status"] == "passed"


def test_ca04_fails_without_gemini_result() -> None:
    payload = {"devices": [], "findings": []}

    result = AcceptanceEvaluator().evaluate(payload)

    assert result["criteria"]["CA04"]["status"] == "failed"


def test_ca04_passes_with_gemini_result() -> None:
    payload = {
        "devices": [],
        "findings": [],
        "ai_diagnosis": {"valid_json": True},
    }

    result = AcceptanceEvaluator().evaluate(payload)

    assert result["criteria"]["CA04"]["status"] == "passed"
