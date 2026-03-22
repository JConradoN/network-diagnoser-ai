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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
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
        """Limpa vendor, retorna sempre o nome do fabricante."""
        import ast
        if isinstance(v, (list, tuple)) and len(v) > 0:
            return str(v[-1])
        if isinstance(v, str):
            try:
                parsed = ast.literal_eval(v)
                if isinstance(parsed, (list, tuple)) and len(parsed) > 0:
                    return str(parsed[-1])
            except Exception:
                pass
            if v and v != "None":
                return v
        return "-"

    def consolidate_devices(self, arp_devices: list, dhcp_leases: list, ping_status: dict) -> list:
        """Une ARP e DHCP priorizando nomes do MikroTik."""
        devices_by_mac = {dev['mac'].lower(): dev for dev in arp_devices}
        consolidated = []
        dhcp_macs = set()

        for lease in dhcp_leases:
            if not isinstance(lease, dict):
                if isinstance(lease, str) and lease != "error":
                    consolidated.append({
                        'ip': lease, 'mac': '', 'hostname': '-', 'vendor': '-',
                        'status': 'Invisível (DHCP Record)'
                    })
                continue
            
            mac = (lease.get('mac-address') or "").lower()
            if not mac: continue
            dhcp_macs.add(mac)
            
            arp_dev = devices_by_mac.get(mac)
            ip = lease.get('address', arp_dev['ip'] if arp_dev else '-')
            if ip == "error": continue
            
            if mac.upper().startswith("F4:1E:57"):
                vendor = "MikroTik/Routerboard"
            elif mac.upper().startswith("98:2A:0A"):
                vendor = "Intelbras (Twibi)"
            else:
                raw_vendor = arp_dev.get('vendor') if arp_dev else None
                vendor = self._clean_vendor(raw_vendor)
            
            ping_ok = ping_status.get(ip, False)
            is_active = (arp_dev is not None) or ping_ok
            
            consolidated.append({
                'ip': ip, 'mac': mac,
                'hostname': lease.get('host-name') or lease.get('comment') or "-",
                'vendor': vendor,
                'status': 'Ativo' if is_active else 'Invisível (DHCP Record)',
            })

        for mac, dev in devices_by_mac.items():
            if mac not in dhcp_macs:
                dev_copy = dev.copy()
                if mac.upper().startswith("F4:1E:57"):
                    dev_copy['vendor'] = "MikroTik/Routerboard"
                elif mac.upper().startswith("98:2A:0A"):
                    dev_copy['vendor'] = "Intelbras (Twibi)"
                else:
                    dev_copy['vendor'] = self._clean_vendor(dev_copy.get('vendor'))
                dev_copy['status'] = 'Ativo (Manual)'
                consolidated.append(dev_copy)

        # Deduplica por IP: mantém a entrada com mais informação (hostname > '-', status Ativo > Invisível)
        by_ip: dict = {}
        for dev in consolidated:
            ip = dev.get('ip', '')
            if not ip or ip == '-':
                continue
            existing = by_ip.get(ip)
            if existing is None:
                by_ip[ip] = dev
            else:
                # Prefere entrada com hostname real
                has_name     = dev.get('hostname', '-') not in ('-', '', None)
                exists_name  = existing.get('hostname', '-') not in ('-', '', None)
                # Prefere status Ativo sobre Invisível
                is_active    = 'Ativo' in dev.get('status', '')
                exists_active = 'Ativo' in existing.get('status', '')
                if (has_name and not exists_name) or (is_active and not exists_active):
                    by_ip[ip] = dev

        return sorted(by_ip.values(), key=lambda d: list(map(int, d['ip'].split('.'))))

    async def _execute_pipeline(self) -> dict:
        """Execução principal assíncrona da pipeline."""
        gateway_ip = self.config.subnet.split('/')[0].replace('.0', '.1')
        mikrotik_ip = os.getenv("ND_MIKROTIK_HOST", "192.168.88.1")

        logger.info("--- [STAGE] 1/10: Coleta de Leases DHCP ---")
        leases = get_dhcp_details(host=mikrotik_ip) or []
        dhcp_ips = [l.get('address') if isinstance(l, dict) else l for l in leases if l]

        logger.info("--- [STAGE] 2/10: Wake-up call (Ping Sweep) ---")
        async def ping_ip(ip):
            proc = await asyncio.create_subprocess_exec(
                'ping', '-c', '1', '-W', '1', ip,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
            )
            await proc.communicate()
            return ip, proc.returncode == 0

        ping_status = {}
        if dhcp_ips:
            results = await asyncio.gather(*(ping_ip(ip) for ip in dhcp_ips if ip and ip != "error"))
            ping_status = dict(results)

        await asyncio.sleep(1)

        logger.info("--- [STAGE] 3/10: ARP Scanner ---")
        try:
            arp_scanner = ARPScanner(subnet=self.config.subnet, iface=self.config.interface)
            arp_raw = [item.to_dict() for item in arp_scanner.scan()]
        except:
            arp_raw = []

        merged_devices = self.consolidate_devices(arp_raw, leases, ping_status)

        payload = {
            "devices": merged_devices, "mikrotik_health": {}, "mikrotik_wan_status": [],
            "mikrotik_neighbors": [], "interface": self.config.interface,
            "ssdp": [], "mdns": [], "dns": {}, "route": {}, "topology": {}
        }

        logger.info("--- [STAGE] 6/10: Coleta SNMP Health + RouterOS API ---")
        if self.config.snmp_enabled:
            try:
                payload["mikrotik_health"] = await get_mikrotik_health(mikrotik_ip, community=self.config.snmp_community)
            except Exception as e:
                payload["mikrotik_health"] = {"error": str(e)}

        # WAN status e neighbors via RouterOS API
        loop = asyncio.get_running_loop()
        try:
            payload["mikrotik_wan_status"] = await loop.run_in_executor(None, get_wan_status)
        except Exception as e:
            logger.warning(f"WAN status não disponível: {e}")
            payload["mikrotik_wan_status"] = []
        try:
            payload["mikrotik_neighbors"] = await loop.run_in_executor(None, get_neighbors)
        except Exception as e:
            logger.warning(f"Neighbors não disponível: {e}")
            payload["mikrotik_neighbors"] = []

        payload["ssdp"] = SSDPScanner().discover() if self.config.ssdp_enabled else []
        payload["mdns"] = MDNSScanner().discover() if self.config.mdns_enabled else []
        payload["dns"] = DNSTester().test(self.config.dns_test_domain) if self.config.dns_enabled else {}
        payload["route"] = RouteAnalyzer().analyze(self.config.traceroute_target) if self.config.route_enabled else {}

        payload["topology"] = TopologyBuilder().build(merged_devices, payload["ssdp"], payload["mdns"])
        payload["findings"] = ProblemDetector().detect(payload)
        payload["prd_acceptance"] = AcceptanceEvaluator().evaluate(payload, self.config.expected_active_hosts)

        logger.info("--- [STAGE] 10/10: Análise Gemini AI ---")
        if self.config.gemini_api_key:
            # Desativado cache para validação de Hot-Reload
            logger.info("📡 Iniciando requisição real ao Gemini...")
            try:
                gemini = GeminiAnalyzer(api_key=self.config.gemini_api_key, model=self.config.gemini_model)
                payload["ai_diagnosis"] = gemini.analyze(payload)
                logger.info("✅ Gemini retornou dados com sucesso.")
            except Exception as e:
                logger.error(f"❌ Falha no Gemini: {e}")
                payload["ai_error"] = str(e)

        return payload

    async def run(self, interface=None, subnet=None, modules=None):
        if interface: self.config.interface = interface
        if subnet: self.config.subnet = subnet
        return await self._execute_pipeline()