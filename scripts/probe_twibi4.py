#!/usr/bin/env python3
"""
Fase 4: Exploração completa com auth — clientes, mesh, rede, satélites.
"""
import asyncio, json, os
import httpx

USER = os.getenv("TWIBI_USER", "admin")
PASS = os.getenv("TWIBI_PASS", "admin")

NODES = {
    "Principal":  "192.168.88.250",
    "C44D":       "192.168.88.111",
    "108B":       "192.168.88.112",
}

# Todos os endpoints a explorar
ENDPOINTS = [
    "/api/v1/device",
    "/api/v1/device/0",
    "/api/v1/device/1",
    "/api/v1/status",
    "/api/v1/wireless",
    "/api/v1/wireless/0",
    "/api/v1/wireless/1",
    "/api/v1/wireless/clients",
    "/api/v1/wireless/clients/0",
    "/api/v1/clients",
    "/api/v1/mesh",
    "/api/v1/mesh/0",
    "/api/v1/mesh/1",
    "/api/v1/mesh/topology",
    "/api/v1/network",
    "/api/v1/network/lan",
    "/api/v1/network/wan",
    "/api/v1/network/lan/dhcp-lease",
    "/api/v1/system",
    "/api/v1/system/info",
    "/api/v1/dhcp",
    "/api/v1/dhcp/lease",
    "/api/v1/stats",
    "/api/v1/radio",
    "/api/v1/radio/0",
    "/api/v1/radio/1",
    "/api/v1/ap",
    "/api/v1/ap/clients",
    "/api/v1/station",
    "/api/v1/stations",
    "/api/v1/assoclist",
    "/api/v1/wlan/clients",
    "/api/v1/hostapd/clients",
]


async def get_token(client, host):
    try:
        r = await client.post(
            f"http://{host}/api/v1/session",
            json={"username": USER, "password": PASS},
            timeout=5
        )
        if r.status_code == 200:
            return r.json().get("token")
    except Exception as e:
        print(f"  Login error {host}: {e}")
    return None


async def probe_node(name, host):
    print(f"\n{'='*60}")
    print(f"  NODE: {name} ({host})")
    print(f"{'='*60}")

    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        token = await get_token(client, host)
        if not token:
            print("  ✗ Login falhou")
            return {}

        print(f"  ✓ Token: {token[:30]}...")
        headers = {"Authorization": f"Bearer {token}"}

        results = {}
        for path in ENDPOINTS:
            try:
                r = await client.get(
                    f"http://{host}{path}",
                    headers=headers,
                    timeout=4
                )
                if r.status_code == 200:
                    try:
                        j = r.json()
                        # Só mostra se tiver dados úteis (não vazio)
                        if j and j != [] and j != {}:
                            print(f"\n  ★ {path}")
                            print(f"  {json.dumps(j, indent=2, ensure_ascii=False)[:800]}")
                            results[path] = j
                    except Exception:
                        if r.text.strip():
                            print(f"\n  ★ {path} (texto)")
                            print(f"  {r.text[:200]!r}")
                elif r.status_code not in (401, 404, 405, 500):
                    print(f"  {r.status_code}  {path}")
            except Exception:
                pass

        return results


async def main():
    all_results = {}
    for name, host in NODES.items():
        results = await probe_node(name, host)
        all_results[name] = results

    print(f"\n{'='*60}")
    print("  RESUMO FINAL")
    print(f"{'='*60}")
    for name, results in all_results.items():
        print(f"\n  {name}:")
        for path in results:
            val = results[path]
            count = len(val) if isinstance(val, list) else "obj"
            print(f"    ✓ {path}  ({count})")


if __name__ == "__main__":
    asyncio.run(main())
