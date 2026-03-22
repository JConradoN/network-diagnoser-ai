"""Unit tests for heuristic problem detection."""

from __future__ import annotations

from analyzer.problem_detector import ProblemDetector


def _finding_ids(findings: list[dict]) -> set[str]:
    return {item.get("id") for item in findings}


def test_detects_double_nat() -> None:
    detector = ProblemDetector()
    report = {
        "route": {
            "nat_multiple_suspected": True,
            "hops": [{"ip": "192.168.0.1", "is_private": True}],
        }
    }

    findings = detector.detect(report)

    assert "DOUBLE_NAT" in _finding_ids(findings)


def test_detects_duplicate_dhcp_servers() -> None:
    detector = ProblemDetector()
    report = {
        "dhcp_servers": [
            {"server_ip": "192.168.0.1", "offered_ip": "192.168.0.50"},
            {"server_ip": "192.168.0.2", "offered_ip": "192.168.0.51"},
        ]
    }

    findings = detector.detect(report)

    assert "DUPLICATE_DHCP" in _finding_ids(findings)


def test_detects_ap_wrong_mode_from_vendor_and_ports() -> None:
    detector = ProblemDetector()
    report = {
        "devices": [
            {"ip": "192.168.0.10", "vendor": "TP-Link"},
            {"ip": "192.168.0.20", "vendor": "Intel"},
        ],
        "ports": [
            {
                "ip": "192.168.0.10",
                "ports": [
                    {"port": 67, "state": "open", "name": "dhcp"},
                    {"port": 80, "state": "open", "name": "http"},
                ],
            },
            {
                "ip": "192.168.0.20",
                "ports": [{"port": 445, "state": "open", "name": "microsoft-ds"}],
            },
        ],
    }

    findings = detector.detect(report)

    assert "AP_WRONG_MODE" in _finding_ids(findings)


def test_detects_backhaul_degraded_for_infra_nodes() -> None:
    detector = ProblemDetector()
    report = {
        "topology": {
            "nodes": [
                {
                    "ip": "192.168.0.1",
                    "vendor": "Mikrotik",
                    "classification": {"role": "router"},
                },
                {
                    "ip": "192.168.0.2",
                    "vendor": "TP-Link",
                    "classification": {"role": "switch"},
                },
            ],
            "gateway_ip": "192.168.0.1",
        },
        "latency": [
            {"host": "192.168.0.1", "avg_ms": 15, "packet_loss_percent": 0},
            {"host": "192.168.0.2", "avg_ms": 95, "packet_loss_percent": 3},
        ],
    }

    findings = detector.detect(report)

    assert "BACKHAUL_DEGRADED" in _finding_ids(findings)


def test_no_false_positive_for_healthy_report() -> None:
    detector = ProblemDetector()
    report = {
        "dns": {"resolved": True},
        "route": {"nat_multiple_suspected": False, "hops": []},
        "dhcp_servers": [{"server_ip": "192.168.0.1", "offered_ip": "192.168.0.30"}],
        "devices": [{"ip": "192.168.0.10", "vendor": "Dell"}],
        "ports": [{"ip": "192.168.0.10", "ports": [{"port": 443, "state": "open"}]}],
        "topology": {
            "nodes": [
                {
                    "ip": "192.168.0.1",
                    "vendor": "Mikrotik",
                    "classification": {"role": "router"},
                },
                {
                    "ip": "192.168.0.10",
                    "vendor": "Dell",
                    "classification": {"role": "unknown"},
                },
            ],
            "gateway_ip": "192.168.0.1",
        },
        "latency": [{"host": "192.168.0.1", "avg_ms": 10, "packet_loss_percent": 0}],
    }

    findings = detector.detect(report)

    critical_ids = {"DOUBLE_NAT", "DUPLICATE_DHCP", "AP_WRONG_MODE", "BACKHAUL_DEGRADED"}
    assert _finding_ids(findings).isdisjoint(critical_ids)