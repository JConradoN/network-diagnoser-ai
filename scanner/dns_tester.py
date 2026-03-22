"""DNS resolver test module."""

from __future__ import annotations

import socket
import time


class DNSTester:
    """Resolve domains and measure lookup duration."""

    def test(self, domain: str) -> dict:
        """Resolve a DNS name and return timing/result payload."""
        start = time.perf_counter()
        try:
            hostname, aliases, addresses = socket.gethostbyname_ex(domain)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return {
                "domain": domain,
                "resolved": True,
                "hostname": hostname,
                "aliases": aliases,
                "addresses": addresses,
                "elapsed_ms": round(elapsed_ms, 2),
            }
        except socket.gaierror as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return {
                "domain": domain,
                "resolved": False,
                "error": str(exc),
                "elapsed_ms": round(elapsed_ms, 2),
            }
