"""Latency and packet-loss test module."""

from __future__ import annotations

import platform
import re
import subprocess
import time


class LatencyTester:
    """Measure average latency and packet loss via ping."""

    def __init__(self, count: int = 4) -> None:
        self.count = count

    def test(self, host: str) -> dict:
        """Run ping test for a given host."""
        start = time.perf_counter()
        system = platform.system().lower()
        count_flag = "-n" if system == "windows" else "-c"

        try:
            completed = subprocess.run(
                ["ping", count_flag, str(self.count), host],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            return {
                "host": host,
                "reachable": False,
                "avg_ms": None,
                "packet_loss_percent": 100.0,
                "error": str(exc),
            }

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        stdout = completed.stdout or ""
        avg_latency = self._parse_avg_latency_ms(stdout)
        packet_loss = self._parse_packet_loss(stdout)
        rtt_samples = self._extract_rtt_samples_ms(stdout)
        jitter_ms = self._calculate_jitter_ms(rtt_samples)

        return {
            "host": host,
            "reachable": completed.returncode == 0,
            "avg_ms": avg_latency,
            "jitter_ms": jitter_ms,
            "packet_loss_percent": packet_loss,
            "elapsed_ms": round(elapsed_ms, 2),
        }

    @staticmethod
    def _parse_avg_latency_ms(output: str) -> float | None:
        linux_match = re.search(r"min/avg/max(?:/mdev)?\s*=\s*[\d.]+/([\d.]+)/", output)
        if linux_match:
            return float(linux_match.group(1))

        windows_match = re.search(r"Average\s*=\s*(\d+)ms", output)
        if windows_match:
            return float(windows_match.group(1))

        return None

    @staticmethod
    def _parse_packet_loss(output: str) -> float | None:
        linux_match = re.search(r"(\d+(?:\.\d+)?)%\s*packet loss", output)
        if linux_match:
            return float(linux_match.group(1))

        windows_match = re.search(r"\((\d+)%\s*loss\)", output)
        if windows_match:
            return float(windows_match.group(1))

        return None

    @staticmethod
    def _extract_rtt_samples_ms(output: str) -> list[float]:
        """Extract per-packet RTT samples from ping output."""
        samples: list[float] = []

        for match in re.finditer(r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms", output, flags=re.IGNORECASE):
            samples.append(float(match.group(1)))

        return samples

    @staticmethod
    def _calculate_jitter_ms(samples: list[float]) -> float | None:
        """Calculate jitter as mean absolute delta between consecutive RTTs."""
        if len(samples) < 2:
            return None

        deltas = [abs(samples[idx] - samples[idx - 1]) for idx in range(1, len(samples))]
        return round(sum(deltas) / len(deltas), 2)
