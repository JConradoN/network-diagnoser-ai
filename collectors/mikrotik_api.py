import os
from routeros_api import RouterOsApiPool
from routeros_api.exceptions import RouterOsApiConnectionError

DEFAULT_HOST = os.getenv("ND_MIKROTIK_HOST", "192.168.88.1")
DEFAULT_USER = os.getenv("ND_MIKROTIK_USER", "homemonitor")
DEFAULT_PASS = os.getenv("ND_MIKROTIK_PASS", "")
DEFAULT_PORT = int(os.getenv("ND_MIKROTIK_PORT", "8728"))


def get_dhcp_details(host=DEFAULT_HOST, username=DEFAULT_USER, password=DEFAULT_PASS, port=DEFAULT_PORT):
    try:
        api_pool = RouterOsApiPool(host, username, password, port=port, plaintext_login=True)
        api = api_pool.get_api()
        leases = api.get_resource('/ip/dhcp-server/lease').get()
        result = []
        for lease in leases:
            address = lease.get('address')
            mac = lease.get('mac-address')
            host_name = lease.get('host-name', '')
            if isinstance(host_name, str):
                host_name = host_name.replace('"', '').strip()
            comment = lease.get('comment', '')
            status = lease.get('status', '')
            result.append({
                'address': address,
                'mac-address': mac,
                'host-name': host_name,
                'comment': comment,
                'status': status
            })
        api_pool.disconnect()
        return result
    except RouterOsApiConnectionError as exc:
        return {'error': f'Falha na conexão: {exc}'}
    except Exception as exc:
        return {'error': str(exc)}


def _is_private_ip(ip: str) -> bool:
    """Retorna True se o IP for de uma faixa privada RFC-1918."""
    if not ip:
        return False
    try:
        parts = list(map(int, ip.split('.')))
        if parts[0] == 10:
            return True
        if parts[0] == 172 and 16 <= parts[1] <= 31:
            return True
        if parts[0] == 192 and parts[1] == 168:
            return True
    except Exception:
        pass
    return False


def get_wan_status(host=DEFAULT_HOST, username=DEFAULT_USER, password=DEFAULT_PASS, port=DEFAULT_PORT):
    try:
        api_pool = RouterOsApiPool(host, username, password, port=port, plaintext_login=True)
        api = api_pool.get_api()

        # Interfaces WAN (por nome)
        interfaces = api.get_resource('/interface').get()
        wan_ifaces = {
            iface['name']: iface
            for iface in interfaces
            if 'wan' in iface.get('name', '').lower()
        }

        # IPs atribuídos a cada interface
        ip_addresses = api.get_resource('/ip/address').get()
        iface_ips = {}
        for addr in ip_addresses:
            iface_name = addr.get('interface', '')
            iface_ips[iface_name] = addr.get('address', '').split('/')[0]

        # Status PPPoE clients
        pppoe_status = {}
        try:
            pppoe_clients = api.get_resource('/interface/pppoe-client').get()
            for client in pppoe_clients:
                iface_name = client.get('name', '')
                pppoe_status[iface_name] = {
                    'running':    client.get('running'),
                    'connected':  client.get('connected'),
                    'ac-name':    client.get('ac-name'),
                    'add-default-route': client.get('add-default-route'),
                }
        except Exception:
            pass

        result = []
        for name, iface in wan_ifaces.items():
            running = iface.get('running') in (True, 'true')
            wan_ip  = iface_ips.get(name, '')
            # Para PPPoE, o IP fica na interface virtual (ex: pppoe-vivo), não na física
            # Tenta achar IP em interface pppoe que usa esta interface
            if not wan_ip:
                for pname, pdata in pppoe_status.items():
                    pppoe_iface_ip = iface_ips.get(pname, '')
                    if pppoe_iface_ip:
                        wan_ip = pppoe_iface_ip
                        break

            bridge_mode_ok = not _is_private_ip(wan_ip) if wan_ip else None

            result.append({
                'name':          name,
                'mtu':           iface.get('mtu'),
                'running':       iface.get('running'),
                'type':          iface.get('type'),
                'mac-address':   iface.get('mac-address'),
                'ip':            wan_ip or None,
                'bridge_mode':   bridge_mode_ok,   # None=desconhecido, True=ok, False=NAT ativo
                'private_ip':    _is_private_ip(wan_ip) if wan_ip else None,
                'pppoe':         pppoe_status.get(name),
            })

        api_pool.disconnect()
        return result
    except RouterOsApiConnectionError as exc:
        return {'error': f'Falha na conexão: {exc}'}
    except Exception as exc:
        return {'error': str(exc)}


def get_wifi_clients(host=DEFAULT_HOST, username=DEFAULT_USER, password=DEFAULT_PASS, port=DEFAULT_PORT):
    """Retorna clientes conectados à interface wireless do MikroTik com sinal e qualidade."""
    try:
        api_pool = RouterOsApiPool(host, username, password, port=port, plaintext_login=True)
        api = api_pool.get_api()
        clients = api.get_resource('/interface/wireless/registration-table').get()
        result = []
        for client in clients:
            signal_raw = str(client.get('signal-strength', '0'))
            try:
                signal_dbm = int(signal_raw.split('dBm')[0].split('@')[0].strip())
            except (ValueError, AttributeError):
                signal_dbm = -100
            ccq_raw = str(client.get('ccq', '0'))
            try:
                ccq = int(ccq_raw.replace('%', '').strip())
            except (ValueError, AttributeError):
                ccq = 0
            result.append({
                'mac': client.get('mac-address', ''),
                'interface': client.get('interface', ''),
                'signal_dbm': signal_dbm,
                'ccq': ccq,
                'tx_rate': client.get('tx-rate', ''),
                'rx_rate': client.get('rx-rate', ''),
                'uptime': client.get('uptime', ''),
            })
        api_pool.disconnect()
        return result
    except RouterOsApiConnectionError as exc:
        return {'error': f'Falha na conexão: {exc}'}
    except Exception as exc:
        return {'error': str(exc)}


def get_neighbors(host=DEFAULT_HOST, username=DEFAULT_USER, password=DEFAULT_PASS, port=DEFAULT_PORT):
    try:
        api_pool = RouterOsApiPool(host, username, password, port=port, plaintext_login=True)
        api = api_pool.get_api()
        neighbors = api.get_resource('/ip/neighbor').get()
        result = []
        for neighbor in neighbors:
            result.append({
                'address': neighbor.get('address'),
                'mac-address': neighbor.get('mac-address'),
                'identity': neighbor.get('identity'),
                'platform': neighbor.get('platform'),
                'version': neighbor.get('version'),
                'interface': neighbor.get('interface'),
                'board': neighbor.get('board'),
                'uptime': neighbor.get('uptime')
            })
        api_pool.disconnect()
        return result
    except RouterOsApiConnectionError as exc:
        return {'error': f'Falha na conexão: {exc}'}
    except Exception as exc:
        return {'error': str(exc)}
