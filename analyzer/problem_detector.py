"""Heuristic problem detection module."""

from __future__ import annotations


class ProblemDetector:
    """Detect common network misconfiguration signals."""

    def detect(self, report: dict) -> list[dict]:
        """Run rule-based checks over collected report."""
        findings: list[dict] = []

        dns = report.get("dns", {})
        if dns and not dns.get("resolved", True):
            findings.append(
                {
                    "id": "DNS_FAILURE",
                    "severity": "high",
                    "message": "Falha na resolucao DNS.",
                    "evidence": dns,
                }
            )

        latency = report.get("latency", [])
        high_latency_hosts = [item for item in latency if (item.get("avg_ms") or 0) > 100]
        if high_latency_hosts:
            findings.append(
                {
                    "id": "HIGH_LATENCY",
                    "severity": "medium",
                    "message": "Latencia media acima de 100ms em um ou mais hosts.",
                    "evidence": high_latency_hosts,
                }
            )

        packet_loss_hosts = [item for item in latency if (item.get("packet_loss_percent") or 0) > 5]
        if packet_loss_hosts:
            findings.append(
                {
                    "id": "PACKET_LOSS",
                    "severity": "high",
                    "message": "Perda de pacotes acima de 5% detectada.",
                    "evidence": packet_loss_hosts,
                }
            )

        route = report.get("route", {})
        if route.get("nat_multiple_suspected"):
            findings.append(
                {
                    "id": "DOUBLE_NAT",
                    "severity": "high",
                    "message": "Suspeita de NAT multiplo detectada por hops privados consecutivos.",
                    "evidence": route,
                }
            )

        dhcp_servers = report.get("dhcp_servers", [])
        if len(dhcp_servers) > 1:
            findings.append(
                {
                    "id": "DUPLICATE_DHCP",
                    "severity": "high",
                    "message": "Multiplos servidores DHCP responderam ao discovery.",
                    "evidence": dhcp_servers,
                }
            )

        ap_router_mode = self._detect_access_points_in_router_mode(report)
        if ap_router_mode:
            findings.append(
                {
                    "id": "AP_WRONG_MODE",
                    "severity": "medium",
                    "message": "Possiveis APs operando em modo roteador.",
                    "evidence": ap_router_mode,
                }
            )

        topology_issues = self._detect_topology_issues(report)
        findings.extend(topology_issues)

        backhaul_issues = self._detect_backhaul_issues(report)
        findings.extend(backhaul_issues)

        return findings

    @staticmethod
    def _detect_access_points_in_router_mode(report: dict) -> list[dict]:
        """Heuristic for AP/router mode mismatch based on vendor and open ports."""
        devices = report.get("devices", [])
        ports = report.get("ports", [])

        ports_by_ip = {item.get("ip"): item for item in ports}
        findings: list[dict] = []

        for device in devices:
            vendor = str(device.get("vendor", "")).lower()
            if not any(keyword in vendor for keyword in ("twibi", "mesh", "access point", "tp-link")):
                continue

            host_ports = ports_by_ip.get(device.get("ip"), {}).get("ports", [])
            open_ports = {
                int(port_data.get("port"))
                for port_data in host_ports
                if str(port_data.get("state", "")).lower() == "open" and port_data.get("port") is not None
            }

            router_signals = {53, 67}.intersection(open_ports)
            if router_signals:
                findings.append(
                    {
                        "ip": device.get("ip"),
                        "vendor": device.get("vendor"),
                        "open_ports": sorted(list(open_ports)),
                        "signals": sorted(list(router_signals)),
                    }
                )

        return findings

    @staticmethod
    def _detect_topology_issues(report: dict) -> list[dict]:
        """Detect topology inconsistencies such as multiple router candidates."""
        findings: list[dict] = []
        topology = report.get("topology", {})
        nodes = topology.get("nodes", [])
        gateway_ip = topology.get("gateway_ip")

        router_candidates = [
            node for node in nodes if node.get("classification", {}).get("role") in {"router", "router_or_ap"}
        ]

        if len(router_candidates) >= 2:
            findings.append(
                {
                    "id": "MULTIPLE_ROUTER_CANDIDATES",
                    "severity": "medium",
                    "message": "Mais de um dispositivo com perfil de roteador/AP detectado na mesma rede.",
                    "evidence": [
                        {
                            "ip": item.get("ip"),
                            "vendor": item.get("vendor"),
                            "role": item.get("classification", {}).get("role"),
                        }
                        for item in router_candidates
                    ],
                }
            )

        if gateway_ip and not any(node.get("ip") == gateway_ip for node in nodes):
            findings.append(
                {
                    "id": "GATEWAY_NOT_IN_INVENTORY",
                    "severity": "low",
                    "message": "Gateway inferido nao aparece na lista de dispositivos do ARP scan.",
                    "evidence": {"gateway_ip": gateway_ip},
                }
            )

        return findings

    @staticmethod
    def _detect_backhaul_issues(report: dict) -> list[dict]:
        """Detect possible degraded backhaul based on latency and loss in infra nodes."""
        findings: list[dict] = []
        topology = report.get("topology", {})
        latency = report.get("latency", [])

        infra_ips = {
            node.get("ip")
            for node in topology.get("nodes", [])
            if node.get("classification", {}).get("role") in {"router", "router_or_ap", "switch"}
        }
        latency_by_ip = {item.get("host"): item for item in latency}

        degraded = []
        for ip in infra_ips:
            metrics = latency_by_ip.get(ip, {})
            avg_ms = metrics.get("avg_ms") or 0
            loss = metrics.get("packet_loss_percent") or 0
            if avg_ms > 80 or loss > 2:
                degraded.append(
                    {
                        "ip": ip,
                        "avg_ms": avg_ms,
                        "packet_loss_percent": loss,
                    }
                )

        if degraded:
            findings.append(
                {
                    "id": "BACKHAUL_DEGRADED",
                    "severity": "medium",
                    "message": "Sinal de backhaul degradado em dispositivos de infraestrutura.",
                    "evidence": degraded,
                }
            )

        return findings
