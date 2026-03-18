from routeros_api import RouterOsApiPool
from routeros_api.exceptions import RouterOsApiConnectionError

DEFAULT_HOST = '192.168.88.1'
DEFAULT_USER = 'homemonitor'
DEFAULT_PASS = 'foxpass'
DEFAULT_PORT = 8728


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


def get_wan_status(host=DEFAULT_HOST, username=DEFAULT_USER, password=DEFAULT_PASS, port=DEFAULT_PORT):
    try:
        api_pool = RouterOsApiPool(host, username, password, port=port, plaintext_login=True)
        api = api_pool.get_api()
        interfaces = api.get_resource('/interface').get()
        wan_ifaces = [iface for iface in interfaces if iface.get('name') == 'ether1' or 'WAN' in iface.get('name', '').upper()]
        result = []
        for iface in wan_ifaces:
            result.append({
                'name': iface.get('name'),
                'mtu': iface.get('mtu'),
                'running': iface.get('running'),
                'type': iface.get('type'),
                'mac-address': iface.get('mac-address')
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
