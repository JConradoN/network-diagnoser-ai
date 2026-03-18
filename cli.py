"""Robust CLI interface for Network Diagnoser AI."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
import time

from config import AppConfig, load_config
from scanner.arp_scanner import ARPScanner, ARPScannerError
from services.diagnosis_service import DiagnosisService, DiagnosisServiceError
from utils.network_utils import list_network_interfaces


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Network Diagnoser AI CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("interfaces", help="Listar interfaces de rede disponiveis")

    scan_parser = subparsers.add_parser("scan", help="Executar diagnostico de rede")
    _add_common_scan_args(scan_parser)
    scan_parser.add_argument("--json-output", default="network_report.json", help="Arquivo de relatorio JSON")
    scan_parser.add_argument("--md-output", default="network_report.md", help="Arquivo de relatorio Markdown")
    scan_parser.add_argument("--no-markdown", action="store_true", help="Nao gerar relatorio Markdown")
    scan_parser.add_argument("--print-json", action="store_true", help="Imprimir relatorio completo no terminal")

    report_parser = subparsers.add_parser("report", help="Ler e filtrar relatorio salvo")
    report_parser.add_argument("--path", default="network_report.json", help="Caminho do relatorio JSON")
    report_parser.add_argument("--severity", default=None, help="Filtrar findings por severidade")
    report_parser.add_argument("--device-ip", default=None, help="Filtrar findings por IP")

    bench_parser = subparsers.add_parser("benchmark", help="Benchmark de tempo do ARP scan")
    bench_parser.add_argument("--subnet", required=True, help="Sub-rede alvo (CIDR)")
    bench_parser.add_argument("--interface", default=None, help="Interface de rede (ex: eth0, wlan0)")
    bench_parser.add_argument("--timeout", type=int, default=2, help="Timeout ARP")
    bench_parser.add_argument("--retry", type=int, default=1, help="Tentativas ARP")
    bench_parser.add_argument("--threshold", type=float, default=10.0, help="Limite de tempo em segundos")

    return parser


def _add_common_scan_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--subnet", default=None, help="Sub-rede em CIDR")
    parser.add_argument("--interface", default=None, help="Interface de rede (ex: eth0, wlan0)")
    parser.add_argument("--ping-count", type=int, default=None, help="Quantidade de pings por host")
    parser.add_argument("--dns-domain", default=None, help="Dominio para teste DNS")
    parser.add_argument("--traceroute-target", default=None, help="Alvo para analise de rota")
    parser.add_argument("--port-scan-ports", default=None, help="Lista CSV de portas para scan")
    parser.add_argument("--expected-active-hosts", type=int, default=None, help="Estimativa de hosts ativos")

    parser.add_argument("--disable-snmp", action="store_true", help="Desabilitar coleta SNMP")
    parser.add_argument("--disable-mdns", action="store_true", help="Desabilitar descoberta mDNS")
    parser.add_argument("--disable-ssdp", action="store_true", help="Desabilitar descoberta SSDP")
    parser.add_argument("--disable-latency", action="store_true", help="Desabilitar testes de latencia/jitter")
    parser.add_argument("--disable-dns", action="store_true", help="Desabilitar teste DNS")
    parser.add_argument("--disable-route", action="store_true", help="Desabilitar analise de rota")
    parser.add_argument("--disable-dhcp", action="store_true", help="Desabilitar detector DHCP")
    parser.add_argument("--disable-port-scan", action="store_true", help="Desabilitar scan de portas")


def _apply_scan_overrides(base: AppConfig, args: argparse.Namespace) -> AppConfig:
    return replace(
        base,
        subnet=args.subnet if args.subnet is not None else base.subnet,
        interface=args.interface if args.interface is not None else base.interface,
        ping_count=args.ping_count if args.ping_count is not None else base.ping_count,
        dns_test_domain=args.dns_domain if args.dns_domain is not None else base.dns_test_domain,
        traceroute_target=(
            args.traceroute_target if args.traceroute_target is not None else base.traceroute_target
        ),
        port_scan_ports=args.port_scan_ports if args.port_scan_ports is not None else base.port_scan_ports,
        expected_active_hosts=(
            args.expected_active_hosts if args.expected_active_hosts is not None else base.expected_active_hosts
        ),
        snmp_enabled=False if args.disable_snmp else base.snmp_enabled,
        mdns_enabled=False if args.disable_mdns else base.mdns_enabled,
        ssdp_enabled=False if args.disable_ssdp else base.ssdp_enabled,
        latency_enabled=False if args.disable_latency else base.latency_enabled,
        dns_enabled=False if args.disable_dns else base.dns_enabled,
        route_enabled=False if args.disable_route else base.route_enabled,
        dhcp_enabled=False if args.disable_dhcp else base.dhcp_enabled,
        port_scan_enabled=False if args.disable_port_scan else base.port_scan_enabled,
    )


def _cmd_interfaces() -> int:
    payload = {
        "count": len(list_network_interfaces()),
        "interfaces": list_network_interfaces(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    base = load_config()
    cfg = _apply_scan_overrides(base, args)
    service = DiagnosisService(cfg)

    try:
        report = service.run_with_metadata()
    except DiagnosisServiceError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1

    json_path = service.save_report(report=report, path=args.json_output)
    md_path = None
    if not args.no_markdown:
        md_path = service.save_markdown_report(report=report, path=args.md_output)

    summary = {
        "status": "ok",
        "json_report": json_path,
        "markdown_report": md_path,
        "devices": len(report.get("report", {}).get("devices", [])),
        "findings": len(report.get("report", {}).get("findings", [])),
        "acceptance": report.get("report", {}).get("prd_acceptance", {}).get("summary", {}),
    }

    if args.print_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    try:
        report = DiagnosisService.load_report(path=args.path)
    except FileNotFoundError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1

    filtered = DiagnosisService.filter_findings(
        report,
        severity=args.severity,
        device_ip=args.device_ip,
    )

    payload = {
        "status": "ok",
        "path": args.path,
        "generated_at": report.get("generated_at"),
        "filters": {
            "severity": args.severity,
            "device_ip": args.device_ip,
        },
        "summary": {
            "devices": len(report.get("report", {}).get("devices", [])),
            "findings_total": len(report.get("report", {}).get("findings", [])),
            "findings_filtered": len(filtered),
        },
        "findings": filtered,
        "acceptance": report.get("report", {}).get("prd_acceptance", {}),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
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
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1

    elapsed_s = round(time.perf_counter() - start, 3)
    payload = {
        "status": "ok",
        "subnet": args.subnet,
        "interface": args.interface,
        "device_count": len(devices),
        "elapsed_seconds": elapsed_s,
        "threshold_seconds": args.threshold,
        "passes_threshold": elapsed_s < args.threshold,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "interfaces":
        return _cmd_interfaces()
    if args.command == "scan":
        return _cmd_scan(args)
    if args.command == "report":
        return _cmd_report(args)
    if args.command == "benchmark":
        return _cmd_benchmark(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
