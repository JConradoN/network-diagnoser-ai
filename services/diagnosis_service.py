from __future__ import annotations
"""Shared diagnosis pipeline service used by CLI and API."""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Generator, Any

from analyzer.acceptance_evaluator import AcceptanceEvaluator
from analyzer.gemini_analyzer import GeminiAnalyzer, GeminiAnalyzerError
from analyzer.problem_detector import ProblemDetector
from analyzer.topology_builder import TopologyBuilder
from config import AppConfig
from output.report_generator import ReportGenerator

from scanner.arp_scanner import ARPScanner, ARPScannerError
from scanner.dns_tester import DNSTester
from scanner.latency_tester import LatencyTester
from scanner.mdns_scanner import MDNSScanner
from scanner.port_scanner import PortScanner
from scanner.route_analyzer import RouteAnalyzer
from scanner.ssdp_scanner import SSDPScanner

# Coletores MikroTik e SNMP
from collectors.mikrotik_api import get_wan_status, get_neighbors
from collectors.mikrotik_dhcp import get_dhcp_details
from collectors.snmp_metrics import get_mikrotik_health

logger = logging.getLogger(__name__)

@dataclass
class LogMessage:
    level: str
    stage: str
    message: str
    data: dict = field(default_factory=dict)

class DiagnosisServiceError(Exception):
    """Raised when diagnosis pipeline fails."""

class DiagnosisService:
    """Runs full network diagnosis and returns structured report payload."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    @staticmethod
    def _clean_vendor(v: Any) -> str:
        """Garante que vendor seja sempre uma string limpa, removendo tuplas residuais."""
        if isinstance(v, tuple):
            return str(v[1]) if len(v) > 1 else str(v[0])
        return str(v) if v and v != "None" else "-"

    def consolidate_devices(self, arp_devices: list, dhcp_leases: list, ping_status: dict) -> list:
        """Une ARP e DHCP priorizando nomes do MikroTik e garantindo limpeza de vendors."""
        devices_by_mac = {dev['mac'].lower(): dev for dev in arp_devices}
        consolidated = []
        dhcp_macs = set()

        for lease in dhcp_leases:
            mac = lease.get('mac-address', '').lower()
            if not mac: continue
            dhcp_macs.add(mac)
            
            arp_dev = devices_by_mac.get(mac)
            ip = lease.get('address', arp_dev['ip'] if arp_dev else '-')
            
            # Um dispositivo é considerado ATIVO se responder ao ping OU ao ARP
            ping_ok = ping_status.get(ip, False)
            is_active = (arp_dev is not None) or ping_ok
            
            # Limpeza rigorosa do vendor
            raw_vendor = arp_dev.get('vendor') if arp_dev else None
            vendor = self._clean_vendor(raw_vendor)

            dev = {
                'ip': ip,
                'mac': mac,
                'hostname': lease.get('host-name') or lease.get('comment') or "-",
                'vendor': vendor,
                'status': 'Ativo' if is_active else 'Invisível (DHCP Record)',
            }
            consolidated.append(dev)

        # Adiciona dispositivos manuais/estáticos detectados apenas via ARP
        for mac, dev in devices_by_mac.items():
            if mac not in dhcp_macs:
                dev_copy = dev.copy()
                dev_copy['vendor'] = self._clean_vendor(dev_copy.get('vendor'))
                # Se foi detectado pelo ARPScanner, está obrigatoriamente ativo
                dev_copy['status'] = 'Ativo (Manual)'
                consolidated.append(dev_copy)
        
        return consolidated

    async def _execute_pipeline(self) -> dict:
        """Execução principal assíncrona da pipeline com polimento de visibilidade."""
        gateway_ip = self.config.subnet.split('/')[0].replace('.0', '.1')
        
        # 1. Coleta inicial de Leases (Base para o Wake-up call)
        leases = get_dhcp_details(host=gateway_ip) or []
        dhcp_ips = [l.get('address') for l in leases if l.get('address')]

        # 2. "Wake-up call" via Ping para popular tabela ARP do Linux
        async def ping_ip(ip):
            proc = await asyncio.create_subprocess_exec(
                'ping', '-c', '1', '-W', '1', ip,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.communicate()
            return ip, proc.returncode == 0

        if dhcp_ips:
            ping_results = await asyncio.gather(*(ping_ip(ip) for ip in dhcp_ips))
            ping_status = {ip: success for ip, success in ping_results}
        else:
            ping_status = {}

        # Ajuste Crítico: Espera de 3 segundos para garantir que a tabela ARP seja populada
        # após as respostas dos dispositivos (essencial para o FOX-NOTE)
        await asyncio.sleep(3)

        # 3. Executa ARP Scanner (Agora com maior probabilidade de sucesso)
        try:
            arp_scanner = ARPScanner(subnet=self.config.subnet, iface=self.config.interface)
            arp_raw = [item.to_dict() for item in arp_scanner.scan()]
        except:
            arp_raw = []

        # 4. Consolidação
        merged_devices = self.consolidate_devices(arp_raw, leases, ping_status)

        # 5. Inicialização do Payload principal
        payload = {
            "devices": merged_devices,
            "mikrotik_health": {},
            "mikrotik_wan_status": [],
            "mikrotik_neighbors": [],
            "interface": self.config.interface,
            "ssdp": [],
            "mdns": [],
            "dns": {},
            "route": {},
        }

        # 6. SNMP Health (Temperatura, CPU, Uptime)
        if self.config.snmp_enabled:
            try:
                payload["mikrotik_health"] = await get_mikrotik_health(gateway_ip, community=self.config.snmp_community)
            except Exception as e:
                payload["mikrotik_health"] = {"error": str(e)}

        # 7. MikroTik API (WAN e Vizinhos)
        payload["mikrotik_wan_status"] = get_wan_status(host=gateway_ip) or []
        payload["mikrotik_neighbors"] = get_neighbors(host=gateway_ip) or []

        # 8. Scanners Adicionais
        payload["ssdp"] = SSDPScanner().discover() if self.config.ssdp_enabled else []
        payload["mdns"] = MDNSScanner().discover() if self.config.mdns_enabled else []
        payload["dns"] = DNSTester().test(self.config.dns_test_domain) if self.config.dns_enabled else {}
        payload["route"] = RouteAnalyzer().analyze(self.config.traceroute_target) if self.config.route_enabled else {}

        # 9. Topologia e PRD Acceptance
        payload["topology"] = TopologyBuilder().build(
            devices=merged_devices,
            ssdp=payload["ssdp"],
            mdns=payload["mdns"]
        )
        
        # Limpeza final de Vendor em todos os nós da topologia para remover tuplas remanescentes
        for node in payload["topology"].get("nodes", []):
            node['vendor'] = self._clean_vendor(node.get('vendor'))

        payload["findings"] = ProblemDetector().detect(payload)
        payload["prd_acceptance"] = AcceptanceEvaluator().evaluate(payload, self.config.expected_active_hosts)

        # 10. Diagnóstico AI (Gemini)
        if self.config.gemini_api_key:
            try:
                gemini = GeminiAnalyzer(api_key=self.config.gemini_api_key, model=self.config.gemini_model)
                payload["ai_diagnosis"] = gemini.analyze(payload)
            except Exception as e:
                payload["ai_error"] = str(e)

        return payload

    def run(self) -> dict:
        return asyncio.run(self._execute_pipeline())

    def run_with_metadata(self) -> dict:
        return ReportGenerator().build(self.run())

    def save_report(self, report: dict, path: str = "network_report.json") -> str:
        return str(ReportGenerator().save(report, path=path))

    def save_markdown_report(self, report: dict, path: str = "network_report.md") -> str:
        return str(ReportGenerator().save_markdown(report, path=path))

    @staticmethod
    def load_report(path: str = "network_report.json") -> dict:
        return ReportGenerator().load(path=path)