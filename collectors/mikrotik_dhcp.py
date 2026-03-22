import os
from routeros_api import RouterOsApiPool
from routeros_api.exceptions import RouterOsApiConnectionError

_DEFAULT_HOST = os.getenv("ND_MIKROTIK_HOST", "192.168.88.1")
_DEFAULT_USER = os.getenv("ND_MIKROTIK_USER", "homemonitor")
_DEFAULT_PASS = os.getenv("ND_MIKROTIK_PASS", "")
_DEFAULT_PORT = int(os.getenv("ND_MIKROTIK_PORT", "8728"))

def get_dhcp_details(host=None, username=None, password=None, port=None):
    host     = host     or _DEFAULT_HOST
    username = username or _DEFAULT_USER
    password = password if password is not None else _DEFAULT_PASS
    port     = port     or _DEFAULT_PORT
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
