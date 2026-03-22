"""Network-related helper functions."""

from __future__ import annotations

import ipaddress
import socket

try:
    from scapy.all import get_if_addr, get_if_list
except ImportError:  # pragma: no cover
    get_if_addr = get_if_list = None


def detect_local_subnet(default_prefix: int = 24) -> str:
    """Detect local IPv4 subnet using outbound interface IP."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        local_ip = sock.getsockname()[0]
    except OSError as exc:
        raise RuntimeError("Nao foi possivel detectar o IP local") from exc
    finally:
        sock.close()

    network = ipaddress.ip_network(f"{local_ip}/{default_prefix}", strict=False)
    return str(network)


def sort_ip_strings(values: list[str]) -> list[str]:
    """Sort a list of IPv4 strings in ascending numerical order."""
    return sorted(values, key=lambda value: ipaddress.ip_address(value))


def list_network_interfaces() -> list[dict]:
    """List available network interfaces with best-effort IPv4 address."""
    interfaces: list[dict] = []

    if get_if_list is not None:
        for name in get_if_list():
            ipv4 = None
            if get_if_addr is not None:
                try:
                    ip_value = get_if_addr(name)
                    if ip_value and ip_value != "0.0.0.0":
                        ipv4 = ip_value
                except Exception:
                    ipv4 = None

            interfaces.append({"name": name, "ipv4": ipv4})

        unique = {item["name"]: item for item in interfaces}
        return sorted(unique.values(), key=lambda item: item["name"])

    # Fallback when scapy is unavailable.
    try:
        names = [item[1] for item in socket.if_nameindex()]
    except OSError:
        names = []

    for name in names:
        interfaces.append({"name": name, "ipv4": None})

    return sorted(interfaces, key=lambda item: item["name"])
