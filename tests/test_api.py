"""API endpoint tests for FastAPI interface."""

from __future__ import annotations

from fastapi.testclient import TestClient

import api


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(api.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_interfaces_endpoint_returns_available_interfaces(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "list_network_interfaces",
        lambda: [
            {"name": "eth0", "ipv4": "192.168.0.10"},
            {"name": "wlan0", "ipv4": None},
        ],
    )
    client = TestClient(api.app)

    response = client.get("/interfaces")
    payload = response.json()

    assert response.status_code == 200
    assert payload["count"] == 2
    assert payload["interfaces"][0]["name"] == "eth0"


def test_scan_endpoint_returns_report(monkeypatch) -> None:
    expected_report = {
        "generated_at": "2026-03-17T00:00:00+00:00",
        "report": {"devices": [{"ip": "192.168.0.10"}], "findings": []},
    }

    class FakeService:
        def __init__(self, _cfg):
            pass

        def run_with_metadata(self):
            return expected_report

    monkeypatch.setattr(api, "DiagnosisService", FakeService)
    client = TestClient(api.app)

    response = client.post("/scan", json={})

    assert response.status_code == 200
    assert response.json() == expected_report


def test_scan_endpoint_returns_500_on_service_error(monkeypatch) -> None:
    class FakeService:
        def __init__(self, _cfg):
            pass

        def run_with_metadata(self):
            raise api.DiagnosisServiceError("falha de teste")

    monkeypatch.setattr(api, "DiagnosisService", FakeService)
    client = TestClient(api.app)

    response = client.post("/scan", json={})

    assert response.status_code == 500
    assert response.json()["detail"] == "falha de teste"


def test_scan_save_returns_json_and_markdown_paths(monkeypatch) -> None:
    expected_report = {
        "generated_at": "2026-03-17T00:00:00+00:00",
        "report": {
            "devices": [{"ip": "192.168.0.10"}, {"ip": "192.168.0.20"}],
            "findings": [{"id": "DOUBLE_NAT"}],
        },
    }

    class FakeService:
        def __init__(self, _cfg):
            pass

        def run_with_metadata(self):
            return expected_report

        def save_report(self, report, path):
            assert report == expected_report
            assert path == "network_report.json"
            return "network_report.json"

        def save_markdown_report(self, report, path):
            assert report == expected_report
            assert path == "network_report.md"
            return "network_report.md"

    monkeypatch.setattr(api, "DiagnosisService", FakeService)
    client = TestClient(api.app)

    response = client.post("/scan/save", json={})
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "saved"
    assert payload["paths"]["json"] == "network_report.json"
    assert payload["paths"]["markdown"] == "network_report.md"
    assert payload["summary"] == {"devices": 2, "findings": 1}


def test_report_latest_applies_filters(monkeypatch) -> None:
    report = {
        "generated_at": "2026-03-17T00:00:00+00:00",
        "report": {
            "devices": [{"ip": "192.168.0.10"}],
            "findings": [
                {"id": "DOUBLE_NAT", "severity": "high"},
                {"id": "BACKHAUL_DEGRADED", "severity": "medium"},
            ],
        },
    }
    filtered = [{"id": "DOUBLE_NAT", "severity": "high"}]

    monkeypatch.setattr(
        api.DiagnosisService,
        "load_report",
        staticmethod(lambda path: report),
    )
    monkeypatch.setattr(
        api.DiagnosisService,
        "filter_findings",
        staticmethod(lambda _report, severity, device_ip: filtered),
    )

    client = TestClient(api.app)
    response = client.get("/report/latest?severity=high&device_ip=192.168.0.10")
    payload = response.json()

    assert response.status_code == 200
    assert payload["filters"] == {"severity": "high", "device_ip": "192.168.0.10"}
    assert payload["summary"] == {"devices": 1, "findings_total": 2, "findings_filtered": 1}
    assert payload["findings"] == filtered


def test_report_latest_returns_404_when_missing(monkeypatch) -> None:
    def raise_not_found(path):
        raise FileNotFoundError("Relatorio nao encontrado: network_report.json")

    monkeypatch.setattr(api.DiagnosisService, "load_report", staticmethod(raise_not_found))
    client = TestClient(api.app)

    response = client.get("/report/latest")

    assert response.status_code == 404
    assert "Relatorio nao encontrado" in response.json()["detail"]


def test_scan_request_propagates_interface_to_config(monkeypatch) -> None:
    captured = {"interface": None}

    class FakeService:
        def __init__(self, cfg):
            captured["interface"] = cfg.interface

        def run_with_metadata(self):
            return {"generated_at": "x", "report": {"devices": [], "findings": []}}

    monkeypatch.setattr(api, "DiagnosisService", FakeService)
    client = TestClient(api.app)

    response = client.post("/scan", json={"interface": "wlan0"})

    assert response.status_code == 200
    assert captured["interface"] == "wlan0"