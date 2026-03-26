"""
wifi_quality.py — Monitor de qualidade de rede em tempo real.

Mede packet loss, jitter, latência DNS e alcance dos APs Twibi.
Roda em background (polling a cada 60s) via api.py.
"""
import subprocess
import time
import re
import os
import socket
from typing import Optional

GATEWAY     = os.getenv("ND_MIKROTIK_HOST",       "192.168.88.1")
INET_TARGET = "8.8.8.8"

TWIBI_HOSTS = {
    "Principal": os.getenv("TWIBI_HOST_PRINCIPAL", "192.168.88.210"),
    "Quintal":   os.getenv("TWIBI_HOST_C44D",      "192.168.88.211"),
    "Sala":      os.getenv("TWIBI_HOST_108B",       "192.168.88.212"),
}


# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_ping(output: str) -> dict:
    """Extrai avg/jitter/loss da saída do ping Linux."""
    result = {
        "avg_ms": None, "jitter_ms": None,
        "loss_pct": 100.0, "min_ms": None, "max_ms": None,
    }
    m = re.search(r'(\d+) packets transmitted, (\d+) received.*?(\d+(?:\.\d+)?)% packet loss', output)
    if m:
        result["loss_pct"] = float(m.group(3))
    m = re.search(r'rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms', output)
    if m:
        result["min_ms"]    = float(m.group(1))
        result["avg_ms"]    = float(m.group(2))
        result["max_ms"]    = float(m.group(3))
        result["jitter_ms"] = float(m.group(4))
    return result


def ping_stats(host: str, count: int = 20, interval: float = 0.2) -> dict:
    """Ping host N vezes e retorna estatísticas (avg, jitter, loss)."""
    try:
        r = subprocess.run(
            ["ping", "-c", str(count), "-i", str(interval), "-W", "2", host],
            capture_output=True, text=True,
            timeout=count * interval + 8,
        )
        return {**_parse_ping(r.stdout), "host": host}
    except Exception as e:
        return {
            "avg_ms": None, "jitter_ms": None, "loss_pct": 100.0,
            "min_ms": None, "max_ms": None, "host": host, "error": str(e),
        }


def dns_latency_ms(domain: str = "google.com", server: str = "8.8.8.8") -> Optional[float]:
    """Mede tempo de resolução DNS em ms."""
    try:
        start = time.monotonic()
        r = subprocess.run(
            ["dig", "+short", "+time=3", f"@{server}", domain],
            capture_output=True, text=True, timeout=5,
        )
        elapsed = (time.monotonic() - start) * 1000
        if r.returncode == 0 and r.stdout.strip():
            return round(elapsed, 1)
    except Exception:
        pass
    # Fallback via socket
    try:
        start = time.monotonic()
        socket.getaddrinfo(domain, None)
        return round((time.monotonic() - start) * 1000, 1)
    except Exception:
        return None


def _grade_jitter(ms: Optional[float]) -> str:
    if ms is None:  return "unknown"
    if ms < 15:     return "good"
    if ms < 40:     return "warning"
    return "critical"


def _grade_loss(pct: float) -> str:
    if pct == 0:    return "good"
    if pct < 2:     return "warning"
    return "critical"


# ── API pública ────────────────────────────────────────────────────────────

def get_wifi_quality() -> dict:
    """
    Avaliação completa de qualidade de rede:
      - gateway: latência/jitter à 192.168.88.1 (baseline cabeado)
      - internet: latência/jitter/perda a 8.8.8.8 (qualidade WAN)
      - dns_ms: tempo de resolução DNS
      - twibi_nodes: ping para cada AP do mesh
      - alerts: lista de alertas com id/level/title/message
    """
    gw_stats   = ping_stats(GATEWAY,      count=10, interval=0.2)
    inet_stats = ping_stats(INET_TARGET,  count=20, interval=0.2)
    dns_ms     = dns_latency_ms("google.com", "8.8.8.8")

    twibi_nodes = []
    for name, host in TWIBI_HOSTS.items():
        s = ping_stats(host, count=5, interval=0.3)
        twibi_nodes.append({
            "name":      name,
            "host":      host,
            **s,
            "reachable": s.get("loss_pct", 100) < 100,
        })

    inet_loss   = inet_stats.get("loss_pct") or 0.0
    inet_jitter = inet_stats.get("jitter_ms") or 0.0
    inet_avg    = inet_stats.get("avg_ms") or 0.0

    alerts = []

    # Packet loss
    if inet_loss >= 5:
        alerts.append({
            "id": "inet-loss", "level": "critical",
            "title":   f"Perda de Pacotes Crítica: {inet_loss:.0f}%",
            "message": "WhatsApp, ligações VoIP e jogos muito afetados. Verifique o link WAN.",
        })
    elif inet_loss >= 1:
        alerts.append({
            "id": "inet-loss", "level": "warning",
            "title":   f"Perda de Pacotes: {inet_loss:.0f}%",
            "message": "Instabilidade em apps em tempo real (WhatsApp, jogos).",
        })

    # Jitter / bufferbloat
    if inet_jitter >= 50:
        alerts.append({
            "id": "inet-jitter", "level": "critical",
            "title":   f"Jitter Crítico: {inet_jitter:.0f}ms",
            "message": "Ligações VoIP caem, jogos com spike. Possível bufferbloat — execute o teste de Bufferbloat nas Ferramentas.",
        })
    elif inet_jitter >= 25:
        alerts.append({
            "id": "inet-jitter", "level": "warning",
            "title":   f"Jitter Elevado: {inet_jitter:.0f}ms",
            "message": "Cortes em ligações de WhatsApp. Execute o Bufferbloat Test nas Ferramentas.",
        })

    # DNS
    if dns_ms and dns_ms >= 300:
        alerts.append({
            "id": "dns-slow", "level": "critical",
            "title":   f"DNS Muito Lento: {dns_ms:.0f}ms",
            "message": "Abertura de apps e páginas muito afetada. Verifique o servidor DNS do MikroTik.",
        })
    elif dns_ms and dns_ms >= 150:
        alerts.append({
            "id": "dns-slow", "level": "warning",
            "title":   f"DNS Lento: {dns_ms:.0f}ms",
            "message": "Apps demoram para abrir. DNS saudável responde em < 50ms.",
        })

    # AP reachability
    for node in twibi_nodes:
        if not node.get("reachable"):
            alerts.append({
                "id":      f"ap-down-{node['name']}",
                "level":   "critical",
                "title":   f"AP Twibi Offline: {node['name']}",
                "message": f"No {node['host']} nao responde. Clientes nessa area sem WiFi.",
            })

    return {
        "timestamp":    time.time(),
        "gateway":      gw_stats,
        "internet":     inet_stats,
        "dns_ms":       dns_ms,
        "twibi_nodes":  twibi_nodes,
        "alerts":       alerts,
        "summary": {
            "inet_loss_pct":  round(inet_loss, 2),
            "inet_jitter_ms": round(inet_jitter, 2),
            "inet_avg_ms":    round(inet_avg, 2),
            "dns_ms":         dns_ms,
            "jitter_grade":   _grade_jitter(inet_jitter or None),
            "loss_grade":     _grade_loss(inet_loss),
        },
    }
