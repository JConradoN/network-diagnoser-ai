"""SSDP discovery module."""

from __future__ import annotations

import re
import socket

from utils.logger import get_logger


class SSDPScanner:
    """Discover UPnP/SSDP devices on local network."""

    MULTICAST_ADDR = ("239.255.255.250", 1900)
    REQUEST = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: 239.255.255.250:1900\r\n"
        "MAN: \"ssdp:discover\"\r\n"
        "MX: 1\r\n"
        "ST: ssdp:all\r\n\r\n"
    ).encode("ascii")

    def __init__(self, timeout: float = 2.0) -> None:
        self.timeout = timeout
        self.logger = get_logger(self.__class__.__name__)

    def discover(self) -> list[dict]:
        """Run SSDP discovery and return parsed responses."""
        results: dict[str, dict] = {}

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.settimeout(self.timeout)
        sock.sendto(self.REQUEST, self.MULTICAST_ADDR)

        while True:
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                break
            except OSError:
                break

            text = data.decode("utf-8", errors="ignore")
            st = self._extract_header(text, "ST")
            server = self._extract_header(text, "SERVER")
            location = self._extract_header(text, "LOCATION")

            results[addr[0]] = {
                "ip": addr[0],
                "st": st,
                "server": server,
                "location": location,
            }

        sock.close()
        return list(results.values())

    @staticmethod
    def _extract_header(payload: str, header: str) -> str | None:
        match = re.search(rf"^{header}:\s*(.+)$", payload, flags=re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip() if match else None
