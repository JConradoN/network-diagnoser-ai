"""Unit tests for LatencyTester parsing and jitter calculation."""

from __future__ import annotations

from scanner.latency_tester import LatencyTester


def test_extract_rtt_samples_linux_output() -> None:
    output = """
64 bytes from 8.8.8.8: icmp_seq=1 ttl=119 time=10.1 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=119 time=12.3 ms
64 bytes from 8.8.8.8: icmp_seq=3 ttl=119 time=11.3 ms
"""

    samples = LatencyTester._extract_rtt_samples_ms(output)

    assert samples == [10.1, 12.3, 11.3]


def test_extract_rtt_samples_windows_output() -> None:
    output = """
Reply from 8.8.8.8: bytes=32 time=14ms TTL=116
Reply from 8.8.8.8: bytes=32 time<1ms TTL=116
Reply from 8.8.8.8: bytes=32 time=9ms TTL=116
"""

    samples = LatencyTester._extract_rtt_samples_ms(output)

    assert samples == [14.0, 1.0, 9.0]


def test_calculate_jitter_mean_absolute_delta() -> None:
    jitter = LatencyTester._calculate_jitter_ms([10.0, 12.0, 11.0, 13.0])
    # deltas = [2, 1, 2], media = 1.666...
    assert jitter == 1.67


def test_calculate_jitter_returns_none_for_single_sample() -> None:
    assert LatencyTester._calculate_jitter_ms([10.0]) is None


def test_test_method_includes_jitter(monkeypatch) -> None:
    tester = LatencyTester(count=3)

    class CompletedProcess:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = (
                "64 bytes from 8.8.8.8: icmp_seq=1 ttl=119 time=10.0 ms\n"
                "64 bytes from 8.8.8.8: icmp_seq=2 ttl=119 time=13.0 ms\n"
                "64 bytes from 8.8.8.8: icmp_seq=3 ttl=119 time=11.0 ms\n"
                "rtt min/avg/max/mdev = 10.000/11.333/13.000/1.247 ms\n"
                "3 packets transmitted, 3 received, 0% packet loss\n"
            )

    monkeypatch.setattr("scanner.latency_tester.subprocess.run", lambda *args, **kwargs: CompletedProcess())

    result = tester.test("8.8.8.8")

    assert result["jitter_ms"] == 2.5
    assert result["avg_ms"] == 11.333
    assert result["packet_loss_percent"] == 0.0
