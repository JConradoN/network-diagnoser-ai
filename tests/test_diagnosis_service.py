"""Integration-like tests for DiagnosisService using monkeypatched dependencies."""

from __future__ import annotations

import pytest

from analyzer.gemini_analyzer import GeminiAnalyzerError
from config import AppConfig
from scanner.arp_scanner import ARPScannerError
from services.diagnosis_service import DiagnosisService, DiagnosisServiceError
import services.diagnosis_service as diagnosis_module


class _Device:
    def __init__(self, ip: str, mac: str, vendor: str) -> None:
        self._payload = {"ip": ip, "mac": mac, "vendor": vendor}

    def to_dict(self) -> dict:
        return dict(self._payload)


class _SNMPResult:
    def __init__(self, ip: str) -> None:
        self.ip = ip

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "sysName": "router.local",
            "sysDescr": "Mikrotik RouterOS",
            "sysUpTime": "12345",
        }


def _base_config(gemini_api_key: str | None = None) -> AppConfig:
    return AppConfig(
        subnet="192.168.0.0/24",
        interface="eth0",
        snmp_community="public",
        snmp_timeout=1,
        ping_count=1,
        dns_test_domain="example.com",
        traceroute_target="8.8.8.8",
        dhcp_discovery_timeout=1,
        snmp_enabled=True,
        mdns_enabled=True,
        ssdp_enabled=True,
        latency_enabled=True,
        dns_enabled=True,
        route_enabled=True,
        dhcp_enabled=True,
        port_scan_enabled=True,
        port_scan_ports="53,67,80",
        expected_active_hosts=None,
        gemini_api_key=gemini_api_key,
        gemini_model="gemini-1.5-flash",
    )


def _patch_pipeline_dependencies(monkeypatch) -> None:
    class FakeARPScanner:
        def __init__(self, subnet, iface=None):
            self.subnet = subnet
            self.iface = iface

        def scan(self):
            return [
                _Device("192.168.0.1", "aa:bb:cc:dd:ee:01", "Mikrotik"),
                _Device("192.168.0.10", "aa:bb:cc:dd:ee:10", "TP-Link"),
            ]

    class FakeSNMPScanner:
        def __init__(self, community, timeout):
            self.community = community
            self.timeout = timeout

        def collect(self, ip: str):
            if ip == "192.168.0.1":
                return _SNMPResult(ip)
            return None

    class FakeMDNSScanner:
        def discover(self):
            return [{"name": "router", "type": "_http._tcp.local.", "addresses": ["192.168.0.1"], "port": 80}]

    class FakeSSDPScanner:
        def discover(self):
            return [{"ip": "192.168.0.10", "st": "upnp:rootdevice", "server": "TP-Link", "location": "http://192.168.0.10"}]

    class FakeLatencyTester:
        def __init__(self, count):
            self.count = count

        def test(self, host: str):
            return {"host": host, "avg_ms": 12.0, "packet_loss_percent": 0.0, "reachable": True}

    class FakeDNSTester:
        def test(self, domain: str):
            return {"domain": domain, "resolved": True, "elapsed_ms": 5.0, "addresses": ["93.184.216.34"]}

    class FakeRouteAnalyzer:
        def analyze(self, target: str):
            return {
                "target": target,
                "hops": [{"ip": "192.168.0.1", "is_private": True}],
                "private_hops_before_public": 1,
                "nat_multiple_suspected": False,
            }

    class FakeDHCPDetector:
        def __init__(self, timeout, iface=None):
            self.timeout = timeout
            self.iface = iface

        def discover_servers(self):
            return [{"server_ip": "192.168.0.1", "offered_ip": "192.168.0.100"}]

    class FakePortScanner:
        def __init__(self, default_ports):
            self.default_ports = default_ports

        def scan(self, ip: str):
            if ip == "192.168.0.10":
                ports = [{"port": 67, "state": "open", "name": "dhcp"}, {"port": 80, "state": "open", "name": "http"}]
            else:
                ports = [{"port": 53, "state": "open", "name": "dns"}]
            return {"ip": ip, "ports": ports}

    class FakeTopologyBuilder:
        def build(self, devices, ssdp, mdns, snmp=None, ports=None, route=None):
            return {"nodes": devices, "links": [{"from": "192.168.0.1", "to": "192.168.0.10"}], "gateway_ip": "192.168.0.1"}

    class FakeProblemDetector:
        def detect(self, payload: dict):
            _ = payload
            return [{"id": "TEST_FINDING", "severity": "low", "message": "ok", "evidence": {}}]

    monkeypatch.setattr(diagnosis_module, "ARPScanner", FakeARPScanner)
    monkeypatch.setattr(diagnosis_module, "SNMPScanner", FakeSNMPScanner)
    monkeypatch.setattr(diagnosis_module, "MDNSScanner", FakeMDNSScanner)
    monkeypatch.setattr(diagnosis_module, "SSDPScanner", FakeSSDPScanner)
    monkeypatch.setattr(diagnosis_module, "LatencyTester", FakeLatencyTester)
    monkeypatch.setattr(diagnosis_module, "DNSTester", FakeDNSTester)
    monkeypatch.setattr(diagnosis_module, "RouteAnalyzer", FakeRouteAnalyzer)
    monkeypatch.setattr(diagnosis_module, "DHCPDetector", FakeDHCPDetector)
    monkeypatch.setattr(diagnosis_module, "PortScanner", FakePortScanner)
    monkeypatch.setattr(diagnosis_module, "TopologyBuilder", FakeTopologyBuilder)
    monkeypatch.setattr(diagnosis_module, "ProblemDetector", FakeProblemDetector)


def test_run_pipeline_without_gemini(monkeypatch) -> None:
    _patch_pipeline_dependencies(monkeypatch)
    service = DiagnosisService(config=_base_config(gemini_api_key=None))

    payload = service.run()

    assert len(payload["devices"]) == 2
    assert payload["dns"]["resolved"] is True
    assert payload["topology"]["gateway_ip"] == "192.168.0.1"
    assert payload["findings"][0]["id"] == "TEST_FINDING"
    assert "ai_diagnosis" not in payload
    assert "ai_error" not in payload


def test_run_pipeline_with_gemini_success(monkeypatch) -> None:
    _patch_pipeline_dependencies(monkeypatch)

    class FakeGeminiAnalyzer:
        def __init__(self, api_key: str, model: str):
            self.api_key = api_key
            self.model = model

        def analyze(self, network_payload: dict):
            _ = network_payload
            return {"valid_json": True, "parsed": {"diagnosis": "ok"}}

    monkeypatch.setattr(diagnosis_module, "GeminiAnalyzer", FakeGeminiAnalyzer)
    service = DiagnosisService(config=_base_config(gemini_api_key="dummy-key"))

    payload = service.run()

    assert payload["ai_diagnosis"]["valid_json"] is True
    assert payload["ai_diagnosis"]["parsed"]["diagnosis"] == "ok"
    assert "ai_error" not in payload


def test_run_pipeline_with_gemini_error_sets_ai_error(monkeypatch) -> None:
    _patch_pipeline_dependencies(monkeypatch)

    class FakeGeminiAnalyzer:
        def __init__(self, api_key: str, model: str):
            self.api_key = api_key
            self.model = model

        def analyze(self, network_payload: dict):
            _ = network_payload
            raise GeminiAnalyzerError("erro gemini")

    monkeypatch.setattr(diagnosis_module, "GeminiAnalyzer", FakeGeminiAnalyzer)
    service = DiagnosisService(config=_base_config(gemini_api_key="dummy-key"))

    payload = service.run()

    assert payload["ai_error"] == "erro gemini"
    assert "ai_diagnosis" not in payload


def test_arp_error_is_wrapped(monkeypatch) -> None:
    class BrokenARPScanner:
        def __init__(self, subnet, iface=None):
            self.subnet = subnet
            self.iface = iface

        def scan(self):
            raise ARPScannerError("sem permissao")

    monkeypatch.setattr(diagnosis_module, "ARPScanner", BrokenARPScanner)
    service = DiagnosisService(config=_base_config(gemini_api_key=None))

    with pytest.raises(DiagnosisServiceError, match="sem permissao"):
        service.run()


def test_report_helpers_save_load_and_filter(tmp_path) -> None:
    report = {
        "generated_at": "2026-03-17T00:00:00+00:00",
        "report": {
            "devices": [{"ip": "192.168.0.10"}],
            "findings": [
                {"id": "DOUBLE_NAT", "severity": "high", "evidence": {"ip": "192.168.0.10"}},
                {"id": "BACKHAUL_DEGRADED", "severity": "medium", "evidence": {"ip": "192.168.0.20"}},
            ],
        },
    }

    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"

    saved_json = DiagnosisService.save_report(report=report, path=str(json_path))
    saved_md = DiagnosisService.save_markdown_report(report=report, path=str(md_path))
    loaded = DiagnosisService.load_report(path=saved_json)
    filtered = DiagnosisService.filter_findings(loaded, severity="high", device_ip="192.168.0.10")

    assert saved_json.endswith("report.json")
    assert saved_md.endswith("report.md")
    assert loaded["report"]["devices"][0]["ip"] == "192.168.0.10"
    assert len(filtered) == 1
    assert filtered[0]["id"] == "DOUBLE_NAT"