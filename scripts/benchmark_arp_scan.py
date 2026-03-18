"""Simple ARP scan benchmark for RNF performance checks.

Usage:
    python scripts/benchmark_arp_scan.py --subnet 192.168.0.0/24 --threshold 10 --interface eth0
"""

from __future__ import annotations

import argparse
import json
import time

from scanner.arp_scanner import ARPScanner, ARPScannerError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark ARP scan runtime")
    parser.add_argument("--subnet", required=True, help="Target subnet in CIDR format")
    parser.add_argument("--threshold", type=float, default=10.0, help="Target max duration in seconds")
    parser.add_argument("--timeout", type=int, default=2, help="ARP reply timeout")
    parser.add_argument("--retry", type=int, default=1, help="ARP retry count")
    parser.add_argument("--interface", default=None, help="Network interface name (ex: eth0, wlan0)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scanner = ARPScanner(
        subnet=args.subnet,
        timeout=args.timeout,
        retry=args.retry,
        iface=args.interface,
    )

    start = time.perf_counter()
    try:
        devices = scanner.scan()
    except ARPScannerError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1

    elapsed_s = round(time.perf_counter() - start, 3)
    result = {
        "status": "ok",
        "subnet": args.subnet,
        "interface": args.interface,
        "device_count": len(devices),
        "elapsed_seconds": elapsed_s,
        "threshold_seconds": args.threshold,
        "passes_threshold": elapsed_s < args.threshold,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
