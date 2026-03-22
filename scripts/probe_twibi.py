#!/usr/bin/env python3
"""
Probe de descoberta da API HTTP dos Twibi Force AX (Intelbras).
Testa portas, endpoints comuns e tenta autenticação.
"""

import asyncio
import json
import sys
import os

# Credenciais padrão do Twibi (ajustar se necessário)
TWIBI_HOST = os.getenv("TWIBI_HOST", "192.168.88.250")
TWIBI_USER = os.getenv("TWIBI_USER", "admin")
TWIBI_PASS = os.getenv("TWIBI_PASS", "admin")

SATELLITES = [
    "192.168.88.111",  # Twibi_Force_AX_C44D
    "192.168.88.112",  # Twibi_Force_AX_108B
]

PORTS_TO_PROBE = [80, 443, 8080, 8443, 8888]

# Endpoints comuns em roteadores/APs Intelbras / OpenWrt / custom firmware
ENDPOINTS_GET = [
    "/",
    "/index.html",
    "/login",
    "/login.html",
    "/api",
    "/api/v1",
    "/api/system",
    "/api/system/info",
    "/api/system/status",
    "/api/device/info",
    "/api/device/status",
    "/api/wireless",
    "/api/wireless/info",
    "/api/wireless/clients",
    "/api/wireless/stations",
    "/api/clients",
    "/api/hosts",
    "/api/mesh",
    "/api/mesh/topology",
    "/api/mesh/nodes",
    "/api/network",
    "/api/network/info",
    "/api/network/status",
    "/api/status",
    "/api/info",
    "/cgi-bin/luci",
    "/cgi-bin/luci/admin/status",
    "/cgi-bin/luci/rpc/sys",
    "/cgi-bin/luci/;stok=/rpc",
    "/cgi-bin/login",
    "/userRpm/StatusRpm.htm",
    "/goform/getRouterInfo",
    "/stok/",
    "/web/",
    "/v1/api",
    "/v2/api",
    "/api/v1/network",
    "/api/v1/wireless",
    "/api/v1/clients",
    "/api/v1/system",
    "/api/v2/system",
    "/api/v2/clients",
    "/api/login",
    "/api/auth",
    "/api/token",
]

LOGIN_ATTEMPTS = [
    # path, payload, content-type
    ("/api/login",   {"username": TWIBI_USER, "password": TWIBI_PASS}, "json"),
    ("/api/login",   {"user": TWIBI_USER, "pass": TWIBI_PASS}, "json"),
    ("/api/auth",    {"username": TWIBI_USER, "password": TWIBI_PASS}, "json"),
    ("/api/token",   {"username": TWIBI_USER, "password": TWIBI_PASS}, "json"),
    ("/login",       {"username": TWIBI_USER, "password": TWIBI_PASS}, "json"),
    ("/login",       f"username={TWIBI_USER}&password={TWIBI_PASS}", "form"),
    ("/cgi-bin/luci","username={}&password={}".format(TWIBI_USER, TWIBI_PASS), "form"),
]


def sep(title=""):
    line = "─" * 60
    if title:
        print(f"\n┌{line}┐")
        print(f"│  {title:<58}│")
        print(f"└{line}┘")
    else:
        print(f"{'─'*62}")


async def check_port(host, port, timeout=2):
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def http_get(session_or_none, url, timeout=5):
    """Faz GET simples via httpx ou urllib."""
    try:
        import httpx
        async with httpx.AsyncClient(verify=False, timeout=timeout,
                                     follow_redirects=True) as client:
            r = await client.get(url)
            return r.status_code, dict(r.headers), r.text[:2000]
    except ImportError:
        import urllib.request
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FOX-NOC/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, dict(resp.headers), resp.read(2000).decode(errors="replace")
        except Exception as e:
            return None, {}, str(e)
    except Exception as e:
        return None, {}, str(e)


async def http_post(url, payload, content_type="json", timeout=5):
    try:
        import httpx
        async with httpx.AsyncClient(verify=False, timeout=timeout,
                                     follow_redirects=True) as client:
            if content_type == "json":
                r = await client.post(url, json=payload)
            else:
                r = await client.post(url, data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"})
            return r.status_code, dict(r.headers), r.text[:3000]
    except Exception as e:
        return None, {}, str(e)


def try_parse_json(text):
    try:
        return json.loads(text)
    except Exception:
        return None


async def probe_host(host):
    sep(f"Probing {host}")

    # 1. Ping
    print(f"\n[PING] {host}")
    ok = await check_port(host, 80, timeout=1)
    print(f"  TCP:80  → {'OPEN ✓' if ok else 'CLOSED ✗'}")

    # 2. Port scan
    print(f"\n[PORTS] {host}")
    open_ports = []
    tasks = {port: check_port(host, port) for port in PORTS_TO_PROBE}
    results = await asyncio.gather(*tasks.values())
    for port, is_open in zip(tasks.keys(), results):
        status = "OPEN  ✓" if is_open else "closed ✗"
        print(f"  :{port:<5} → {status}")
        if is_open:
            open_ports.append(port)

    if not open_ports:
        print(f"  ⚠ Nenhuma porta aberta — host pode estar inacessível")
        return

    base_port = open_ports[0]
    scheme = "https" if base_port in (443, 8443) else "http"
    base_url = f"{scheme}://{host}:{base_port}"
    print(f"\n  → Usando base: {base_url}")

    # 3. Endpoint discovery
    print(f"\n[GET ENDPOINTS] {base_url}")
    interesting = []
    for path in ENDPOINTS_GET:
        url = base_url + path
        status, headers, body = await http_get(None, url)
        if status and status not in (404, 405, 500, 502, 503):
            ct = headers.get("content-type", headers.get("Content-Type", ""))
            parsed = try_parse_json(body)
            marker = "★ JSON" if parsed else ""
            print(f"  {status}  {path:<45} {ct[:30]} {marker}")
            if status in (200, 201, 302, 401, 403):
                interesting.append((path, status, body, parsed))

    # 4. Login attempts
    print(f"\n[LOGIN ATTEMPTS] {base_url}")
    for path, payload, ct in LOGIN_ATTEMPTS:
        url = base_url + path
        status, headers, body = await http_post(url, payload, ct)
        if status and status != 404:
            parsed = try_parse_json(body)
            token = None
            if parsed and isinstance(parsed, dict):
                token = (parsed.get("token") or parsed.get("access_token")
                         or parsed.get("stok") or parsed.get("data", {}).get("token")
                         if isinstance(parsed.get("data"), dict) else None)
            print(f"  {status}  {path:<45} {'TOKEN: ' + token[:20] if token else body[:80]!r}")

    # 5. Mostrar corpos interessantes
    if interesting:
        print(f"\n[INTERESTING RESPONSES]")
        for path, status, body, parsed in interesting:
            if parsed:
                print(f"\n  → {path} [{status}]")
                print(f"  {json.dumps(parsed, indent=2, ensure_ascii=False)[:500]}")
            elif len(body) > 20 and status == 200:
                print(f"\n  → {path} [{status}] (HTML/texto)")
                print(f"  {body[:200]!r}")


async def main():
    hosts = [TWIBI_HOST] + SATELLITES
    for host in hosts:
        await probe_host(host)

    sep("FIM DO PROBE")
    print("\nPróximos passos:")
    print("  1. Identifique os endpoints com JSON (★ JSON)")
    print("  2. Veja qual login retornou token")
    print("  3. Ajuste TWIBI_PASS se necessário:")
    print(f"     TWIBI_PASS=suasenha python3 scripts/probe_twibi.py")


if __name__ == "__main__":
    asyncio.run(main())
