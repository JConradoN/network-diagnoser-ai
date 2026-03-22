#!/usr/bin/env python3
"""
Fase 3: Login correto + exploração dos endpoints autenticados.
"""
import asyncio, re, json, os
import httpx

HOST = os.getenv("TWIBI_HOST", "192.168.88.250")
USER = os.getenv("TWIBI_USER", "admin")
PASS = os.getenv("TWIBI_PASS", "admin")
BASE = f"http://{HOST}"

# Endpoints para explorar após login
ENDPOINTS = [
    "/api/v1/device",
    "/api/v1/device/0",
    "/api/v1/status",
    "/api/v1/session",
    "/api/v1/user/0",
    "/api/v1/user",
    "/api/v1/mesh",
    "/api/v1/mesh/0",
    "/api/v1/mesh/nodes",
    "/api/v1/network",
    "/api/v1/network/lan",
    "/api/v1/network/wan",
    "/api/v1/network/lan/dhcp-lease",
    "/api/v1/wireless",
    "/api/v1/wireless/clients",
    "/api/v1/wireless/0",
    "/api/v1/clients",
    "/api/v1/system",
    "/api/v1/system/info",
    "/api/v1/dhcp",
    "/api/v1/dhcp/lease",
    "/api/v1/stats",
    "/api/v1/topology",
]


def sep(t): print(f"\n{'─'*60}\n  {t}\n{'─'*60}")


async def try_login(client):
    """Tenta várias estratégias de login e retorna (headers, cookie_jar) com sucesso."""

    # 1. Primeiro, verifica o que o bundle JS diz sobre login
    print("\n[ANALISANDO BUNDLE JS para formato de login]")
    js = await client.get(f"{BASE}/static/js/main.a7922d41.chunk.js")
    js_text = js.text

    # Busca padrões de login no JS
    patterns = [
        r'(session|login|auth)[^;{]{0,200}(username|password|user|pass)',
        r'POST[^;]{0,100}(session|login)',
        r'"(username|user|login)"',
    ]
    for p in patterns:
        for m in re.finditer(p, js_text, re.IGNORECASE):
            snippet = m.group(0)[:150]
            if any(c in snippet for c in ['{', 'fetch', 'axios', 'post']):
                print(f"  → {snippet!r}")

    # Busca literalmente a chamada de login
    for keyword in ['login', 'session', 'auth', 'password']:
        idx = js_text.lower().find(f'api/v1/{keyword}')
        if idx > 0:
            print(f"\n  Contexto de '/api/v1/{keyword}' no bundle:")
            print(f"  {js_text[max(0,idx-100):idx+200]!r}")

    print("\n[TENTATIVAS DE LOGIN]")

    attempts = [
        # (path, payload_dict)
        ("/api/v1/session",  {"username": USER, "password": PASS}),
        ("/api/v1/session",  {"user": USER, "password": PASS}),
        ("/api/v1/session",  {"login": USER, "password": PASS}),
        ("/api/v1/session",  {"username": USER, "pass": PASS}),
        ("/api/v1/login",    {"username": USER, "password": PASS}),
        ("/api/v1/login",    {"user": USER, "pass": PASS}),
        ("/api/v1/user/login", {"username": USER, "password": PASS}),
        # Alguns firmwares usam só password (sem username)
        ("/api/v1/session",  {"password": PASS}),
        ("/api/v1/login",    {"password": PASS}),
    ]

    for path, payload in attempts:
        try:
            r = await client.post(BASE + path, json=payload, timeout=5)
            print(f"  {r.status_code}  POST {path}  payload={list(payload.keys())}")
            if r.status_code not in (404, 405):
                print(f"     body: {r.text[:200]!r}")
                print(f"     set-cookie: {r.headers.get('set-cookie', '-')}")
                if r.status_code in (200, 201):
                    try:
                        j = r.json()
                        print(f"     JSON: {json.dumps(j, indent=2)[:300]}")
                        # Extrai token
                        for k in ['token','access_token','stok','sid','session_id','data']:
                            if k in j:
                                print(f"     ✓ CAMPO '{k}': {str(j[k])[:60]}")
                        return r.cookies, r.json() if r.text else {}
                    except Exception:
                        return r.cookies, {}
        except Exception as e:
            print(f"  ERR  {path}: {e}")

    return None, {}


async def probe_with_auth(client, cookies, auth_data):
    """Proba todos os endpoints com cookies/token."""
    sep("ENDPOINTS COM AUTENTICAÇÃO")

    # Monta headers de autenticação
    headers = {}
    if isinstance(auth_data, dict):
        for k in ['token', 'access_token', 'stok']:
            if k in auth_data:
                headers['Authorization'] = f"Bearer {auth_data[k]}"
                headers['X-Auth-Token'] = str(auth_data[k])
                break
        if 'data' in auth_data and isinstance(auth_data['data'], dict):
            for k in ['token', 'stok']:
                if k in auth_data['data']:
                    headers['Authorization'] = f"Bearer {auth_data['data'][k]}"
                    break

    print(f"  Headers: {headers}")
    print(f"  Cookies: {dict(cookies) if cookies else {}}")

    results = {}
    for path in ENDPOINTS:
        try:
            r = await client.get(BASE + path, headers=headers, cookies=cookies, timeout=5)
            if r.status_code not in (404, 405, 500, 502):
                try:
                    j = r.json()
                    print(f"\n  {r.status_code} ★ {path}")
                    print(f"  {json.dumps(j, indent=2, ensure_ascii=False)[:600]}")
                    results[path] = j
                except Exception:
                    if r.status_code == 200:
                        print(f"  {r.status_code}   {path} → {r.text[:100]!r}")
                    else:
                        print(f"  {r.status_code}   {path}")
        except Exception as e:
            print(f"  ERR  {path}: {e}")

    return results


async def main():
    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        # Sobrescreve o get para compatibilidade
        orig_get = client.get
        async def _get(url, **kw):
            try:
                return None, await orig_get(url, **kw)
            except Exception as e:
                return str(e), None
        # Não precisamos sobrescrever, usamos diretamente

        sep(f"FASE 3 — Login + Endpoints Autenticados ({HOST})")

        # Tenta login
        cookies, auth_data = await try_login(client)

        # Proba endpoints
        results = await probe_with_auth(client, cookies or {}, auth_data or {})

        sep("RESUMO")
        print(f"  Endpoints com dados: {[p for p in results]}")


if __name__ == "__main__":
    asyncio.run(main())
