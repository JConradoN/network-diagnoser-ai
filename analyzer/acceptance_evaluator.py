"""Acceptance criteria evaluator for PRD tracking."""

from __future__ import annotations

import json
import ipaddress
from typing import Any


class AcceptanceEvaluator:
    """Evaluate PRD acceptance criteria against generated payload."""

    def evaluate(self, payload: dict[str, Any], expected_active_hosts: int | None = None) -> dict[str, Any]:
        """Return criterion-by-criterion status for CA01..CA05."""
        criteria: dict[str, dict[str, Any]] = {
            "CA01": self._evaluate_ca01(payload, expected_active_hosts),
            "CA02": self._evaluate_ca02(payload),
            "CA03": self._evaluate_ca03(payload),
            "CA04": self._evaluate_ca04(payload),
            "CA05": self._evaluate_ca05(payload),
        }

        passed = sum(1 for item in criteria.values() if item.get("status") == "passed")
        failed = sum(1 for item in criteria.values() if item.get("status") == "failed")
        not_evaluated = sum(1 for item in criteria.values() if item.get("status") == "not_evaluated")

        return {
            "summary": {
                "passed": passed,
                "failed": failed,
                "not_evaluated": not_evaluated,
                "total": len(criteria),
            },
            "criteria": criteria,
        }

    @staticmethod
    def _evaluate_ca01(payload: dict[str, Any], expected_active_hosts: int | None) -> dict[str, Any]:
        """CA01: Cobertura de descoberta de dispositivos >= 90%."""
        devices = payload.get("devices", [])
        # Contamos apenas os que estão realmente 'Ativo' (incluindo Ativo (Manual))
        active_found = sum(1 for d in devices if "Ativo" in str(d.get("status", "")))
        
        if not expected_active_hosts or expected_active_hosts <= 0:
            return {
                "status": "not_evaluated",
                "message": "Defina expected_active_hosts para avaliar cobertura.",
                "details": {
                    "active_found": active_found,
                    "expected_active_hosts": expected_active_hosts,
                },
            }

        coverage = (active_found / expected_active_hosts) * 100.0
        return {
            "status": "passed" if coverage >= 90.0 else "failed",
            "message": "Cobertura de descoberta de dispositivos ativos.",
            "details": {
                "active_found": active_found,
                "expected_active_hosts": expected_active_hosts,
                "coverage_percent": round(coverage, 2),
            },
        }

    @staticmethod
    def _evaluate_ca02(payload: dict[str, Any]) -> dict[str, Any]:
        """
        CA02: Detecção de NAT múltiplo (Double NAT).
        O critério 'falha' (failed) se um Double NAT for detectado.
        """
        route = payload.get("route", {})
        hops = route.get("hops", [])
        ssdp = payload.get("ssdp", [])
        findings = payload.get("findings", [])
        
        # Gateway padrão da sua rede MikroTik
        local_gateway = "192.168.88.1"
        
        is_private_first_hop = False
        first_hop_ip = "unknown"

        # 1. Analisa o primeiro salto (Hop 0) do traceroute
        if hops:
            first_hop_ip = hops[0].get("ip", "")
            try:
                ip_obj = ipaddress.ip_address(first_hop_ip)
                # Se o primeiro salto é privado e NÃO é o MikroTik, temos um roteador ISP no meio
                if ip_obj.is_private and first_hop_ip != local_gateway:
                    is_private_first_hop = True
            except ValueError:
                pass

        # 2. Analisa SSDP vindo de fora da sub-rede local (ex: 192.168.100.1 do ISP)
        ssdp_external = False
        for item in ssdp:
            ip = item.get("ip", "")
            if ip and not ip.startswith("192.168.88."):
                ssdp_external = True
                break

        # 3. Cruzamento com detector de problemas (Finding ID)
        has_double_nat_finding = any(f.get("id") == "DOUBLE_NAT" for f in findings)
        
        # O problema é detetado se qualquer uma das condições for verdadeira
        detected = is_private_first_hop or ssdp_external or has_double_nat_finding

        return {
            "status": "failed" if detected else "passed",
            "message": "Presença de NAT múltiplo (Double NAT) detetada." if detected else "Configuração de NAT única.",
            "details": {
                "detected": detected,
                "first_hop_is_private": is_private_first_hop,
                "first_hop_ip": first_hop_ip,
                "ssdp_external_detected": ssdp_external
            },
        }

    @staticmethod
    def _evaluate_ca03(payload: dict[str, Any]) -> dict[str, Any]:
        """CA03: Detecção de DHCP duplicado e integridade de vizinhos."""
        supported = "mikrotik_neighbors" in payload 
        findings = payload.get("findings", [])
        duplicate_detected = any(f.get("id") == "DUPLICATE_DHCP" for f in findings)
        
        return {
            "status": "passed" if supported and not duplicate_detected else "failed",
            "message": "Deteccao de DHCP duplicado e integridade.",
            "details": {
                "supported": supported,
                "duplicate_detected": duplicate_detected
            },
        }

    @staticmethod
    def _evaluate_ca04(payload: dict[str, Any]) -> dict[str, Any]:
        """CA04: Diagnóstico via Gemini gerado com sucesso."""
        # Garante que existe conteúdo no diagnóstico AI
        has_ai = "ai_diagnosis" in payload and payload["ai_diagnosis"] is not None
        has_error = "ai_error" in payload or payload.get("ai_diagnosis") == "Não disponível."
        
        return {
            "status": "passed" if has_ai and not has_error else "failed",
            "message": "Diagnóstico via Gemini gerado com sucesso.",
            "details": {
                "has_ai_diagnosis": has_ai,
                "has_ai_error": payload.get("ai_error") if has_error else None
            },
        }

    @staticmethod
    def _evaluate_ca05(payload: dict[str, Any]) -> dict[str, Any]:
        """CA05: Verificação de integridade e serialização JSON do relatório."""
        try:
            json.dumps(payload, ensure_ascii=False)
            status = "passed"
            error_msg = None
        except (TypeError, ValueError) as exc:
            status = "failed"
            error_msg = str(exc)
            
        return {
            "status": status,
            "message": "Relatório serializável em JSON válido.",
            "details": {} if status == "passed" else {"error": error_msg},
        }