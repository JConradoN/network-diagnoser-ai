"""Tests for robust CLI interface."""

from __future__ import annotations

import json

import cli


def test_interfaces_command_outputs_interfaces(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "list_network_interfaces",
        lambda: [{"name": "eth0", "ipv4": "192.168.0.10"}],
    )

    exit_code = cli.main(["interfaces"])

    captured = capsys.readouterr().out
    payload = json.loads(captured)
    assert exit_code == 0
    assert payload["count"] == 1
    assert payload["interfaces"][0]["name"] == "eth0"


def test_scan_command_applies_tool_overrides(monkeypatch, capsys) -> None:
    captured_cfg = {"value": None}

    class FakeService:
        def __init__(self, cfg):
            captured_cfg["value"] = cfg

        def run_with_metadata(self):
            return {
                "generated_at": "2026-03-17T00:00:00+00:00",
                "report": {
                    "devices": [{"ip": "192.168.0.10"}],
                    "findings": [],
                    "prd_acceptance": {"summary": {"passed": 1, "failed": 0, "not_evaluated": 4, "total": 5}},
                },
            }

        def save_report(self, report, path):
            _ = report
            return path

        def save_markdown_report(self, report, path):
            _ = report
            return path

    monkeypatch.setattr(cli, "DiagnosisService", FakeService)

    exit_code = cli.main(
        [
            "scan",
            "--interface",
            "wlan0",
            "--disable-snmp",
            "--disable-mdns",
            "--disable-ssdp",
            "--disable-dns",
            "--disable-route",
            "--disable-dhcp",
            "--disable-latency",
            "--disable-port-scan",
        ]
    )

    captured = capsys.readouterr().out
    payload = json.loads(captured)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert captured_cfg["value"].interface == "wlan0"
    assert captured_cfg["value"].snmp_enabled is False
    assert captured_cfg["value"].mdns_enabled is False
    assert captured_cfg["value"].ssdp_enabled is False
    assert captured_cfg["value"].dns_enabled is False
    assert captured_cfg["value"].route_enabled is False
    assert captured_cfg["value"].dhcp_enabled is False
    assert captured_cfg["value"].latency_enabled is False
    assert captured_cfg["value"].port_scan_enabled is False
