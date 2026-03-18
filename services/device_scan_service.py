# DeviceScanner integration
from scanner.device_scanner import DeviceScanner

def scan_devices(network="192.168.88.0/24", iface=None):
    scanner = DeviceScanner(iface=iface)
    return scanner.scan(network=network)
