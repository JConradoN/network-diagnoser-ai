"""Port scanner module using python-nmap."""

from __future__ import annotations

from utils.logger import get_logger

try:
    import nmap
except ImportError:  # pragma: no cover
    nmap = None


class PortScanner:
    """Simple TCP port scanner."""

    def __init__(self, default_ports: str = "22,53,80,443") -> None:
        self.default_ports = default_ports
        self.logger = get_logger(self.__class__.__name__)

    def scan(self, ip: str, ports: str | None = None) -> dict:
        """Scan selected ports for a target host."""
        if nmap is None:
            self.logger.warning("python-nmap nao instalado, pulando scan de portas para %s", ip)
            return {"ip": ip, "ports": []}

        scanner = nmap.PortScanner()
        selected_ports = ports or self.default_ports
        scanner.scan(ip, selected_ports, arguments="-sT -Pn")

        result_ports: list[dict] = []
        host_data = scanner[ip] if ip in scanner.all_hosts() else {}
        tcp_data = host_data.get("tcp", {}) if isinstance(host_data, dict) else {}

        for port, data in tcp_data.items():
            result_ports.append(
                {
                    "port": int(port),
                    "state": data.get("state"),
                    "name": data.get("name"),
                }
            )

        return {"ip": ip, "ports": sorted(result_ports, key=lambda item: item["port"]) }
