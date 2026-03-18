"""Regression tests for topology building heuristics."""

from __future__ import annotations

from analyzer.topology_builder import TopologyBuilder


def _node_by_ip(nodes: list[dict], ip: str) -> dict:
    return next(item for item in nodes if item.get("ip") == ip)


def test_gateway_prefers_private_route_hop_when_present_in_nodes() -> None:
    builder = TopologyBuilder()
    devices = [
        {"ip": "192.168.1.1", "mac": "aa:aa:aa:aa:aa:01", "vendor": "Mikrotik"},
        {"ip": "192.168.1.10", "mac": "aa:aa:aa:aa:aa:10", "vendor": "Dell"},
    ]

    topology = builder.build(
        devices=devices,
        ssdp=[],
        mdns=[],
        ports=[{"ip": "192.168.1.1", "ports": [{"port": 53, "state": "open"}]}],
        route={"hops": [{"ip": "192.168.1.1", "is_private": True}]},
    )

    assert topology["gateway_ip"] == "192.168.1.1"
    assert topology["links"] == [{"from": "192.168.1.1", "to": "192.168.1.10", "type": "inferred-lan"}]


def test_gateway_falls_back_to_router_candidate_when_route_hop_missing() -> None:
    builder = TopologyBuilder()
    devices = [
        {"ip": "192.168.1.2", "mac": "aa:aa:aa:aa:aa:02", "vendor": "TP-Link"},
        {"ip": "192.168.1.20", "mac": "aa:aa:aa:aa:aa:20", "vendor": "Apple"},
    ]

    topology = builder.build(
        devices=devices,
        ssdp=[],
        mdns=[],
        ports=[{"ip": "192.168.1.2", "ports": [{"port": 67, "state": "open"}]}],
        route={"hops": [{"ip": "10.0.0.1", "is_private": True}]},
    )

    assert topology["gateway_ip"] == "192.168.1.2"


def test_gateway_falls_back_to_lowest_ip_when_no_router_candidate() -> None:
    builder = TopologyBuilder()
    devices = [
        {"ip": "192.168.1.50", "mac": "aa:aa:aa:aa:aa:50", "vendor": "Dell"},
        {"ip": "192.168.1.3", "mac": "aa:aa:aa:aa:aa:03", "vendor": "Lenovo"},
    ]

    topology = builder.build(
        devices=devices,
        ssdp=[],
        mdns=[],
        ports=[],
        route={"hops": []},
    )

    assert topology["gateway_ip"] == "192.168.1.3"


def test_classifies_roles_from_ports_services_and_snmp() -> None:
    builder = TopologyBuilder()
    devices = [
        {"ip": "192.168.0.1", "mac": "aa:aa:aa:aa:aa:01", "vendor": "Mikrotik"},
        {"ip": "192.168.0.10", "mac": "aa:aa:aa:aa:aa:10", "vendor": "Generic"},
        {"ip": "192.168.0.20", "mac": "aa:aa:aa:aa:aa:20", "vendor": "Generic"},
        {"ip": "192.168.0.30", "mac": "aa:aa:aa:aa:aa:30", "vendor": "Generic"},
    ]

    topology = builder.build(
        devices=devices,
        ssdp=[{"ip": "192.168.0.20", "st": "upnp", "server": "Google Chromecast", "location": "http://x"}],
        mdns=[{"name": "Office Printer", "type": "_ipp._tcp.local.", "addresses": ["192.168.0.30"], "port": 631}],
        snmp=[{"ip": "192.168.0.10", "sysName": "sw-01", "sysDescr": "Managed Switch", "sysUpTime": "123"}],
        ports=[
            {"ip": "192.168.0.1", "ports": [{"port": 67, "state": "open"}]},
            {"ip": "192.168.0.10", "ports": [{"port": 22, "state": "open"}]},
            {"ip": "192.168.0.20", "ports": [{"port": 8009, "state": "open"}]},
            {"ip": "192.168.0.30", "ports": [{"port": 631, "state": "open"}]},
        ],
        route={"hops": [{"ip": "192.168.0.1", "is_private": True}]},
    )

    nodes = topology["nodes"]
    assert _node_by_ip(nodes, "192.168.0.1")["classification"]["role"] == "router"
    assert _node_by_ip(nodes, "192.168.0.10")["classification"]["role"] == "switch"
    assert _node_by_ip(nodes, "192.168.0.20")["classification"]["role"] == "media_device"
    assert _node_by_ip(nodes, "192.168.0.30")["classification"]["role"] == "printer"


def test_classifies_vendor_router_or_ap_and_promotes_with_dns_port() -> None:
    builder = TopologyBuilder()
    devices = [{"ip": "192.168.10.2", "mac": "aa:aa:aa:aa:aa:02", "vendor": "Ubiquiti"}]

    topology = builder.build(
        devices=devices,
        ssdp=[],
        mdns=[],
        ports=[{"ip": "192.168.10.2", "ports": [{"port": 53, "state": "open"}]}],
        route={"hops": []},
    )

    node = topology["nodes"][0]
    assert node["classification"]["role"] == "router"
    assert node["classification"]["confidence"] == 0.85