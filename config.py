"""Application configuration for Network Diagnoser AI."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=False)  # Explicitamente definido como False para evitar erros
class AppConfig:
    """Runtime settings loaded from environment variables."""

    subnet: str | None = None
    interface: str | None = None
    snmp_community: str = "public"
    snmp_timeout: int = 2
    ping_count: int = 4
    dns_test_domain: str = "google.com"
    traceroute_target: str = "8.8.8.8"
    dhcp_discovery_timeout: int = 4
    snmp_enabled: bool = True
    mdns_enabled: bool = True
    ssdp_enabled: bool = True
    latency_enabled: bool = True
    dns_enabled: bool = True
    route_enabled: bool = True
    dhcp_enabled: bool = True
    port_scan_enabled: bool = True
    port_scan_ports: str = "22,53,67,68,80,443"
    expected_active_hosts: int | None = None
    gemini_api_key: str | None = None
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

def load_config() -> AppConfig:
    """Load application configuration from environment variables."""
    return AppConfig(
        subnet=os.getenv("ND_SUBNET") or None,
        interface=os.getenv("ND_INTERFACE") or None,
        snmp_community=os.getenv("ND_SNMP_COMMUNITY", "public"),
        snmp_timeout=int(os.getenv("ND_SNMP_TIMEOUT", "2")),
        ping_count=int(os.getenv("ND_PING_COUNT", "4")),
        dns_test_domain=os.getenv("ND_DNS_TEST_DOMAIN", "google.com"),
        traceroute_target=os.getenv("ND_TRACEROUTE_TARGET", "8.8.8.8"),
        dhcp_discovery_timeout=int(os.getenv("ND_DHCP_DISCOVERY_TIMEOUT", "4")),
        snmp_enabled=os.getenv("ND_SNMP_ENABLED", "true").lower() == "true",
        mdns_enabled=os.getenv("ND_MDNS_ENABLED", "true").lower() == "true",
        ssdp_enabled=os.getenv("ND_SSDP_ENABLED", "true").lower() == "true",
        latency_enabled=os.getenv("ND_LATENCY_ENABLED", "true").lower() == "true",
        dns_enabled=os.getenv("ND_DNS_ENABLED", "true").lower() == "true",
        route_enabled=os.getenv("ND_ROUTE_ENABLED", "true").lower() == "true",
        dhcp_enabled=os.getenv("ND_DHCP_ENABLED", "true").lower() == "true",
        port_scan_enabled=os.getenv("ND_PORT_SCAN_ENABLED", "true").lower() == "true",
        port_scan_ports=os.getenv("ND_PORT_SCAN_PORTS", "22,53,67,68,80,443"),
        expected_active_hosts=(
            int(os.getenv("ND_EXPECTED_ACTIVE_HOSTS"))
            if os.getenv("ND_EXPECTED_ACTIVE_HOSTS")
            and os.getenv("ND_EXPECTED_ACTIVE_HOSTS", "").isdigit()
            else None
        ),
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    )