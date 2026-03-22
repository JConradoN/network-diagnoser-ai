def merge_network_data(arp_scan_results, dhcp_leases):
    # Cria um dicionário de dispositivos ARP por IP
    arp_by_ip = {dev.get('ip'): dev for dev in arp_scan_results}
    merged = []
    # Itera sobre todos os leases DHCP
    for lease in dhcp_leases:
        ip = lease.get('address')
        hostname = lease.get('host-name', '').replace('"', '').strip()
        mac = lease.get('mac-address')
        comment = lease.get('comment', '')
        status = lease.get('status', '')
        if ip in arp_by_ip:
            # Atualiza hostname do ARP com o valor do MikroTik
            device = arp_by_ip[ip].copy()
            device['hostname'] = hostname or device.get('hostname')
            device['dhcp_comment'] = comment
            device['dhcp_status'] = status
            merged.append(device)
        else:
            # Adiciona dispositivo "invisível" (não visto no ARP)
            merged.append({
                'ip': ip,
                'mac': mac,
                'hostname': hostname,
                'dhcp_comment': comment,
                'dhcp_status': status,
                'classification': {
                    'role': 'Invisível/Provável Firewall',
                    'confidence': 0.1,
                    'open_ports': []
                },
                'services': [],
                'status': 'Inativo',
                'registered': True
            })
    # Adiciona dispositivos ARP que não estão nos leases DHCP
    for ip, device in arp_by_ip.items():
        if not any(lease.get('address') == ip for lease in dhcp_leases):
            merged.append(device)
    return merged
