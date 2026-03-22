import scapy.all as scapy
from getmac import get_mac_address
import socket
import json

class DeviceScanner:
    def __init__(self, iface=None):
        self.iface = iface

    def scan(self, network="192.168.88.0/24"):
        devices = []
        arp_request = scapy.ARP(pdst=network)
        broadcast = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
        arp_request_broadcast = broadcast / arp_request
        answered = scapy.srp(arp_request_broadcast, timeout=2, iface=self.iface, verbose=False)[0]

        for sent, received in answered:
            ip = received.psrc
            mac = received.hwsrc
            vendor = self.get_vendor(mac)
            hostname = self.get_hostname(ip)
            device = {
                "ip": ip,
                "mac": mac,
                "vendor": vendor,
                "hostname": hostname,
                "classification": {
                    "role": "unknown",
                    "confidence": 0.2,
                    "open_ports": []
                },
                "services": []
            }
            devices.append(device)
        return devices

    def get_vendor(self, mac):
        try:
            from getmac.vendor import EUI, oui
            return oui.get(mac) or self.oui_lookup(mac) or "Desconhecido"
        except Exception:
            return self.oui_lookup(mac) or "Desconhecido"

    def oui_lookup(self, mac):
        oui_map = {
            "f4:1e:57": "MikroTik",
            "38:9d:92": "Seiko Epson Corporation",
            "08:c2:24": "Amazon Technologies Inc."
        }
        prefix = mac.lower()[:8]
        return oui_map.get(prefix.replace(':', ''), None)

    def get_hostname(self, ip):
        try:
            nb_name = self.netbios_name(ip)
            if nb_name:
                return nb_name
            mdns_name = self.mdns_name(ip)
            if mdns_name:
                return mdns_name
            return socket.getfqdn(ip)
        except Exception:
            return None

    def netbios_name(self, ip):
        try:
            import nmb
            n = nmb.NetBIOS()
            names = n.query_name(ip, timeout=2)
            if names:
                return names[0]
        except Exception:
            pass
        return None

    def mdns_name(self, ip):
        # Placeholder: implementar consulta mDNS se necessário
        return None

if __name__ == "__main__":
    scanner = DeviceScanner()
    devices = scanner.scan()
    print(json.dumps(devices, indent=2, ensure_ascii=False))
