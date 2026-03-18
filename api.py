from __future__ import annotations
"""FastAPI interface for Network Diagnoser AI - Versão Final Polida."""

import os
import asyncio
import logging
from typing import Any
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import AppConfig, load_config
from services.diagnosis_service import DiagnosisService
from utils.network_utils import list_network_interfaces

app = FastAPI(title="Network Diagnoser AI API")

# Configuração de CORS para permitir acesso do Frontend (Porta 8080)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Modelos de Dados ---

class ScanRequest(BaseModel):
    subnet: str = Field(default="192.168.88.0/24")
    interface: str | None = Field(default=None)
    ping_count: int = 4
    dns_test_domain: str = "google.com"
    traceroute_target: str = "8.8.8.8"
    expected_active_hosts: int = 30
    snmp_enabled: bool = True
    mdns_enabled: bool = True
    ssdp_enabled: bool = True
    latency_enabled: bool = True
    dns_enabled: bool = True
    route_enabled: bool = True
    dhcp_enabled: bool = True
    port_scan_enabled: bool = True

# --- Endpoints ---

@app.get("/interfaces")
async def get_interfaces():
    """Retorna as placas de rede válidas do sistema."""
    try:
        return {"interfaces": list_network_interfaces()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scan/save")
async def run_scan_and_save(req: ScanRequest):
    """Executa o diagnóstico e salva os resultados."""
    try:
        cfg = load_config()
        # Sobrescreve configurações com dados do request
        cfg = cfg.__class__(
            subnet=req.subnet,
            interface=req.interface or cfg.interface,
            ping_count=req.ping_count,
            dns_test_domain=req.dns_test_domain,
            traceroute_target=req.traceroute_target,
            expected_active_hosts=req.expected_active_hosts,
            snmp_enabled=req.snmp_enabled,
            mdns_enabled=req.mdns_enabled,
            ssdp_enabled=req.ssdp_enabled,
            latency_enabled=req.latency_enabled,
            dns_enabled=req.dns_enabled,
            route_enabled=req.route_enabled,
            dhcp_enabled=req.dhcp_enabled,
            port_scan_enabled=req.port_scan_enabled,
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            snmp_community=os.getenv("ND_SNMP_COMMUNITY", "public")
        )

        service = DiagnosisService(cfg)
        
        # CORREÇÃO CRÍTICA: Aguardando a corrotina assíncrona
        payload = await service._execute_pipeline()
        
        # Gera metadados e formata o relatório final
        from output.report_generator import ReportGenerator
        report_with_meta = ReportGenerator().build(payload)
        
        # Persistência
        service.save_report(report_with_meta, path="network_report.json")
        service.save_markdown_report(report_with_meta, path="network_report.md")

        return {"status": "success", "generated_at": report_with_meta.get("generated_at")}
    
    except Exception as e:
        logging.error(f"Erro no Scan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard/stats")
async def get_dashboard_stats():
    """Dados resumidos para o Dashboard Web."""
    try:
        if not os.path.exists("network_report.json"):
            return {"error": "Sem dados"}
            
        report = DiagnosisService.load_report(path="network_report.json")
        data = report.get("report", {})
        health = data.get("mikrotik_health", {})
        devices = data.get("devices", [])
        
        # Pega o status do CA02 (Double NAT)
        prd = data.get("prd_acceptance", {}).get("criteria", {})
        nat_failed = prd.get("CA02", {}).get("status") == "failed"

        return {
            "mikrotik": {
                "temperature": health.get("temperature", 0),
                "voltage": health.get("voltage", 0),
                "cpu": health.get("cpu_usage", 0),
                "uptime": health.get("uptime_str", "N/A")
            },
            "stats": {
                "active_devices": sum(1 for d in devices if "Ativo" in str(d.get("status"))),
                "total_devices": len(devices),
                "double_nat_alert": nat_failed
            },
            "raw_report": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report/pdf")
async def download_pdf():
    """
    Ponto 4: Exporta o relatório em PDF. 
    Requer a instalação de: pip install fpdf2
    """
    from fpdf import FPDF
    
    md_path = "network_report.md"
    pdf_path = "network_report.pdf"
    
    if not os.path.exists(md_path):
        raise HTTPException(status_code=404, detail="Gere um scan primeiro.")

    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        
        for line in content.split("\n"):
            # Limpeza simples de caracteres Markdown para o PDF
            clean_line = line.replace("#", "").replace("*", "").replace("`", "")
            pdf.cell(200, 8, txt=clean_line, ln=True)
            
        pdf.output(pdf_path)
        return FileResponse(pdf_path, media_type="application/pdf", filename="relatorio_rede.pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)