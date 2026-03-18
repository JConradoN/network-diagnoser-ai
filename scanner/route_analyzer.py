"""Route analysis module for NAT heuristics."""

from __future__ import annotations

import ipaddress
import platform
import re
import subprocess


class RouteAnalyzer:
    """Run traceroute/tracert and infer private/public hop sequence."""

    def __init__(self, max_hops: int = 6) -> None:
        self.max_hops = max_hops

    def analyze(self, target: str = "8.8.8.8") -> dict:
        """Return parsed route information and NAT signal fields."""
        system = platform.system().lower()
        command = self._build_command(system, target)

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            return {
                "target": target,
                "error": str(exc),
                "hops": [],
                "private_hops_before_public": 0,
                "nat_multiple_suspected": False,
            }

        hops = self._extract_hops(completed.stdout or "")
        private_before_public = self._private_hops_before_public(hops)

        return {
            "target": target,
            "hops": hops,
            "private_hops_before_public": private_before_public,
            "nat_multiple_suspected": private_before_public >= 2,
        }

    def _build_command(self, system: str, target: str) -> list[str]:
        if system == "windows":
            return ["tracert", "-h", str(self.max_hops), target]
        return ["traceroute", "-m", str(self.max_hops), "-n", target]

    @staticmethod
    def _extract_hops(output: str) -> list[dict]:
        ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", output)
        hops: list[dict] = []
        for ip in ips:
            hops.append(
                {
                    "ip": ip,
                    "is_private": RouteAnalyzer._is_private_ip(ip),
                }
            )
        return hops

    @staticmethod
    def _private_hops_before_public(hops: list[dict]) -> int:
        count = 0
        for hop in hops:
            if hop.get("is_private"):
                count += 1
                continue
            break
        return count

    @staticmethod
    def _is_private_ip(value: str) -> bool:
        try:
            return ipaddress.ip_address(value).is_private
        except ValueError:
            return False
