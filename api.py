from __future__ import annotations
import os
import asyncio
import logging
import time
import subprocess
import psutil
from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import deque

from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.exceptions import RequestValidationError

# --- SEUS MÓDULOS (Certifique-se que os caminhos estão corretos) ---
from performance import ping_stats
import database
from services.diagnosis_service import DiagnosisService
from config import load_config
from scanner.arp_scanner import ARPScanner
from collectors.snmp_metrics import get_mikrotik_health as _snmp_mikrotik_health
from collectors.mikrotik_api import get_dhcp_details as _mtk_dhcp, get_wifi_clients as _mtk_wifi
from collectors.twibi_api import get_mesh_status as _twibi_mesh, NODES as _TWIBI_NODES, TWIBI_USER as _TWIBI_USER, TWIBI_PASS as _TWIBI_PASS
from collectors.wifi_quality import get_wifi_quality as _get_wifi_quality

# --- CONFIGURAÇÃO DE LOG ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("FoxAPI")

# --- INICIALIZAÇÃO ---
app = FastAPI(title="Fox Network NOC")
app_config = load_config() 
diagnosis_service = DiagnosisService(config=app_config)

# Histórico de tráfego (30 amostras para o Chart.js)
traffic_history = deque(maxlen=30)
for _ in range(30): traffic_history.append({"download": 0, "upload": 0})
last_snmp_data = {"rx": 0, "tx": 0, "ts": 0}

# Cache traceroute (TTL 5 min — traceroute é lento)
_tr_cache: Dict[str, Any] = {"data": None, "ts": 0.0}
_TR_TTL = 300

# Cache de qualidade WiFi (atualizado a cada 60s pelo background poller)
_wifi_quality_cache: Dict[str, Any] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS ---
class NetworkTarget(BaseModel):
    interface: str
    subnet: str

class ScanConfig(BaseModel):
    interface: str = "eth0"
    subnet: str = "192.168.100.0/24"
    expected_hosts: Optional[int] = 30
    modules: List[str] = Field(default_factory=list)
    # Suporte a múltiplas redes simultâneas
    networks: List[NetworkTarget] = Field(default_factory=list)

# --- 1. TELEMETRIA RÁPIDA (OVERWATCH) ---
# IMPORTANTE: Estas rotas devem vir ANTES de qualquer app.mount

@app.get("/system/metrics")
async def get_system_metrics():
    """Métricas do node fox-dev: CPU, temperatura e contagem de dispositivos do último scan."""
    cpu = psutil.cpu_percent(interval=None)

    # Lê temperatura diretamente do thermal zone (mais confiável que psutil neste hardware)
    temp = None
    try:
        raw = open("/sys/class/thermal/thermal_zone0/temp").read().strip()
        temp = int(raw) / 1000.0
    except Exception:
        pass
    if temp is None and hasattr(psutil, "sensors_temperatures"):
        temps = psutil.sensors_temperatures()
        if temps and 'coretemp' in temps:
            temp = temps['coretemp'][0].current

    mem = psutil.virtual_memory()
    mem_total_gb = mem.total / (1024 ** 3)
    mem_used_gb  = mem.used  / (1024 ** 3)
    mem_pct      = mem.percent

    device_count = 0
    try:
        row = database.get_last_scan()
        if row:
            device_count = row.get('device_count', 0) or 0
    except Exception:
        pass

    return {
        "cpu": cpu,
        "temp": temp,
        "temp_warn":     temp is not None and temp >= 70,
        "temp_critical": temp is not None and temp >= 75,
        "mem_total_gb":  round(mem_total_gb, 1),
        "mem_used_gb":   round(mem_used_gb,  1),
        "mem_pct":       mem_pct,
        "devices":       device_count
    }

@app.get("/performance/ping")
async def get_performance_ping():
    """Retorna campos exatos para o dashboard: latency, jitter, loss"""
    try:
        stats = await ping_stats()
        # Mapeia os nomes das chaves para o que o JS espera
        return {
            "latency": stats.get("latency", 0),
            "jitter": stats.get("jitter", 0),
            "loss": stats.get("loss", 0)
        }
    except Exception as e:
        logger.error(f"Erro no ping: {e}")
        return {"latency": 0, "jitter": 0, "loss": 100}

@app.get("/network/interfaces")
async def get_network_interfaces():
    """Lista interfaces de rede IPv4 disponíveis (exceto loopback e virtuais)"""
    try:
        interfaces = psutil.net_if_addrs()
        result = []
        for name, addrs in interfaces.items():
            if name == 'lo' or 'veth' in name or 'docker' in name:
                continue
            for addr in addrs:
                if addr.family == 2:  # IPv4
                    ip = addr.address
                    parts = ip.split('.')
                    subnet_val = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
                    result.append({
                        "id": name,
                        "display": f"{name} - {ip}",
                        "subnet": subnet_val
                    })
        return result
    except Exception as e:
        logger.error(f"Erro ao listar interfaces: {e}")
        return []

@app.get("/network/traffic")
async def get_network_traffic():
    """Cálculo de Throughput em Mbps via contadores da interface local"""
    global last_snmp_data
    now = time.time()

    try:
        counters = psutil.net_io_counters()
        current_rx = counters.bytes_recv
        current_tx = counters.bytes_sent

        dt = now - last_snmp_data["ts"]
        mbps_down = 0
        mbps_up = 0

        if last_snmp_data["ts"] > 0 and dt > 0:
            mbps_down = round(((current_rx - last_snmp_data["rx"]) * 8) / dt / 1_000_000, 2)
            mbps_up = round(((current_tx - last_snmp_data["tx"]) * 8) / dt / 1_000_000, 2)

        last_snmp_data = {"rx": current_rx, "tx": current_tx, "ts": now}
        traffic_history.append({"download": max(mbps_down, 0), "upload": max(mbps_up, 0)})
        return {"history": list(traffic_history)}

    except Exception as e:
        logger.error(f"Erro ao obter tráfego: {e}")
        return {"history": list(traffic_history)}

# --- 2. TRACEROUTE LIVE ---

@app.get("/network/traceroute")
async def get_traceroute():
    """Traceroute até 8.8.8.8 com latência por salto e detecção de gargalo. Cache 5 min."""
    global _tr_cache
    now = time.time()
    if _tr_cache["data"] and now - _tr_cache["ts"] < _TR_TTL:
        return _tr_cache["data"]
    try:
        from scanner.route_analyzer import RouteAnalyzer
        loop = asyncio.get_running_loop()
        analyzer = RouteAnalyzer(max_hops=20)
        result = await loop.run_in_executor(None, analyzer.analyze, "8.8.8.8")

        raw_hops = result.get("hops", [])
        # Filtra saltos sem resposta e numera sequencialmente
        valid: list[dict] = []
        for h in raw_hops:
            if h.get("ip") == "*" or h.get("latency") is None:
                continue
            valid.append({
                "hop_num": len(valid) + 1,
                "ip":       h["ip"],
                "latency":  round(h["latency"], 2),
                "is_private": h.get("is_private", False),
            })

        # Detecção de gargalo: salto cujo delta > 30ms E rtt > 15ms
        for i, hop in enumerate(valid):
            prev = valid[i - 1]["latency"] if i > 0 else 0.0
            delta = hop["latency"] - prev
            hop["delta_ms"]      = round(delta, 1)
            hop["is_bottleneck"] = i > 0 and delta > 30 and hop["latency"] > 15

        data = {
            "hops":         valid,
            "total_hops":   len(valid),
            "target":       result.get("target", "8.8.8.8"),
            "nat_suspected": result.get("nat_multiple_suspected", False),
            "has_bottleneck": any(h["is_bottleneck"] for h in valid),
        }
        _tr_cache = {"data": data, "ts": now}
        return data
    except Exception as e:
        logger.error(f"Traceroute error: {e}")
        return {"hops": [], "error": str(e)}

# --- 3. TOPOLOGIA (MAPA TÁTICO) ---

@app.get("/topology/map")
async def get_topology_map():
    """Retorna a estrutura hierárquica para o JS percorrer"""
    # Estrutura compatível com o loop do seu index.html
    return {
        "children": [
            {
                "name": "Huawei",
                "children": [
                    {
                        "name": "MikroTik",
                        "ports": [
                            {"devices": [{"name": "Twibi Principal"}]}, # ETH0
                            {"devices": []},                           # ETH1
                            {"devices": [{"name": "Twibi AX"}]},        # ETH2
                            {"devices": []},                           # ETH3
                            {"devices": [{"name": "Twibi AD"}]}         # ETH4
                        ]
                    }
                ]
            }
        ]
    }

# --- 4. SERVIÇOS DE DIAGNÓSTICO (INTELLIGENCE) ---

@app.get("/dashboard/stats")
async def get_dashboard_stats():
    try:
        row = database.get_last_scan()
        if not row: 
            return {"stats": {"ai_summary": {"summary": "Aguardando primeiro scan..."}}}
        
        # Desembrulha recursivamente todos os níveis de {"parsed": ...}
        ai_diag = row.get('ai_diagnosis', {})
        while isinstance(ai_diag, dict) and list(ai_diag.keys()) == ['parsed']:
            ai_diag = ai_diag['parsed']
        parsed = ai_diag if isinstance(ai_diag, dict) else {}
        
        raw_json = row.get('raw_json', {})
        # Unwrap nested {"generated_at":..., "report":{...}} structure
        raw_report = raw_json.get('report', raw_json) if isinstance(raw_json, dict) and 'report' in raw_json else raw_json

        return {
            "stats": {
                "timestamp": row.get('timestamp'),
                "ai_summary": parsed
            },
            "raw_report": raw_report
        }
    except Exception as e:
        return {"error": str(e)}

async def _run_and_save(interface: str, subnet: str, modules: list, extra_networks: list = None):
    """Executa o scan (uma ou múltiplas redes) e persiste no banco de dados."""
    import json
    from datetime import datetime
    try:
        payload = await diagnosis_service.run(interface=interface, subnet=subnet, modules=modules)
        if not payload:
            logger.error("Scan retornou payload vazio — não salvo.")
            return

        # Dual-network: roda scans adicionais e mescla devices
        if extra_networks:
            for net in extra_networks:
                logger.info(f"🔀 Scan adicional: {net['subnet']} via {net['interface']}")
                try:
                    extra = await diagnosis_service.run(
                        interface=net["interface"],
                        subnet=net["subnet"],
                        modules=modules,
                    )
                    if extra and extra.get("devices"):
                        existing_ips = {d["ip"] for d in payload.get("devices", [])}
                        new_devices = [d for d in extra["devices"] if d.get("ip") not in existing_ips]
                        payload["devices"].extend(new_devices)
                        logger.info(f"  ↳ +{len(new_devices)} dispositivos de {net['subnet']}")
                except Exception as e:
                    logger.warning(f"Scan adicional {net['subnet']} falhou: {e}")

        device_count  = len(payload.get("devices", []))
        temp_mikrotik = (payload.get("mikrotik_health") or {}).get("temperature")
        raw_json      = json.dumps({"generated_at": datetime.now().isoformat(), "report": payload},
                                   ensure_ascii=False, default=str)
        # ai_diagnosis já vem como {"parsed": {...}} do GeminiAnalyzer — guarda direto
        ai_diag     = payload.get("ai_diagnosis")
        ai_analysis = json.dumps(ai_diag, ensure_ascii=False, default=str) if ai_diag else ""

        database.insert_scan(device_count, temp_mikrotik, raw_json, ai_analysis)
        logger.info(f"✅ Scan salvo no banco: {device_count} dispositivos, temp={temp_mikrotik}")
    except Exception as e:
        logger.error(f"❌ Erro ao salvar scan: {e}", exc_info=True)

@app.post("/scan/start")
async def start_scan(config: ScanConfig, background_tasks: BackgroundTasks):
    networks_info = f" + {len(config.networks)} rede(s) extra" if config.networks else ""
    logger.info(f"🚀 MISSÃO INICIADA: {config.subnet}{networks_info}")
    extra = [{"interface": n.interface, "subnet": n.subnet} for n in config.networks]
    background_tasks.add_task(
        _run_and_save,
        interface=config.interface,
        subnet=config.subnet,
        modules=config.modules,
        extra_networks=extra or None,
    )
    return {"status": "success"}

# --- 4. MIKROTIK ---

@app.get("/mikrotik/health")
async def get_mikrotik_health_endpoint():
    """Saúde do MikroTik via SNMP: CPU, temperatura, uptime, voltagem, memória."""
    host = os.getenv("ND_MIKROTIK_HOST", "192.168.88.1")
    community = os.getenv("ND_SNMP_COMMUNITY", "public")
    try:
        data = await _snmp_mikrotik_health(host, community)
        return data
    except Exception as e:
        logger.error(f"Erro saúde MikroTik: {e}")
        return {"error": str(e)}

@app.get("/mikrotik/clients")
async def get_mikrotik_clients():
    """Dispositivos com lease DHCP no MikroTik."""
    try:
        loop = asyncio.get_event_loop()
        leases = await loop.run_in_executor(None, _mtk_dhcp)
        return leases if isinstance(leases, list) else []
    except Exception as e:
        logger.error(f"Erro clientes MikroTik: {e}")
        return []

@app.get("/mikrotik/wifi")
async def get_mikrotik_wifi():
    """Clientes WiFi conectados com sinal (RSSI) e qualidade (CCQ)."""
    try:
        loop = asyncio.get_event_loop()
        clients = await loop.run_in_executor(None, _mtk_wifi)
        return clients if isinstance(clients, list) else []
    except Exception as e:
        logger.error(f"Erro WiFi MikroTik: {e}")
        return []

# --- 5. TWIBI MESH ---

@app.get("/twibi/mesh")
async def get_twibi_mesh():
    """Status dos 3 nós do mesh Twibi Force AX."""
    try:
        nodes = await _twibi_mesh()
        return nodes
    except Exception as e:
        logger.error(f"Erro mesh Twibi: {e}")
        return []

# --- 6. QUALIDADE WiFi (background poller + endpoint) ---

async def _poll_wifi_quality():
    """Background task: mede qualidade da rede a cada 60s e salva no banco."""
    await asyncio.sleep(10)  # aguarda startup
    while True:
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, _get_wifi_quality)
            _wifi_quality_cache.update(data)
            s = data.get("summary", {})
            database.insert_wifi_metric(
                inet_loss_pct  = s.get("inet_loss_pct"),
                inet_jitter_ms = s.get("inet_jitter_ms"),
                inet_avg_ms    = s.get("inet_avg_ms"),
                gw_avg_ms      = data.get("gateway", {}).get("avg_ms"),
                dns_ms         = s.get("dns_ms"),
            )
        except Exception as e:
            logger.error(f"WiFi quality poller error: {e}")
        await asyncio.sleep(60)


@app.on_event("startup")
async def _startup():
    asyncio.create_task(_poll_wifi_quality())


@app.get("/wifi/quality")
async def wifi_quality():
    """Métricas de qualidade da rede: packet loss, jitter, DNS, APs Twibi. Histórico recente."""
    # Se o cache estiver vazio (primeira requisição antes do poller), executa agora
    if not _wifi_quality_cache:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, _get_wifi_quality)
        _wifi_quality_cache.update(data)
    history = database.get_wifi_metrics_recent(limit=60)
    return {**_wifi_quality_cache, "history": history}


# --- 6b. TOPOLOGIA LIVE ---

@app.get("/topology/live")
async def get_topology_live():
    """
    Monta topologia completa: Internet → ISP → MikroTik → Twibis → Clientes WiFi.
    Cruza dados do último scan (neighbors, devices, route, ssdp) com dados live.
    """
    try:
        row = database.get_last_scan()
        report = (row.get("raw_json", {}) if row else {})
        if isinstance(report, dict) and "report" in report:
            report = report["report"]

        devices    = report.get("devices", [])
        neighbors  = report.get("mikrotik_neighbors", [])
        route      = report.get("route", {})
        ssdp       = report.get("ssdp", [])
        mk_health  = report.get("mikrotik_health", {})
        mk_wan     = report.get("mikrotik_wan_status", [{}])
        wan_if     = mk_wan[0] if mk_wan else {}
        wifi_mesh  = report.get("wifi_mesh", [])
        wifi_quality = report.get("wifi_quality", {})

        # ── WAN status: qual link está ativo e se há failover ────────────────
        mk_ip = os.getenv("ND_MIKROTIK_HOST", "192.168.88.1")
        wan_interfaces = {w.get("name",""): w for w in mk_wan}
        def _wan_running(w): return w.get("running") in (True, "true")
        vivo_wan        = wan_interfaces.get("wan-vivo", {})
        nio_wan         = wan_interfaces.get("wan-nio",  {})
        vivo_up         = _wan_running(vivo_wan)
        nio_up          = _wan_running(nio_wan)
        failover_active = nio_up and not vivo_up
        # Detecta se Vivo saiu do modo bridge: IP privado na WAN = modem Vivo virou NAT
        vivo_bridge_ok  = vivo_wan.get("bridge_mode")   # True=bridge, False=NAT, None=desconhecido
        vivo_private_ip = vivo_wan.get("private_ip")
        active_wan_name = "wan-nio" if failover_active else ("wan-vivo" if vivo_up else (list(wan_interfaces.keys())[0] if wan_interfaces else "?"))

        # ── Detecta Double NAT ────────────────────────────────────────────
        # Traceroute detecta via hops privados; mas NIO em DMZ "esconde" o NAT duplo.
        # Se o link ativo for NIO → double NAT é sempre verdadeiro (o modem NIO faz NAT).
        hops = route.get("hops", [])
        private_hops = [h for h in hops if h.get("is_private") and h.get("ip") not in ("*", mk_ip)]
        # Double NAT: failover NIO ativo, OU Vivo saiu do bridge, OU traceroute detectou
        vivo_double_nat = vivo_up and vivo_private_ip is True
        double_nat = failover_active or vivo_double_nat or len(private_hops) >= 2
        isp_ip = next((h["ip"] for h in hops if not h.get("is_private") and h.get("ip") not in ("*", None)), "?")

        # ── Mapa MAC → device (normaliza: remove zeros, compara base-16) ─
        def mac_base(mac):
            return mac.upper().replace("-", ":") if mac else ""

        def mac_matches(mac_a, mac_b):
            """Twibi LAN MAC = device MAC ± 1 no último octeto."""
            try:
                a = mac_base(mac_a).split(":")
                b = mac_base(mac_b).split(":")
                if a[:5] != b[:5]: return False
                return abs(int(a[5], 16) - int(b[5], 16)) <= 1
            except Exception:
                return False

        def find_device(mac):
            for d in devices:
                if mac_matches(d.get("mac",""), mac):
                    return d
            return None

        # ── Portas WAN (não são APs) ──────────────────────────────────────
        wan_port_names = {w.get("name", "") for w in mk_wan}

        # ── Mapeia portas do MikroTik → Twibi (só LAN) ───────────────────
        port_map = {}  # porta → {device, mac}
        for nbr in neighbors:
            nbr_mac  = nbr.get("mac-address", "")
            iface    = nbr.get("interface", "")
            port     = iface.split(",")[0]  # "ether3,bridge" → "ether3"
            # Ignora vizinhos na porta WAN (modem ISP)
            if port in wan_port_names:
                continue
            device   = find_device(nbr_mac)
            port_map[port] = {
                "port":     port,
                "mac":      nbr_mac,
                "device":   device,
                "hostname": device.get("hostname", "-") if device else nbr_mac[-8:],
                "ip":       device.get("ip") if device else None,
            }

        # ── Twibi IPs conhecidos para marcar nos devices ──────────────────
        twibi_ips = {d["ip"] for d in devices if "Twibi" in d.get("hostname", "") or "twibi" in d.get("hostname","").lower()}

        # ── Cruza wifi_mesh com port_map para enriquecer cada AP ──────────
        # Monta índice: nome amigável → dados do mesh
        mesh_by_name = {n.get("name", ""): n for n in wifi_mesh}

        # ── Clientes WiFi = devices ativos que NÃO são infra ─────────────
        infra_ips = {
            "192.168.88.1", "192.168.88.250",
            "192.168.88.111", "192.168.88.112",
        } | twibi_ips

        wifi_clients = [
            d for d in devices
            if d.get("ip") not in infra_ips
            and d.get("status") in ("Ativo", "Invisível (DHCP Record)")
        ]

        # ── Enriquece port_map com dados de mesh WiFi ────────────────────
        for port, info in port_map.items():
            hostname = (info.get("hostname") or "")
            mesh_node = None
            # Tenta match por nome amigável (ex: "Twibi Quintal")
            for name, node in mesh_by_name.items():
                if name and name.lower() in hostname.lower():
                    mesh_node = node
                    break
            if mesh_node:
                info["wifi_mesh"] = {
                    "mode":             mesh_node.get("mode"),
                    "uptime":           mesh_node.get("uptime"),
                    "interference_max": mesh_node.get("interference_max", 0),
                    "radios":           mesh_node.get("radios", []),
                }

        # ── Monta resposta ────────────────────────────────────────────────
        return {
            "internet": {
                "label": "Internet",
                "type":  "internet",
            },
            "wan_links": {
                "vivo": {
                    "up":         vivo_up,
                    "ip":         vivo_wan.get("ip"),
                    "bridge_ok":  vivo_bridge_ok,
                    "double_nat": vivo_double_nat,
                    "label":      "Vivo (PPPoE)",
                    "type":       "isp",
                },
                "nio": {
                    "up":         nio_up,
                    "ip":         nio_wan.get("ip"),
                    "double_nat": True,
                    "label":      "NIO (DHCP)",
                    "type":       "isp",
                },
                "failover_active":   failover_active,
                "loadbalance_active": vivo_up and nio_up,
            },
            "isp": {
                "label":           "ISP / Modem",
                "type":            "router",
                "ip":              isp_ip,
                "double_nat":      double_nat,
                "vendor":          "NIO" if failover_active else "Vivo",
                "failover_active":  failover_active,
                "vivo_up":          vivo_up,
                "nio_up":           nio_up,
                "vivo_bridge_ok":   vivo_bridge_ok,
                "vivo_double_nat":  vivo_double_nat,
                "vivo_ip":          vivo_wan.get("ip"),
            },
            "mikrotik": {
                "label":       "MikroTik",
                "type":        "router",
                "ip":          os.getenv("ND_MIKROTIK_HOST", "192.168.88.1"),
                "wan_port":    active_wan_name,
                "wan_up":      vivo_up or nio_up,
                "cpu":         mk_health.get("cpu_usage"),
                "temp":        mk_health.get("temperature"),
                "uptime":      mk_health.get("uptime_str"),
                "mem_free":    mk_health.get("mem_free"),
            },
            "ports": port_map,
            "wifi_clients": wifi_clients,
            "wifi_quality": wifi_quality,
        }
    except Exception as e:
        logger.error(f"Erro topology/live: {e}")
        return {"error": str(e)}

# --- TOOLS: MÓDULOS DE TESTE DE REDE ---
from fastapi.responses import StreamingResponse
import json as _json

TOOLS_REGISTRY = [
    {
        "id": "arp",
        "name": "ARP Scanner",
        "description": "Descobre dispositivos ativos na rede via ARP",
        "icon": "radar",
        "params": [
            {"id": "subnet", "label": "Subnet", "type": "text", "default": "192.168.88.0/24"},
            {"id": "iface",  "label": "Interface", "type": "text", "default": "enp2s0"},
        ]
    },
    {
        "id": "port",
        "name": "Port Scanner",
        "description": "Verifica portas abertas em um host",
        "icon": "door-open",
        "params": [
            {"id": "target", "label": "Host / IP", "type": "text", "default": "192.168.88.1"},
            {"id": "ports",  "label": "Portas", "type": "text", "default": "22,53,80,443,8728"},
        ]
    },
    {
        "id": "dns",
        "name": "DNS Tester",
        "description": "Testa resolução DNS e mede latência",
        "icon": "globe",
        "params": [
            {"id": "domain", "label": "Domínio", "type": "text", "default": "google.com"},
        ]
    },
    {
        "id": "latency",
        "name": "Latency Tester",
        "description": "Mede latência e perda de pacotes via ping",
        "icon": "activity",
        "params": [
            {"id": "host", "label": "Host / IP", "type": "text", "default": "8.8.8.8"},
        ]
    },
    {
        "id": "route",
        "name": "Route Analyzer",
        "description": "Traceroute e análise de roteamento",
        "icon": "git-branch",
        "params": [
            {"id": "target", "label": "Destino", "type": "text", "default": "8.8.8.8"},
        ]
    },
    {
        "id": "snmp",
        "name": "SNMP Scanner",
        "description": "Consulta métricas SNMP de um dispositivo",
        "icon": "cpu",
        "params": [
            {"id": "host",      "label": "Host / IP",  "type": "text", "default": "192.168.88.1"},
            {"id": "community", "label": "Community",  "type": "text", "default": "public"},
        ]
    },
    {
        "id": "ssdp",
        "name": "SSDP Discovery",
        "description": "Descobre dispositivos UPnP/SSDP na rede",
        "icon": "wifi",
        "params": []
    },
    {
        "id": "mdns",
        "name": "mDNS Discovery",
        "description": "Descobre serviços mDNS/Bonjour na rede",
        "icon": "share-2",
        "params": []
    },
    {
        "id": "bufferbloat",
        "name": "Bufferbloat Test",
        "description": "Analisa distribuição de latência (indicador de bufferbloat)",
        "icon": "bar-chart-2",
        "params": [
            {"id": "host", "label": "Host / IP", "type": "text", "default": "8.8.8.8"},
        ]
    },
    {
        "id": "wifi-channels",
        "name": "Canais WiFi",
        "description": "Analisa interferência e recomenda melhores canais nos nós Twibi",
        "icon": "radio",
        "params": []
    },
    {
        "id": "set-channel",
        "name": "Trocar Canal WiFi",
        "description": "Aplica um canal específico em um nó Twibi (requer reboot para ativar)",
        "icon": "settings",
        "params": [
            {"id": "node",    "label": "Nó",         "type": "select",
             "options": ["Principal", "C44D", "108B"],
             "labels":  ["Twibi Principal", "Twibi Quintal", "Twibi Sala"],
             "default": "Principal"},
            {"id": "band",    "label": "Frequência",  "type": "select",
             "options": ["2.4GHz", "5GHz"],           "default": "2.4GHz"},
            {"id": "channel", "label": "Canal",       "type": "number", "default": "11"},
        ]
    },
]

@app.get("/tools/modules")
async def list_tools():
    return TOOLS_REGISTRY

class ToolRunRequest(BaseModel):
    params: Dict[str, str] = Field(default_factory=dict)

@app.post("/tools/run/{tool_id}")
async def run_tool(tool_id: str, req: ToolRunRequest):
    """Executa um módulo de teste e retorna resultado como SSE stream."""
    async def event_stream():
        def emit(type_: str, msg: str, data: Any = None):
            payload = {"type": type_, "message": msg}
            if data is not None:
                payload["data"] = data
            return f"data: {_json.dumps(payload, ensure_ascii=False, default=str)}\n\n"

        loop = asyncio.get_event_loop()
        p = req.params

        try:
            if tool_id == "arp":
                yield emit("info", f"Iniciando ARP scan em {p.get('subnet', '192.168.88.0/24')}...")
                from scanner.arp_scanner import ARPScanner, ARPScannerError
                def _run():
                    s = ARPScanner(subnet=p.get("subnet","192.168.88.0/24"), iface=p.get("iface","enp2s0"))
                    return [d.to_dict() for d in s.scan()]
                devices = await loop.run_in_executor(None, _run)
                yield emit("info", f"Encontrados {len(devices)} dispositivos:")
                for d in devices:
                    yield emit("result", f"  {d['ip']:<18} {d['mac']:<20} {d.get('vendor','-')}", d)
                yield emit("success", f"ARP scan concluído — {len(devices)} hosts ativos.")

            elif tool_id == "port":
                target = p.get("target", "192.168.88.1")
                ports  = p.get("ports", "22,53,80,443")
                yield emit("info", f"Escaneando portas {ports} em {target}...")
                from scanner.port_scanner import PortScanner
                def _run():
                    return PortScanner().scan(target, ports)
                result = await loop.run_in_executor(None, _run)
                open_ports = [pt for pt in result.get("ports", []) if pt.get("state") == "open"]
                yield emit("info", f"Portas abertas ({len(open_ports)}):")
                for pt in result.get("ports", []):
                    icon = "✓" if pt.get("state") == "open" else "✗"
                    yield emit("result", f"  {icon} {pt['port']:<6} {pt.get('name','-'):<15} {pt['state']}", pt)
                yield emit("success", f"Port scan concluído — {len(open_ports)} portas abertas.")

            elif tool_id == "dns":
                domain = p.get("domain", "google.com")
                yield emit("info", f"Testando resolução DNS para {domain}...")
                from scanner.dns_tester import DNSTester
                def _run():
                    return DNSTester().test(domain)
                result = await loop.run_in_executor(None, _run)
                if result.get("resolved"):
                    addrs = ", ".join(result.get("addresses", []))
                    yield emit("result", f"  Resolvido: {addrs}", result)
                    yield emit("result", f"  Latência: {result.get('elapsed_ms', '-')} ms")
                    yield emit("success", "DNS resolvido com sucesso.")
                else:
                    yield emit("error", f"Falha na resolução: {result.get('error', 'desconhecido')}")

            elif tool_id == "latency":
                host = p.get("host", "8.8.8.8")
                yield emit("info", f"Testando latência para {host}...")
                from scanner.latency_tester import LatencyTester
                def _run():
                    return LatencyTester().test(host)
                result = await loop.run_in_executor(None, _run)
                avg = result.get('avg_ms') or result.get('avg_latency_ms', '-')
                loss = result.get('packet_loss_percent', result.get('loss', '-'))
                yield emit("result", f"  Latência média: {avg} ms", result)
                yield emit("result", f"  Jitter: {result.get('jitter_ms', '-')} ms")
                yield emit("result", f"  Perda de pacotes: {loss}%")
                if result.get("reachable") or result.get("success"):
                    yield emit("success", "Teste de latência concluído.")
                else:
                    yield emit("error", f"Host inacessível: {result.get('error','')}")

            elif tool_id == "route":
                target = p.get("target", "8.8.8.8")
                yield emit("info", f"Executando traceroute para {target}...")
                from scanner.route_analyzer import RouteAnalyzer
                def _run():
                    return RouteAnalyzer(max_hops=20).analyze(target)
                result = await loop.run_in_executor(None, _run)
                hops = result.get("hops", [])
                for hop in hops:
                    ip  = hop.get("ip","*")
                    lat = f"{hop.get('latency',0):.1f} ms" if hop.get("latency") else "*"
                    flag = " ⚠ NAT" if hop.get("is_private") else ""
                    yield emit("result", f"  {hop.get('hop_num','?'):>2}  {ip:<18} {lat}{flag}", hop)
                nat = result.get("nat_multiple_suspected", False)
                yield emit("success", f"Traceroute concluído — {len(hops)} saltos. NAT duplo: {'sim' if nat else 'não'}.")

            elif tool_id == "snmp":
                host      = p.get("host", "192.168.88.1")
                community = p.get("community", "public")
                yield emit("info", f"Consultando SNMP em {host} (community={community})...")
                from collectors.snmp_metrics import get_mikrotik_health
                result = await get_mikrotik_health(host, community=community)
                if result.get("snmp_error"):
                    yield emit("error", f"SNMP indisponível: {result['snmp_error']}")
                else:
                    yield emit("result", f"  CPU:         {result.get('cpu_usage','?')}%", result)
                    yield emit("result", f"  Temperatura: {result.get('temperature','?')} °C")
                    yield emit("result", f"  Uptime:      {result.get('uptime_str','?')}")
                    yield emit("result", f"  Mem livre:   {result.get('mem_free','?')} KB")
                    yield emit("result", f"  Voltagem:    {result.get('voltage','?')} V")
                    yield emit("success", "Consulta SNMP concluída.")

            elif tool_id == "ssdp":
                yield emit("info", "Descobrindo dispositivos SSDP/UPnP na rede...")
                from scanner.ssdp_scanner import SSDPScanner
                def _run():
                    return SSDPScanner().discover()
                devices = await loop.run_in_executor(None, _run)
                yield emit("info", f"Encontrados {len(devices)} dispositivos:")
                for d in devices:
                    yield emit("result", f"  {d.get('ip','?'):<18} {d.get('server','-')}", d)
                yield emit("success", f"SSDP discovery concluída — {len(devices)} dispositivos.")

            elif tool_id == "mdns":
                yield emit("info", "Descobrindo serviços mDNS/Bonjour na rede...")
                from scanner.mdns_scanner import MDNSScanner
                def _run():
                    return MDNSScanner().discover()
                services = await loop.run_in_executor(None, _run)
                yield emit("info", f"Encontrados {len(services)} serviços:")
                for s in services:
                    yield emit("result", f"  {s.get('name','-'):<30} {s.get('type','-')}", s)
                yield emit("success", f"mDNS discovery concluída — {len(services)} serviços.")

            elif tool_id == "bufferbloat":
                host = p.get("host", "8.8.8.8")
                yield emit("info", f"Analisando distribuição de latência para {host}...")
                yield emit("info", "Executando 80 pings a 0.1s de intervalo (~8s)...")

                def _run_bb():
                    import re as _re
                    r = subprocess.run(
                        ["ping", "-c", "80", "-i", "0.1", "-W", "2", host],
                        capture_output=True, text=True, timeout=25,
                    )
                    rtts = [float(m) for m in _re.findall(r'time=([\d.]+)', r.stdout)]
                    m2 = _re.search(r'(\d+(?:\.\d+)?)% packet loss', r.stdout)
                    loss = float(m2.group(1)) if m2 else 0.0
                    return rtts, loss

                rtts, loss = await loop.run_in_executor(None, _run_bb)

                if not rtts:
                    yield emit("error", "Nenhuma resposta recebida. Host inacessível.")
                else:
                    rtts.sort()
                    n = len(rtts)
                    def pct(p): return rtts[min(int(p / 100 * n), n - 1)]
                    mn = rtts[0]; p50 = pct(50); p95 = pct(95); p99 = pct(99); mx = rtts[-1]
                    ratio = round(mx / mn, 1) if mn > 0 else 0

                    yield emit("result", f"  Min (base):  {mn:.1f} ms")
                    yield emit("result", f"  Mediana P50: {p50:.1f} ms")
                    yield emit("result", f"  Percentil P95: {p95:.1f} ms")
                    yield emit("result", f"  Percentil P99: {p99:.1f} ms")
                    yield emit("result", f"  Max (pico):  {mx:.1f} ms")
                    yield emit("result", f"  Perda:       {loss:.0f}%")
                    yield emit("result", f"  Pico/Base:   {ratio}x")

                    if ratio > 10:
                        grade, verdict = "F", "BUFFERBLOAT SEVERO"
                        tip = "Fila do roteador lotando. Configure QoS/filas no MikroTik (Simple Queues ou mangle+CAKE)."
                    elif ratio > 5:
                        grade, verdict = "D", "BUFFERBLOAT ALTO"
                        tip = "Jogo/ligacao ruim quando alguem baixa algo. Configure fila de prioridade no MikroTik."
                    elif ratio > 3:
                        grade, verdict = "C", "BUFFERBLOAT MODERADO"
                        tip = "Impacto perceptivel em picos. Considere habilitar filas no MikroTik."
                    elif ratio > 2:
                        grade, verdict = "B", "BUFFERBLOAT BAIXO"
                        tip = "Impacto pequeno. Razoavel para uso doméstico."
                    else:
                        grade, verdict = "A", "EXCELENTE"
                        tip = "Sem bufferbloat detectado. Fila do roteador saudável."

                    yield emit("result", f"\n  NOTA: {grade}  —  {verdict}")
                    lvl = "success" if grade in ("A", "B") else "error" if grade in ("F", "D") else "info"
                    yield emit(lvl, f"Bufferbloat: {grade} — {tip}")

            elif tool_id == "wifi-channels":
                yield emit("info", "Consultando canais e interferencia WiFi nos nos Twibi...")
                nodes = await _twibi_mesh()

                def _bar(score: int, width: int = 20) -> str:
                    filled = round(score / 100 * width)
                    return "[" + "#" * filled + "-" * (width - filled) + f"] {score}/100"

                def _recommend_24g(top_interferers: list) -> tuple[int, str]:
                    """Retorna (canal_recomendado, motivo) para 2.4GHz."""
                    occ: dict[int, int] = {}  # canal -> sinal mais forte
                    for ap in top_interferers:
                        ch  = ap.get("channel", 0)
                        sig = ap.get("signal", -100)
                        occ[ch] = max(occ.get(ch, -100), sig)
                    # Verifica canais nao-sobrepostos: 1, 6, 11
                    candidates = []
                    for c in [1, 6, 11]:
                        # sinal no canal e vizinhos ±3 (para BW 40MHz evita sobreposicao)
                        worst = max((occ.get(ch, -100) for ch in range(c - 3, c + 4)), default=-100)
                        candidates.append((c, worst))
                    # Escolhe o com menor sinal (mais limpo)
                    best_ch, best_sig = min(candidates, key=lambda x: x[1])
                    if best_sig < -80:
                        motivo = f"canal {best_ch} tem apenas vizinhos fracos ({best_sig} dBm)"
                    elif best_sig < -65:
                        motivo = f"canal {best_ch} menos congestionado ({best_sig} dBm)"
                    else:
                        motivo = f"canal {best_ch} é o menos pior (todos congestionados)"
                    return best_ch, motivo

                all_recommendations = []

                for node in nodes:
                    if node.get("error"):
                        yield emit("error", f"  {node.get('name','?')}: {node['error']}")
                        continue
                    name = node.get("alias") or node.get("name", "?")
                    raw_name = node.get("name", "?")
                    mode = node.get("mode", "?")
                    yield emit("info", f"\n┌─ {name}  ({mode})")
                    for radio in node.get("radios", []):
                        freq    = radio.get("freq", "?")
                        ch      = radio.get("channel")
                        bw      = radio.get("bandwidth", "?")
                        enabled = radio.get("enabled", True)
                        intf    = radio.get("interference", {})
                        score   = intf.get("score", 0)
                        level   = intf.get("level", "low")
                        top     = intf.get("top", [])
                        level_icon = {"low": "OK ", "warning": "AVS", "critical": "!!!"}
                        yield emit("result",
                            f"│  {freq:<8} ch {str(ch):<4} {bw:<6}  "
                            f"Interferencia [{level_icon.get(level,'?')}] {_bar(score)}")
                        if top:
                            for ap in top[:3]:
                                yield emit("info",
                                    f"│    - {ap['ssid']:<22} ch{ap['channel']:<4} "
                                    f"{ap['signal']} dBm  (contrib {ap['contrib']})")
                        if freq == "2.4GHz" and score >= 30:
                            best_ch, motivo = _recommend_24g(top)
                            if best_ch != ch:
                                yield emit("warning",
                                    f"│  Recomendacao: mudar para canal {best_ch}  ({motivo})")
                                all_recommendations.append({
                                    "node": raw_name, "band": "2.4GHz",
                                    "current": ch, "recommended": best_ch, "reason": motivo
                                })
                    yield emit("info", "└" + "─" * 60)

                yield emit("info", "")
                if all_recommendations:
                    yield emit("warning", "ACOES RECOMENDADAS:")
                    for r in all_recommendations:
                        yield emit("warning",
                            f"  [{r['node']}] {r['band']}: canal {r['current']} -> canal {r['recommended']}")
                    yield emit("info", "")
                    yield emit("info", "Para trocar o canal use a ferramenta 'Trocar Canal WiFi' abaixo.")
                    yield emit("info", "Apos configurar, reinicie o no pelo app Twibi para ativar a mudanca.")
                else:
                    yield emit("success", "Todos os canais com interferencia baixa — nenhuma acao necessaria.")
                yield emit("success", "Analise de canais concluida.")

            elif tool_id == "set-channel":
                node_name = p.get("node", "Principal")
                band      = p.get("band", "2.4GHz")
                try:
                    ch_new = int(p.get("channel", "11"))
                except ValueError:
                    yield emit("error", "Canal invalido — deve ser um numero inteiro.")
                    yield emit("done", "")
                    return

                # Validate channel range
                if band == "2.4GHz" and ch_new not in range(1, 15):
                    yield emit("error", "Canal 2.4GHz deve ser entre 1 e 14.")
                    yield emit("done", "")
                    return
                if band == "5GHz" and ch_new not in [36,40,44,48,52,56,60,64,100,104,108,112,116,120,124,128,132,136,140,144,149,153,157,161,165]:
                    yield emit("error", "Canal 5GHz invalido. Valores comuns: 36,40,44,48,149,153,157,161.")
                    yield emit("done", "")
                    return

                host = _TWIBI_NODES.get(node_name)
                if not host:
                    yield emit("error", f"No '{node_name}' nao encontrado. Use: {list(_TWIBI_NODES.keys())}")
                    yield emit("done", "")
                    return

                yield emit("info", f"Conectando a {node_name} ({host})...")
                import httpx as _httpx
                async with _httpx.AsyncClient(verify=False, follow_redirects=True) as hc:
                    # Auth
                    try:
                        r = await hc.post(f"http://{host}/api/v1/session",
                                          json={"username": _TWIBI_USER, "password": _TWIBI_PASS}, timeout=5)
                        token = r.json().get("token") if r.status_code == 200 else None
                    except Exception as e:
                        yield emit("error", f"Falha de autenticacao: {e}")
                        yield emit("done", "")
                        return
                    if not token:
                        yield emit("error", "Login falhou — verifique TWIBI_USER e TWIBI_PASS no .env")
                        yield emit("done", "")
                        return

                    # Get current radio config
                    r = await hc.get(f"http://{host}/api/v1/radio",
                                     headers={"Authorization": f"Bearer {token}"}, timeout=5)
                    radios = r.json() if r.status_code == 200 else []
                    radio_id = None
                    radio_obj = None
                    for rad in radios:
                        is_24 = rad.get("frequency") == 0
                        if (band == "2.4GHz" and is_24) or (band == "5GHz" and not is_24):
                            radio_id  = rad.get("id")
                            radio_obj = dict(rad)
                            break

                    if not radio_obj:
                        yield emit("error", f"Radio {band} nao encontrado em {node_name}.")
                        yield emit("done", "")
                        return

                    current_ch = radio_obj.get("channel", "?")
                    yield emit("info", f"  Radio atual: {radio_id}  canal {current_ch}  -> configurando canal {ch_new}...")

                    # Stage the change
                    radio_obj["configuredChannel"] = ch_new
                    radio_obj["channel"]           = ch_new
                    put_r = await hc.put(
                        f"http://{host}/api/v1/radio/{radio_id}",
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                        json=radio_obj, timeout=5)

                    if put_r.status_code == 200:
                        yield emit("success",
                            f"  Canal {ch_new} configurado em {node_name} {band} (anteriormente: {current_ch}).")
                        yield emit("warning", "")
                        yield emit("warning", "IMPORTANTE: A mudanca fica pendente ate o proximo reboot.")
                        yield emit("warning", f"Para ativar, reinicie o no '{node_name}' pelo app Twibi:")
                        yield emit("info",   "  1. Abra o app Twibi no celular")
                        yield emit("info",   f"  2. Selecione o no '{node_name}'")
                        yield emit("info",   "  3. Toque em Configuracoes > Reiniciar")
                        yield emit("info",   "  4. O no reiniciara e aplicara o novo canal automaticamente.")
                        yield emit("info",   "  (tambem funciona desligando e religando o no na tomada)")
                    else:
                        err_body = put_r.text[:200]
                        yield emit("error", f"  Falha ao configurar canal: HTTP {put_r.status_code}  {err_body}")

            else:
                yield emit("error", f"Módulo '{tool_id}' não encontrado.")

        except Exception as e:
            logger.error(f"Tool {tool_id} error: {e}")
            yield emit("error", f"Erro: {e}")

        yield emit("done", "")

    return StreamingResponse(event_stream(), media_type="text/event-stream")

# --- RELATÓRIO PDF ---
from fastapi.responses import Response as _Response

@app.get("/report/export")
async def export_pdf_report():
    """Gera e retorna o relatório PDF do último scan."""
    row = database.get_last_scan()
    if not row:
        raise HTTPException(status_code=404, detail="Nenhum scan disponível")

    raw = row.get("raw_json") or {}
    # raw_json é salvo como {"generated_at": ..., "report": payload}
    scan_data = raw.get("report", raw) if isinstance(raw, dict) else raw

    # Injeta ai_diagnosis da coluna separada se não estiver no payload
    if not scan_data.get("ai_diagnosis"):
        ai_raw = row.get("ai_diagnosis") or row.get("ai_analysis") or ""
        if ai_raw:
            try:
                ai_parsed = json.loads(ai_raw) if isinstance(ai_raw, str) else ai_raw
                # Desempacota nested parsed
                while isinstance(ai_parsed, dict) and list(ai_parsed.keys()) == ["parsed"]:
                    ai_parsed = ai_parsed["parsed"]
                scan_data["ai_diagnosis"] = ai_parsed
            except Exception:
                pass

    loop = asyncio.get_running_loop()
    from services.report_generator_pdf import generate_pdf
    pdf_bytes = await loop.run_in_executor(None, generate_pdf, scan_data)

    filename = f"fox-noc-report-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf"
    return _Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# --- 7. MONTAGEM DE ARQUIVOS ---

@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/noc")
# As rotas de API foram definidas acima. Agora montamos os estáticos por último.
# Assim, o FastAPI só tenta ler um arquivo se a rota não existir no código.

# Caminhos relativos ao arquivo — funciona local e em Docker
_BASE = os.path.dirname(os.path.abspath(__file__))
app.mount("/noc", StaticFiles(directory=os.path.join(_BASE, "app", "noc"), html=True), name="noc")

if __name__ == "__main__":
    import uvicorn
    # Importante: O nome aqui deve ser o nome do arquivo (api.py -> api:app)
    uvicorn.run("api:app", host="0.0.0.0", port=80, reload=True)