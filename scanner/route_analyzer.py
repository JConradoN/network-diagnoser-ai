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
        hops: list[dict] = []
        lines = output.splitlines()
        hop_regex = re.compile(r"^\s*\d+\s+(.*)")
        ip_regex = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
        latency_regex = re.compile(r"(\d+\.\d+) ms")
        for line in lines:
            m = hop_regex.match(line)
            if not m:
                continue
            hop_data = m.group(1)
            ips = ip_regex.findall(hop_data)
            latencies = latency_regex.findall(hop_data)
            if not ips:
                # Saltos com * * *
                hops.append({"ip": "*", "latency": None, "is_private": False})
            else:
                for idx, ip in enumerate(ips):
                    latency = float(latencies[idx]) if idx < len(latencies) else None
                    hops.append({
                        "ip": ip,
                        "latency": latency,
                        "is_private": RouteAnalyzer._is_private_ip(ip),
                    })
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
