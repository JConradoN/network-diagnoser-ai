from routeros_api import RouterOsApiPool
from routeros_api.exceptions import RouterOsApiConnectionError

def get_dhcp_details(host='192.168.88.1', username='homemonitor', password='foxpass', port=8728):
    try:
        api_pool = RouterOsApiPool(host, username, password, port=port, plaintext_login=True)
        api = api_pool.get_api()
        leases = api.get_resource('/ip/dhcp-server/lease').get()
        result = []
        for lease in leases:
            address = lease.get('address')
            mac = lease.get('mac-address')
            host_name = lease.get('host-name', '')
            # Limpa aspas do host-name
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
