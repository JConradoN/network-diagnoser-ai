"""Build inferred network topology from collected data."""

from __future__ import annotations

import ipaddress


class TopologyBuilder:
    """Create inferred topology and classify network devices."""

    def build(
        self,
        devices: list[dict],
        ssdp: list[dict],
        mdns: list[dict],
        snmp: list[dict] | None = None,
        ports: list[dict] | None = None,
        route: dict | None = None,
    ) -> dict:
        """Build topology with classified nodes and inferred links."""
        snmp_by_ip = {item.get("ip"): item for item in (snmp or [])}
        ports_by_ip = {item.get("ip"): item.get("ports", []) for item in (ports or [])}
        service_index = self._build_service_index(ssdp=ssdp, mdns=mdns)

        nodes = []
        for device in devices:
            ip = device.get("ip")
            classification = self._classify_device(
                device=device,
                snmp_data=snmp_by_ip.get(ip, {}),
                ports=ports_by_ip.get(ip, []),
                service_data=service_index.get(ip, []),
            )
            enriched = dict(device)
            enriched["classification"] = classification
            enriched["services"] = service_index.get(ip, [])
            nodes.append(enriched)

        gateway_ip = self._infer_gateway_ip(nodes=nodes, route=route)
        links: list[dict] = []

        if gateway_ip:
            for device in nodes:
                if device.get("ip") == gateway_ip:
                    continue
                links.append(
                    {
                        "from": gateway_ip,
                        "to": device.get("ip"),
                        "type": "inferred-lan",
                    }
                )

        return {
            "nodes": nodes,
            "links": links,
            "gateway_ip": gateway_ip,
            "services": {
                "ssdp": ssdp,
                "mdns": mdns,
            },
        }

    @staticmethod
    def _build_service_index(ssdp: list[dict], mdns: list[dict]) -> dict[str, list[dict]]:
        index: dict[str, list[dict]] = {}

        for item in ssdp:
            ip = item.get("ip")
            if not ip:
                continue
            index.setdefault(ip, []).append(
                {
                    "source": "ssdp",
                    "st": item.get("st"),
                    "server": item.get("server"),
                    "location": item.get("location"),
                }
            )

        for item in mdns:
            for ip in item.get("addresses", []):
                index.setdefault(ip, []).append(
                    {
                        "source": "mdns",
                        "name": item.get("name"),
                        "type": item.get("type"),
                        "port": item.get("port"),
                    }
                )

        return index

    @staticmethod
    def _classify_device(device: dict, snmp_data: dict, ports: list[dict], service_data: list[dict]) -> dict:
        vendor = str(device.get("vendor", "")).lower()
        snmp_text = " ".join(
            [
                str(snmp_data.get("sysName", "")),
                str(snmp_data.get("sysDescr", "")),
            ]
        ).lower()
        service_text = " ".join(str(item) for item in service_data).lower()

        open_ports = {
            int(item.get("port"))
            for item in ports
            if str(item.get("state", "")).lower() == "open" and item.get("port") is not None
        }

        role = "unknown"
        confidence = 0.2

        if 67 in open_ports or 68 in open_ports:
            role = "router"
            confidence = 0.9
        elif any(keyword in vendor for keyword in ("mikrotik", "ubiquiti", "tp-link", "asus", "huawei")):
            role = "router_or_ap"
            confidence = 0.6
        elif any(keyword in snmp_text for keyword in ("switch", "bridge")):
            role = "switch"
            confidence = 0.75
        elif any(keyword in service_text for keyword in ("chromecast", "googlecast", "airplay")):
            role = "media_device"
            confidence = 0.8
        elif any(keyword in service_text for keyword in ("printer", "ipp", "_printer")):
            role = "printer"
            confidence = 0.85

        if role == "router_or_ap" and (53 in open_ports or 67 in open_ports):
            role = "router"
            confidence = 0.85

        return {
            "role": role,
            "confidence": confidence,
            "open_ports": sorted(list(open_ports)),
        }

    @staticmethod
    def _infer_gateway_ip(nodes: list[dict], route: dict | None) -> str | None:
        route_hops = (route or {}).get("hops", [])
        first_private_hop = None
        for hop in route_hops:
            if hop.get("is_private"):
                first_private_hop = hop.get("ip")
                break

        if first_private_hop and any(item.get("ip") == first_private_hop for item in nodes):
            return first_private_hop

        def is_valid_ip(ip):
            try:
                ipaddress.ip_address(ip)
                return True
            except Exception:
                return False

        router_candidates = [
            item.get("ip")
            for item in nodes
            if item.get("classification", {}).get("role") == "router"
        ]
        valid_router_ips = [ip for ip in router_candidates if is_valid_ip(ip)]
        if valid_router_ips:
            return sorted(valid_router_ips, key=lambda ip: ipaddress.ip_address(ip))[0]

        if not nodes:
            return None

        ips = [item.get("ip") for item in nodes if item.get("ip")]
        valid_ips = [ip for ip in ips if is_valid_ip(ip)]
        if not valid_ips:
            return "192.168.100.1"  # Fallback para gateway padrão
        return sorted(valid_ips, key=lambda ip: ipaddress.ip_address(ip))[0]
