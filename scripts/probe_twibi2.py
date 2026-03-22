#!/usr/bin/env python3
"""
Fase 2: Extrai bundle JS do Twibi e busca endpoints de API.
"""

import asyncio
import re
import json
import os
import httpx

HOST = os.getenv("TWIBI_HOST", "192.168.88.250")
USER = os.getenv("TWIBI_USER", "admin")
PASS = os.getenv("TWIBI_PASS", "admin")

EXTRA_PORTS = [8888]

async def get(client, url):
    try:
        r = await client.get(url, timeout=8)
        return r.status_code, r.text
    except Exception as e:
        return None, str(e)

async def post(client, url, **kwargs):
    try:
        r = await client.post(url, timeout=8, **kwargs)
        return r.status_code, r.text
    except Exception as e:
        return None, str(e)

def extract_api_strings(js_text):
    """Extrai strings que parecem endpoints de API do bundle JS."""
    patterns = [
        r'["\`](/[a-zA-Z0-9_\-/{}:]+)["\`]',  # strings com /path
        r'url\s*[=:]\s*["\`]([^"\'`]+)["\`]',
        r'path\s*[=:]\s*["\`]([^"\'`]+)["\`]',
        r'endpoint\s*[=:]\s*["\`]([^"\'`]+)["\`]',
        r'fetch\(["\`]([^"\'`]+)["\`]',
        r'axios\.[a-z]+\(["\`]([^"\'`]+)["\`]',
    ]
    found = set()
    for p in patterns:
        for m in re.finditer(p, js_text):
            s = m.group(1)
            if s.startswith('/') and len(s) > 2 and not s.endswith('.js') and not s.endswith('.css'):
                found.add(s)
    # Filtra só os que parecem API (não assets)
    api = sorted(s for s in found if any(k in s.lower() for k in
        ['api', 'login', 'auth', 'token', 'client', 'device', 'wireless',
         'mesh', 'network', 'status', 'system', 'info', 'health', 'config',
         'user', 'password', 'station', 'host', 'dhcp', 'wan', 'lan']))
    return api

async def probe_port(base_url):
    print(f"\n{'='*60}")
    print(f"Base: {base_url}")
    print('='*60)

    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:

        # 1. Pega o HTML raiz
        status, html = await get(client, base_url + "/")
        print(f"\n[/] status={status}, len={len(html)}")

        # 2. Extrai <script src=...>
        script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html)
        print(f"\n[SCRIPTS encontrados]: {script_srcs}")

        all_api_strings = set()

        for src in script_srcs:
            if not src.startswith('http'):
                src = base_url + ('' if src.startswith('/') else '/') + src
            print(f"\n  → Baixando: {src}")
            s2, js = await get(client, src)
            if s2 == 200:
                apis = extract_api_strings(js)
                print(f"     {len(apis)} strings de API encontradas")
                all_api_strings.update(apis)
                # Mostra amostra
                for a in apis[:20]:
                    print(f"       {a}")

        # 3. Tenta logins para pegar token
        print(f"\n[LOGIN ATTEMPTS]")
        token = None
        stok = None

        login_payloads = [
            ("/api/v1/login",      {"username": USER, "password": PASS}),
            ("/api/login",         {"username": USER, "password": PASS}),
            ("/api/login",         {"user": USER, "password": PASS}),
            ("/api/auth/login",    {"username": USER, "password": PASS}),
            ("/api/auth",          {"username": USER, "password": PASS}),
            ("/api/user/login",    {"username": USER, "password": PASS}),
            ("/login",             {"username": USER, "password": PASS}),
            # Formato form
        ]
        for path, payload in login_payloads:
            url = base_url + path
            st, body = await post(client, url, json=payload)
            if st and st not in (404, 405):
                print(f"  {st}  {path}")
                try:
                    j = json.loads(body)
                    print(f"     → {json.dumps(j, indent=2, ensure_ascii=False)[:300]}")
                    # Tenta extrair token
                    if isinstance(j, dict):
                        for k in ['token','access_token','stok','data','result']:
                            if k in j:
                                if isinstance(j[k], str):
                                    token = j[k]
                                elif isinstance(j[k], dict):
                                    token = j[k].get('token') or j[k].get('access_token') or j[k].get('stok')
                except Exception:
                    print(f"     → {body[:200]!r}")

        # 4. Se tiver token, tenta endpoints descobertos + lista fixa
        extra_endpoints = [
            "/api/v1/system/info",
            "/api/v1/device",
            "/api/v1/clients",
            "/api/v1/wireless/clients",
            "/api/v1/mesh",
            "/api/v1/mesh/nodes",
            "/api/v1/network",
            "/api/v1/status",
            "/api/system/info",
            "/api/clients",
            "/api/wireless/clients",
            "/api/mesh/nodes",
            "/api/status",
        ]
        all_endpoints = list(set(list(all_api_strings) + extra_endpoints))

        headers = {}
        if token:
            print(f"\n  ✓ Token obtido: {token[:30]}...")
            headers = {"Authorization": f"Bearer {token}",
                       "X-Auth-Token": token}

        print(f"\n[PROBING {len(all_endpoints)} ENDPOINTS]")
        for path in sorted(all_endpoints):
            url = base_url + path
            try:
                r = await client.get(url, headers=headers, timeout=4)
                if r.status_code not in (404, 405, 500):
                    try:
                        j = r.json()
                        print(f"  {r.status_code} ★ {path}")
                        print(f"     {json.dumps(j, indent=2, ensure_ascii=False)[:400]}")
                    except Exception:
                        if r.status_code == 200:
                            print(f"  {r.status_code}   {path} → {r.text[:100]!r}")
                        else:
                            print(f"  {r.status_code}   {path}")
            except Exception:
                pass


async def main():
    targets = [
        f"http://{HOST}",
        f"http://{HOST}:8888",
    ]
    for base in targets:
        await probe_port(base)

if __name__ == "__main__":
    asyncio.run(main())
