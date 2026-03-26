import os
import asyncio
import httpx

NODES = {
    "Principal": os.getenv("TWIBI_HOST_PRINCIPAL", "192.168.88.210"),
    "C44D":      os.getenv("TWIBI_HOST_C44D",      "192.168.88.211"),
    "108B":      os.getenv("TWIBI_HOST_108B",       "192.168.88.212"),
}
TWIBI_USER = os.getenv("TWIBI_USER", "admin")
TWIBI_PASS = os.getenv("TWIBI_PASS", "")

FREQ_LABEL = {0: "2.4GHz", 1: "5GHz"}
BW_LABEL   = {0: "20MHz", 1: "40MHz", 2: "80MHz", 3: "160MHz"}

FRIENDLY_NAMES = {
    "Principal": "Twibi Principal",
    "C44D":      "Twibi Quintal",
    "108B":      "Twibi Sala",
}

# MACs LAN dos nós (para identificar backhaul no site_survey)
NODE_MACS = {
    "Principal": os.getenv("TWIBI_MAC_PRINCIPAL", "98:2a:0a:cb:c4:9d").lower(),
    "C44D":      os.getenv("TWIBI_MAC_C44D",      "98:2a:0a:cb:c4:4d").lower(),
    "108B":      os.getenv("TWIBI_MAC_108B",       "30:e1:f1:8d:10:8b").lower(),
}


def format_uptime(seconds: int) -> str:
    d = seconds // 86400
    h = (seconds % 86400) // 3600
    m = (seconds % 3600) // 60
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if not parts: parts.append(f"{seconds}s")
    return " ".join(parts)


async def _get_token(client: httpx.AsyncClient, host: str) -> str | None:
    try:
        r = await client.post(
            f"http://{host}/api/v1/session",
            json={"username": TWIBI_USER, "password": TWIBI_PASS},
            timeout=5,
        )
        if r.status_code == 200:
            return r.json().get("token")
    except Exception:
        pass
    return None


async def _get(client: httpx.AsyncClient, host: str, path: str, token: str, timeout: float = 5):
    try:
        r = await client.get(
            f"http://{host}{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _interference_score(my_channel: int, bw_label: str, neighbors: list[dict]) -> dict:
    """
    Calcula score de interferência para um rádio com base nos vizinhos visíveis.
    Retorna: score (0-100), level, count, top_interferers
    """
    if not my_channel or not neighbors:
        return {"score": 0, "level": "low", "count": 0, "top": []}

    is_5g = my_channel >= 36
    bw_overlap = 8 if "80" in bw_label else 4 if "40" in bw_label else 2

    total_score = 0
    interferers = []
    seen = set()

    for ap in neighbors:
        ch   = ap.get("channel", 0)
        sig  = ap.get("signal_level", -100)
        ssid = ap.get("ssid", "?")
        mac  = ap.get("mac", "")

        # Filtra por banda (2.4GHz: ch 1-14, 5GHz: ch 36+)
        ap_5g = ch >= 36
        if ap_5g != is_5g:
            continue

        # Sobreposição de canal
        ch_diff = abs(ch - my_channel)
        if is_5g:
            # No 5GHz canais são espaçados de 4 em 4, sobreposição de 80MHz = ±4 slots
            overlap = max(0, bw_overlap - ch_diff)
        else:
            overlap = max(0, bw_overlap - ch_diff)

        if overlap <= 0:
            continue

        # Peso do sinal: -40 dBm = máximo, -95 = mínimo
        sig_norm = max(0, (sig + 95) / 55)  # 0..1
        contrib  = round(overlap * sig_norm * 20)

        key = mac or ssid
        if key not in seen:
            seen.add(key)
            interferers.append({
                "ssid":    ssid,
                "channel": ch,
                "signal":  sig,
                "contrib": contrib,
            })
            total_score += contrib

    total_score = min(total_score, 100)
    level = "critical" if total_score >= 60 else "warning" if total_score >= 30 else "low"

    top = sorted(interferers, key=lambda x: x["contrib"], reverse=True)[:4]
    return {"score": total_score, "level": level, "count": len(interferers), "top": top}


async def get_node_info(name: str, host: str) -> dict:
    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        token = await _get_token(client, host)
        if not token:
            return {"name": name, "host": host, "error": "login failed"}

        device_raw, status_raw, radio_raw, system_raw = await asyncio.gather(
            _get(client, host, "/api/v1/device/0", token),
            _get(client, host, "/api/v1/status",   token),
            _get(client, host, "/api/v1/radio",    token),
            _get(client, host, "/api/v1/system",   token),
        )
        # site_survey é mais lento — chama separado com timeout maior
        survey_raw = await _get(client, host, "/api/v1/site_survey", token, timeout=10)

        # Device
        device    = device_raw or {}
        uptime_sec = device.get("uptime", 0)

        # Status
        status = (status_raw[0] if isinstance(status_raw, list) else status_raw) or {}

        # Site survey — APs vizinhos
        survey = survey_raw if isinstance(survey_raw, list) else []
        # Filtra nossos próprios APs pelo SSID "Vilachaves" para usar como backhaul info
        our_macs   = set(NODE_MACS.values())
        # Aprox: MAC LAN vs WLAN pode diferir em 1 no último octeto
        other_aps  = [ap for ap in survey if ap.get("ssid") != "Vilachaves"]
        own_nodes  = [ap for ap in survey if ap.get("ssid") == "Vilachaves"]

        # Radios + interferência
        radios = []
        if isinstance(radio_raw, list):
            for r in radio_raw:
                bw_label = BW_LABEL.get(r.get("bandwidth"), "?")
                ch       = r.get("channel")
                freq     = FREQ_LABEL.get(r.get("frequency"), "?")
                wifi6    = r.get("ofdma", False) or r.get("twt", False)

                # Interferência: apenas de APs externos
                intf = _interference_score(ch, bw_label, other_aps)

                # Backhaul: APs "Vilachaves" visíveis nesta frequência
                bh_ch_min = 36 if freq == "5GHz" else 1
                bh_ch_max = 200 if freq == "5GHz" else 35
                backhaul_nodes = [
                    {"mac": ap.get("mac"), "signal": ap.get("signal_level"), "channel": ap.get("channel")}
                    for ap in own_nodes
                    if bh_ch_min <= (ap.get("channel") or 0) <= bh_ch_max
                ]

                radios.append({
                    "id":           r.get("id"),
                    "freq":         freq,
                    "channel":      ch,
                    "bandwidth":    bw_label,
                    "mu_mimo":      r.get("mu_mimo", False),
                    "ofdma":        r.get("ofdma", False),
                    "wifi6":        wifi6,
                    "enabled":      r.get("enabled", True),
                    "interference": intf,
                    "backhaul":     backhaul_nodes,
                })

        # Mode
        sys_info  = (system_raw[0] if isinstance(system_raw, list) else system_raw) or {}
        op_mode   = sys_info.get("operationMode", 0)
        mode_label = {1: "Router", 3: "AP Satelite"}.get(op_mode, f"mode {op_mode}")

        # Resumo de interferência geral (pior rádio)
        max_score = max((r["interference"]["score"] for r in radios), default=0)

        return {
            "name":             name,
            "host":             host,
            "alias":            FRIENDLY_NAMES.get(name, device.get("alias", name)),
            "model":            device.get("model", "Twibi Force AX"),
            "fw_version":       device.get("fw_version", "--"),
            "uptime_sec":       uptime_sec,
            "uptime_str":       format_uptime(uptime_sec),
            "has_internet":     status.get("has_internet", False),
            "firmware_update":  status.get("firmware_update", False),
            "mode":             mode_label,
            "radios":           radios,
            "survey_count":     len(survey),
            "neighbor_count":   len(other_aps),
            "interference_max": max_score,
        }


async def get_mesh_status() -> list[dict]:
    """Retorna lista com info de todos os nós do mesh Twibi."""
    tasks = [get_node_info(name, host) for name, host in NODES.items()]
    return await asyncio.gather(*tasks)
