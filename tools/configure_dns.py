#!/usr/bin/env python3
"""
Configura DNS estático no MikroTik para todos os dispositivos conhecidos da rede.
- Ativa servidor DNS com allow-remote-requests
- Adiciona registros estáticos A para cada hostname
- Configura DHCP network para distribuir MikroTik como servidor DNS
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routeros_api import RouterOsApiPool
from routeros_api.exceptions import RouterOsApiConnectionError

HOST  = os.getenv("ND_MIKROTIK_HOST", "192.168.88.1")
USER  = os.getenv("ND_MIKROTIK_USER", "admin")       # DNS config requer admin
PASS  = os.getenv("ND_MIKROTIK_PASS", "")
PORT  = int(os.getenv("ND_MIKROTIK_PORT", "8728"))

# Mapa hostname → IP (todos os dispositivos fixos da rede)
STATIC_HOSTS = {
    "mikrotik":              "192.168.88.1",
    "fox-dev":               "192.168.88.200",
    "fox-note":              "192.168.88.201",
    "twibi":                 "192.168.88.210",
    "twibi-principal":       "192.168.88.210",
    "twibi-quintal":         "192.168.88.211",
    "twibi-sala":            "192.168.88.212",
    "epson":                 "192.168.88.230",
    "impressora":            "192.168.88.230",
    "lg-tv":                 "192.168.88.240",
    "ps5":                   "192.168.88.241",
    "alexa":                 "192.168.88.242",
    "emilia-pc":             "192.168.88.220",
}


def connect():
    pool = RouterOsApiPool(HOST, USER, PASS, port=PORT, plaintext_login=True)
    return pool, pool.get_api()


def enable_dns_server(api):
    print("→ Ativando servidor DNS com allow-remote-requests...")
    api.get_resource('/ip/dns').set(
        **{"allow-remote-requests": "yes"}
    )
    cfg = api.get_resource('/ip/dns').get()[0]
    print(f"  DNS servers: {cfg.get('servers','(nenhum)')}")
    print(f"  allow-remote-requests: {cfg.get('allow-remote-requests')}")


def clear_existing_static(api):
    print("→ Removendo registros DNS estáticos existentes (gerados por este script)...")
    dns_static = api.get_resource('/ip/dns/static')
    existing = dns_static.get()
    removed = 0
    for entry in existing:
        name = entry.get('name', '')
        # Remove apenas entradas que batem com nossa lista
        if name in STATIC_HOSTS:
            dns_static.remove(id=entry['.id'])
            removed += 1
    print(f"  {removed} entradas removidas.")


def add_static_entries(api):
    print("→ Adicionando registros DNS estáticos...")
    dns_static = api.get_resource('/ip/dns/static')
    for hostname, ip in sorted(STATIC_HOSTS.items()):
        try:
            dns_static.add(name=hostname, address=ip, ttl="1d")
            print(f"  ✓  {hostname:<25} → {ip}")
        except Exception as e:
            print(f"  ✗  {hostname:<25} → {ip}  [{e}]")


def configure_dhcp_dns(api):
    """Configura o DHCP network para distribuir MikroTik como DNS."""
    print("→ Configurando DHCP para distribuir MikroTik como DNS...")
    dhcp_networks = api.get_resource('/ip/dhcp-server/network')
    networks = dhcp_networks.get()
    for net in networks:
        addr = net.get('address', '')
        if addr.startswith('192.168.88'):
            dhcp_networks.set(id=net['.id'], **{"dns-server": HOST})
            print(f"  ✓  DHCP network {addr} → dns-server={HOST}")


def show_current_dns(api):
    print("\n--- Registros DNS estáticos atuais ---")
    entries = api.get_resource('/ip/dns/static').get()
    for e in sorted(entries, key=lambda x: x.get('name', '')):
        print(f"  {e.get('name',''):<25} → {e.get('address','')}")
    print(f"  Total: {len(entries)} entradas\n")


def main():
    print(f"Conectando ao MikroTik {HOST}:{PORT} como '{USER}'...")
    try:
        pool, api = connect()
    except RouterOsApiConnectionError as e:
        print(f"ERRO: Falha na conexão: {e}")
        print("  Verifique se ND_MIKROTIK_USER=admin e ND_MIKROTIK_PASS estão corretos.")
        sys.exit(1)

    try:
        enable_dns_server(api)
        clear_existing_static(api)
        add_static_entries(api)
        configure_dhcp_dns(api)
        show_current_dns(api)
        print("✅ DNS configurado com sucesso!")
        print(f"\nAcesse o dashboard em: http://fox-dev")
        print(f"(Após renovar o DHCP nos clientes ou reconectar à rede)")
    finally:
        pool.disconnect()


if __name__ == "__main__":
    main()
