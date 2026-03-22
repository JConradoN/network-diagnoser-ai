
"""Gerador de relatórios de diagnóstico de rede."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ReportGenerator:
    def build(self, payload: dict) -> dict:
        """Adiciona metadados e retorna o relatório envelopado."""
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "report": payload,
        }

    def save(self, report: dict, path: str = "network_report.json") -> Path:
        """Salva o relatório em JSON."""
        output_path = Path(path)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_path

    def save_markdown(self, report: dict, path: str = "network_report.md") -> Path:
        """Salva o relatório em Markdown."""
        output_path = Path(path)
        output_path.write_text(self.to_markdown(report), encoding="utf-8")
        return output_path

    def to_markdown(self, report: dict) -> str:
        """Gera o relatório em Markdown detalhado."""
        payload = report.get("report", {})
        generated_at = report.get("generated_at", "N/A")

        merged_devices = payload.get("devices", [])
        findings = payload.get("findings", [])
        ai_diagnosis = payload.get("ai_diagnosis")
        ai_error = payload.get("ai_error")
        prd_acceptance = payload.get("prd_acceptance")
        topology = payload.get("topology")
        arp_devices = payload.get("arp_devices", [])
        device_scanner_devices = payload.get("device_scanner_devices", [])
        mikrotik_health = payload.get("mikrotik_health", {})
        mikrotik_wan_status = payload.get("mikrotik_wan_status", {})
        mikrotik_dhcp_leases = payload.get("mikrotik_dhcp_leases", {})
        mikrotik_neighbors = payload.get("mikrotik_neighbors", {})

        lines = []
        lines.append("# Network Diagnoser Report")
        lines.append("")
        lines.append(f"- Gerado em: {generated_at}")
        lines.append(f"- Dispositivos identificados: {len(merged_devices)}")
        lines.append(f"- Findings: {len(findings)}")
        lines.append("")

        lines.append("## Dispositivos Consolidados (ARP + DHCP)")
        if merged_devices:
            for dev in merged_devices:
                hostname = dev.get("hostname") or dev.get("dhcp_hostname") or "-"
                lines.append(f"- IP: {dev.get('ip', '-')}, MAC: {dev.get('mac', '-')}, Hostname: {hostname}")
        else:
            lines.append("- Nenhum dispositivo consolidado.")
        lines.append("")

        lines.append("## Mikrotik Health (SNMP)")
        lines.append("```json")
        lines.append(json.dumps(mikrotik_health, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")

        lines.append("## Mikrotik WAN Status")
        lines.append("```json")
        lines.append(json.dumps(mikrotik_wan_status, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")

        lines.append("## Mikrotik DHCP Leases")
        lines.append("```json")
        lines.append(json.dumps(mikrotik_dhcp_leases, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")

        lines.append("## Mikrotik Neighbors")
        lines.append("```json")
        lines.append(json.dumps(mikrotik_neighbors, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")

        lines.append("## Dispositivos ARP (legacy)")
        lines.append("```json")
        lines.append(json.dumps(arp_devices, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")

        lines.append("## Dispositivos DeviceScanner")
        lines.append("```json")
        lines.append(json.dumps(device_scanner_devices, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")

        lines.append("## Diagnóstico AI")
        if ai_diagnosis:
            if isinstance(ai_diagnosis, dict):
                lines.append("```json")
                lines.append(json.dumps(ai_diagnosis, ensure_ascii=False, indent=2))
                lines.append("```")
            else:
                lines.append(str(ai_diagnosis))
        elif ai_error:
            lines.append(f"Erro AI: {ai_error}")
        else:
            lines.append("- Não disponível.")
        lines.append("")

        lines.append("## PRD Acceptance")
        if prd_acceptance:
            lines.append("```json")
            lines.append(json.dumps(prd_acceptance, ensure_ascii=False, indent=2))
            lines.append("```")
        else:
            lines.append("- Não disponível.")
        lines.append("")

        lines.append("## Topologia")
        if topology:
            lines.append("```json")
            lines.append(json.dumps(topology, ensure_ascii=False, indent=2))
            lines.append("```")
        else:
            lines.append("- Não disponível.")
        lines.append("")

        lines.append("## Findings")
        if not findings:
            lines.append("- No findings detected.")
        else:
            for idx, finding in enumerate(findings, start=1):
                lines.append(f"### {idx}. {finding.get('id', 'UNKNOWN')}")
                lines.append(f"- Severity: {finding.get('severity', 'unknown')}")
                lines.append(f"- Message: {finding.get('message', '')}")
                lines.append(f"- Evidence: {json.dumps(finding.get('evidence', {}), ensure_ascii=False)}")
                lines.append("")

        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def load(path: str = "network_report.json") -> dict:
        """Carrega um relatório JSON do disco."""
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Relatório não encontrado: {path}")
        return json.loads(file_path.read_text(encoding="utf-8"))
        return json.loads(file_path.read_text(encoding="utf-8"))