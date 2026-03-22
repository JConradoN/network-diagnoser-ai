"""
Generates a professional PDF management report from the latest scan data.
Uses fpdf2 library.
"""
from __future__ import annotations
import os
import io
import json
from datetime import datetime
from typing import Any

from fpdf import FPDF, XPos, YPos


FONT_DIR     = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")
FONT_BOLD    = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
FONT_MONO    = os.path.join(FONT_DIR, "DejaVuSansMono.ttf")

BRAND_DARK   = (15, 23, 42)      # slate-900
BRAND_ACCENT = (6, 182, 212)     # cyan-400
GREEN        = (34, 197, 94)
YELLOW       = (234, 179, 8)
RED          = (239, 68, 68)
GRAY         = (100, 113, 133)
WHITE        = (255, 255, 255)
LIGHT_BG     = (241, 245, 249)


def _status_color(status: str):
    s = (status or "").upper()
    if "CRÍTICO" in s or "CRÍTICA" in s:   return RED
    if "ATENÇÃO" in s or "ATENCAO" in s:   return YELLOW
    if "NORMAL" in s or "OPERACIONAL" in s: return GREEN
    return GRAY


class FoxNOCReport(FPDF):
    def __init__(self, scan_data: dict):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.scan_data = scan_data
        self.generated_at = datetime.now().strftime("%d/%m/%Y às %H:%M")
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(20, 20, 20)
        # Fontes Unicode (suporte completo a português e caracteres especiais)
        self.add_font("DejaVu",      style="",  fname=FONT_REGULAR)
        self.add_font("DejaVu",      style="B", fname=FONT_BOLD)
        self.add_font("DejaVuMono",  style="",  fname=FONT_MONO)

    # ── helpers ────────────────────────────────────────────────────────────
    def _fill_rect(self, x, y, w, h, color):
        self.set_fill_color(*color)
        self.rect(x, y, w, h, style="F")

    def _colored_badge(self, text: str, color):
        self.set_fill_color(*color)
        self.set_text_color(*WHITE)
        self.set_font("DejaVu", "B", 9)
        self.cell(0, 7, f"  {text}  ", border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True, align="C")
        self.set_text_color(0, 0, 0)

    def _section_title(self, title: str):
        self.ln(4)
        self.set_fill_color(*BRAND_ACCENT)
        self.rect(self.get_x(), self.get_y(), 4, 7, style="F")
        self.set_x(self.get_x() + 6)
        self.set_font("DejaVu", "B", 13)
        self.set_text_color(*BRAND_DARK)
        self.cell(0, 7, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*BRAND_ACCENT)
        self.set_line_width(0.3)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def _table_header(self, cols: list[tuple[str, int]]):
        self.set_fill_color(*BRAND_DARK)
        self.set_text_color(*WHITE)
        self.set_font("DejaVu", "B", 9)
        for label, w in cols:
            self.cell(w, 7, label, border=0, fill=True, align="C")
        self.ln()
        self.set_text_color(0, 0, 0)

    def _table_row(self, values: list[tuple[str, int]], shade: bool):
        self.set_fill_color(*(LIGHT_BG if shade else WHITE))
        self.set_font("DejaVu", "", 8)
        for val, w in values:
            self.cell(w, 6, str(val)[:40], border=0, fill=True)
        self.ln()

    # ── cover ───────────────────────────────────────────────────────────────
    def cover_page(self):
        self.add_page()
        # dark header bar
        self._fill_rect(0, 0, 210, 80, BRAND_DARK)
        self.set_y(20)
        self.set_font("DejaVu", "B", 28)
        self.set_text_color(*BRAND_ACCENT)
        self.cell(0, 12, "FOX NOC", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("DejaVu", "", 14)
        self.set_text_color(*WHITE)
        self.cell(0, 8, "Relatório Gerencial de Rede", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("DejaVu", "", 10)
        self.set_text_color(*GRAY)
        self.cell(0, 6, f"Gerado em {self.generated_at}", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # status badge
        ai = self.scan_data.get("ai_diagnosis") or {}
        if isinstance(ai, dict) and "parsed" in ai: ai = ai["parsed"]
        status = ai.get("status_geral", "N/A") if isinstance(ai, dict) else "N/A"
        color  = _status_color(status)
        self._fill_rect(70, 90, 70, 18, color)
        self.set_y(94)
        self.set_font("DejaVu", "B", 12)
        self.set_text_color(*WHITE)
        self.cell(0, 8, f"STATUS GERAL: {status}", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)

        # summary boxes
        self.set_y(120)
        devices = self.scan_data.get("devices", [])
        active  = len([d for d in devices if "Ativo" in d.get("status", "")])
        mk      = self.scan_data.get("mikrotik_health", {})

        boxes = [
            ("Dispositivos", str(len(devices)), BRAND_DARK),
            ("Ativos",       str(active),       GREEN),
            ("CPU MikroTik", f"{mk.get('cpu_usage','?')}%", BRAND_ACCENT),
            ("Temperatura",  f"{mk.get('temperature','?')}°C", YELLOW),
        ]
        bw = 37
        bx = 20
        for label, value, color in boxes:
            self._fill_rect(bx, 120, bw, 24, color)
            self.set_xy(bx, 122)
            self.set_font("DejaVu", "B", 18)
            self.set_text_color(*WHITE)
            self.cell(bw, 10, value, align="C")
            self.set_xy(bx, 133)
            self.set_font("DejaVu", "", 8)
            self.cell(bw, 5, label, align="C")
            bx += bw + 4
        self.set_text_color(0, 0, 0)

    # ── executive summary ───────────────────────────────────────────────────
    def executive_summary(self):
        self.add_page()
        self._section_title("1. Resumo Executivo")
        ai = self.scan_data.get("ai_diagnosis") or {}
        if isinstance(ai, dict) and "parsed" in ai: ai = ai["parsed"]
        diag = (ai.get("diagnostico_detalhado", "") if isinstance(ai, dict) else "") or "Não disponível."
        self.set_font("DejaVu", "", 10)
        self.set_text_color(*BRAND_DARK)
        self.multi_cell(0, 6, diag)
        self.ln(4)

        # findings
        problems = (ai.get("problemas_identificados", []) or []) if isinstance(ai, dict) else []
        if problems:
            self._section_title("Problemas Identificados")
            for i, p in enumerate(problems, 1):
                self.set_font("DejaVu", "B", 9)
                self.set_text_color(*RED)
                self.cell(6, 6, f"{i}.")
                self.set_font("DejaVu", "", 9)
                self.set_text_color(*BRAND_DARK)
                self.multi_cell(0, 6, str(p))

        actions = (ai.get("acoes_recomendadas", []) or []) if isinstance(ai, dict) else []
        if actions:
            self._section_title("Ações Recomendadas")
            for i, a in enumerate(actions, 1):
                self.set_font("DejaVu", "B", 9)
                self.set_text_color(*GREEN)
                self.cell(6, 6, f"{i}.")
                self.set_font("DejaVu", "", 9)
                self.set_text_color(*BRAND_DARK)
                self.multi_cell(0, 6, str(a))

    # ── device inventory ───────────────────────────────────────────────────
    def device_inventory(self):
        self.add_page()
        self._section_title("2. Inventário de Dispositivos")
        cols = [("IP", 38), ("Hostname", 45), ("Fabricante", 60), ("MAC", 38), ("Status", 29)]
        self._table_header(cols)
        for i, dev in enumerate(sorted(self.scan_data.get("devices", []), key=lambda d: d.get("ip",""))):
            self._table_row([
                (dev.get("ip","-"),       38),
                (dev.get("hostname","-"), 45),
                (dev.get("vendor","-"),   60),
                (dev.get("mac","-"),      38),
                (dev.get("status","-"),   29),
            ], shade=i % 2 == 0)

    # ── mikrotik health ────────────────────────────────────────────────────
    def mikrotik_health(self):
        self.add_page()
        self._section_title("3. Saúde do Roteador MikroTik")
        mk = self.scan_data.get("mikrotik_health", {})
        if mk.get("snmp_error"):
            self.set_font("DejaVu", "", 10)
            self.multi_cell(0, 6, f"SNMP indisponível: {mk['snmp_error']}")
            return

        metrics = [
            ("CPU", f"{mk.get('cpu_usage','?')} %"),
            ("Temperatura", f"{mk.get('temperature','?')} °C"),
            ("Voltagem", f"{mk.get('voltage','?')} V"),
            ("Uptime", str(mk.get("uptime_str","?"))),
            ("Memória livre", f"{mk.get('mem_free','?')} KB"),
        ]
        self.set_font("DejaVu", "", 10)
        for label, value in metrics:
            self._fill_rect(20, self.get_y(), 170, 8, LIGHT_BG)
            self.set_x(22)
            self.set_font("DejaVu", "B", 10)
            self.cell(60, 8, label)
            self.set_font("DejaVu", "", 10)
            self.cell(0, 8, value, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # WAN
        wan = self.scan_data.get("mikrotik_wan_status", [])
        if wan:
            self.ln(4)
            self._section_title("Interfaces WAN")
            cols = [("Interface", 50), ("Status", 30), ("IP", 55), ("TX/RX", 55)]
            self._table_header(cols)
            for i, w in enumerate(wan):
                self._table_row([
                    (w.get("name","-"), 50),
                    (w.get("running","?"), 30),
                    (w.get("address","-"), 55),
                    (f"{w.get('tx-byte','?')} / {w.get('rx-byte','?')}", 55),
                ], shade=i%2==0)

    # ── network tests ──────────────────────────────────────────────────────
    def network_tests(self):
        self.add_page()
        self._section_title("4. Testes de Rede")

        dns = self.scan_data.get("dns", {})
        if dns:
            self.set_font("DejaVu", "B", 11)
            self.cell(0, 8, "DNS", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_font("DejaVu", "", 10)
            status = "OK" if dns.get("resolved") else "FALHA"
            addrs  = ", ".join(dns.get("addresses", []))
            self.multi_cell(0, 6, f"Domínio: {dns.get('domain','-')}  |  Status: {status}  |  Latência: {dns.get('elapsed_ms','-')} ms\nEndereços: {addrs}")
            self.ln(3)

        route = self.scan_data.get("route", {})
        hops  = route.get("hops", [])
        if hops:
            self._section_title("Traceroute")
            cols = [("Hop", 15), ("IP", 55), ("Latência (ms)", 40), ("Privado", 30), ("Gargalo", 30)]
            self._table_header(cols)
            for i, hop in enumerate(hops):
                if hop.get("ip") == "*": continue
                self._table_row([
                    (str(hop.get("hop_num",i+1)), 15),
                    (hop.get("ip","-"),            55),
                    (f"{hop.get('latency',0):.1f}", 40),
                    ("Sim" if hop.get("is_private") else "Não", 30),
                    ("!" if hop.get("is_bottleneck") else "-",   30),
                ], shade=i%2==0)

    # ── topology ───────────────────────────────────────────────────────────
    def topology_section(self):
        self.add_page()
        self._section_title("5. Topologia da Rede")
        topo = self.scan_data.get("topology", {})
        nodes = topo.get("nodes", [])
        edges = topo.get("edges", [])
        self.set_font("DejaVu", "", 10)
        self.multi_cell(0, 6,
            f"Nós detectados: {len(nodes)}  |  Conexões mapeadas: {len(edges)}"
        )
        self.ln(2)
        if nodes:
            cols = [("ID/IP", 55), ("Tipo", 40), ("Label", 75)]
            self._table_header(cols)
            for i, n in enumerate(nodes):
                self._table_row([
                    (n.get("id","-"),    55),
                    (n.get("type","-"),  40),
                    (n.get("label","-"), 75),
                ], shade=i%2==0)

    # ── footer/header override ─────────────────────────────────────────────
    def header(self):
        if self.page_no() == 1:
            return
        self._fill_rect(0, 0, 210, 12, BRAND_DARK)
        self.set_y(3)
        self.set_font("DejaVu", "B", 8)
        self.set_text_color(*BRAND_ACCENT)
        self.cell(0, 6, "FOX NOC | Relatorio Gerencial de Rede", align="C")
        self.set_text_color(0, 0, 0)
        self.set_y(15)

    def footer(self):
        self.set_y(-15)
        self.set_draw_color(*BRAND_ACCENT)
        self.line(20, self.get_y(), 190, self.get_y())
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*GRAY)
        self.cell(0, 8, f"Pagina {self.page_no()} | FOX NOC Dashboard | {self.generated_at}", align="C")

    # ── main ───────────────────────────────────────────────────────────────
    def build(self) -> bytes:
        self.cover_page()
        self.executive_summary()
        self.device_inventory()
        self.mikrotik_health()
        self.network_tests()
        self.topology_section()
        return self.output()


def generate_pdf(scan_data: dict) -> bytes:
    report = FoxNOCReport(scan_data)
    return report.build()
