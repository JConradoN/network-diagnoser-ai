import os
import asyncio
import httpx

NODES = {
    "Principal": os.getenv("TWIBI_HOST_PRINCIPAL", "192.168.88.250"),
    "C44D":      os.getenv("TWIBI_HOST_C44D",      "192.168.88.111"),
    "108B":      os.getenv("TWIBI_HOST_108B",       "192.168.88.112"),
}
TWIBI_USER = os.getenv("TWIBI_USER", "admin")
TWIBI_PASS = os.getenv("TWIBI_PASS", "")

FREQ_LABEL = {0: "2.4GHz", 1: "5GHz"}
BW_LABEL   = {0: "20MHz", 1: "40MHz", 2: "80MHz", 3: "160MHz"}


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


async def _get(client: httpx.AsyncClient, host: str, path: str, token: str):
    try:
        r = await client.get(
            f"http://{host}{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=4,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


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

        # Device
        device = device_raw or {}
        uptime_sec = device.get("uptime", 0)

        # Status
        status = (status_raw[0] if isinstance(status_raw, list) else status_raw) or {}

        # Radios
        radios = []
        if isinstance(radio_raw, list):
            for r in radio_raw:
                radios.append({
                    "id":        r.get("id"),
                    "freq":      FREQ_LABEL.get(r.get("frequency"), "?"),
                    "channel":   r.get("channel"),
                    "bandwidth": BW_LABEL.get(r.get("bandwidth"), "?"),
                    "mu_mimo":   r.get("mu_mimo", False),
                    "ofdma":     r.get("ofdma", False),
                    "wifi6":     r.get("ofdma", False) or r.get("twt", False),
                    "enabled":   r.get("enabled", True),
                })

        # Mode
        sys_info = (system_raw[0] if isinstance(system_raw, list) else system_raw) or {}
        op_mode = sys_info.get("operationMode", 0)
        mode_label = {1: "Router", 3: "AP Satélite"}.get(op_mode, f"mode {op_mode}")

        return {
            "name":            name,
            "host":            host,
            "alias":           device.get("alias", name),
            "model":           device.get("model", "Twibi Force AX"),
            "fw_version":      device.get("fw_version", "--"),
            "uptime_sec":      uptime_sec,
            "uptime_str":      format_uptime(uptime_sec),
            "has_internet":    status.get("has_internet", False),
            "firmware_update": status.get("firmware_update", False),
            "mode":            mode_label,
            "radios":          radios,
        }


async def get_mesh_status() -> list[dict]:
    """Retorna lista com info de todos os nós do mesh Twibi."""
    tasks = [get_node_info(name, host) for name, host in NODES.items()]
    return await asyncio.gather(*tasks)
