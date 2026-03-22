"""mDNS discovery module using zeroconf."""

from __future__ import annotations

import socket
import time

from utils.logger import get_logger

try:
    from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf
except ImportError:  # pragma: no cover
    ServiceBrowser = ServiceStateChange = Zeroconf = None


class MDNSScanner:
    """Discover mDNS services available in local network."""

    def __init__(self, timeout: float = 2.0) -> None:
        self.timeout = timeout
        self.logger = get_logger(self.__class__.__name__)

    def discover(self) -> list[dict]:
        """Return discovered mDNS services."""
        if Zeroconf is None:
            self.logger.warning("zeroconf nao instalado, pulando mDNS")
            return []

        services: list[dict] = []

        def on_service_state_change(zeroconf, service_type, name, state_change):
            if state_change != ServiceStateChange.Added:
                return
            try:
                info = zeroconf.get_service_info(service_type, name)
            except Exception as exc:
                self.logger.warning(f"mDNS ignorado: {service_type}, {name}, erro: {exc}")
                return
            if info is None:
                return

            addresses = [socket.inet_ntoa(addr) for addr in info.addresses]
            services.append(
                {
                    "name": name,
                    "type": service_type,
                    "addresses": addresses,
                    "port": info.port,
                }
            )

        zeroconf = Zeroconf()
        try:
            ServiceBrowser(zeroconf, "_services._dns-sd._udp.local.", handlers=[on_service_state_change])
            time.sleep(self.timeout)
        finally:
            zeroconf.close()

        return services
