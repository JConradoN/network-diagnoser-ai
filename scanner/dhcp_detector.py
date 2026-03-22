"""DHCP server discovery module."""

from __future__ import annotations

import random

try:
    from scapy.all import BOOTP, DHCP, IP, UDP, Ether, RandMAC, conf, sendp, sniff
    from scapy.error import Scapy_Exception
except ImportError:  # pragma: no cover
    BOOTP = DHCP = IP = UDP = Ether = RandMAC = conf = sendp = sniff = None

    class Scapy_Exception(Exception):
        """Fallback exception when scapy is not installed."""


class DHCPDetectorError(Exception):
    """Base exception for DHCP detector errors."""


class DHCPDetector:
    """Discover DHCP servers by broadcasting DHCPDISCOVER."""

    def __init__(self, timeout: int = 4, iface: str | None = None) -> None:
        self.timeout = timeout
        self.iface = iface

    def discover_servers(self) -> list[dict]:
        """Return discovered DHCP servers from DHCPOFFER replies."""
        if any(item is None for item in (BOOTP, DHCP, IP, UDP, Ether, RandMAC, sendp, sniff)):
            return []

        xid = random.randint(1, 0xFFFFFFFF)
        mac = str(RandMAC())

        discover = (
            Ether(src=mac, dst="ff:ff:ff:ff:ff:ff")
            / IP(src="0.0.0.0", dst="255.255.255.255")
            / UDP(sport=68, dport=67)
            / BOOTP(chaddr=bytes.fromhex(mac.replace(":", "")), xid=xid)
            / DHCP(options=[("message-type", "discover"), ("param_req_list", [1, 3, 6, 15, 51, 58, 59]), "end"])
        )

        try:
            sendp(discover, iface=self.iface or conf.iface, verbose=False)
            offers = sniff(
                iface=self.iface or conf.iface,
                timeout=self.timeout,
                filter="udp and (port 67 or port 68)",
                lfilter=lambda p: p.haslayer(BOOTP) and getattr(p[BOOTP], "xid", None) == xid,
            )
        except (PermissionError, OSError, Scapy_Exception):
            return []

        servers: dict[str, dict] = {}
        for packet in offers:
            if not packet.haslayer(DHCP):
                continue

            options = packet[DHCP].options
            option_map = {opt[0]: opt[1] for opt in options if isinstance(opt, tuple) and len(opt) >= 2}
            msg_type = option_map.get("message-type")
            if str(msg_type).lower() not in {"2", "offer"}:
                continue

            server_id = option_map.get("server_id") or packet[IP].src
            ip_offer = packet[BOOTP].yiaddr

            servers[str(server_id)] = {
                "server_ip": str(server_id),
                "offered_ip": ip_offer,
            }

        return list(servers.values())
