"""SNMP scanner alternativo usando subprocess e snmpget/snmpwalk."""

import subprocess
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class SNMPResult:
    ip: str
    sys_name: str | None
    sys_descr: str | None
    sys_uptime: str | None
    interfaces_count: int | None
    interfaces: list[dict[str, Any]]
    ip_forwarding: str | None
    route_destinations: list[str]

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "sysName": self.sys_name,
            "sysDescr": self.sys_descr,
            "sysUpTime": self.sys_uptime,
            "interfacesCount": self.interfaces_count,
            "interfaces": self.interfaces,
            "ipForwarding": self.ip_forwarding,
            "routeDestinations": self.route_destinations,
            "routeCount": len(self.route_destinations),
        }

class SNMPScannerAlt:
    """Coleta OIDs SNMP usando snmpget/snmpwalk via subprocess."""

    OIDS = {
        "sysName": "1.3.6.1.2.1.1.5.0",
        "sysDescr": "1.3.6.1.2.1.1.1.0",
        "sysUpTime": "1.3.6.1.2.1.1.3.0",
        "ifNumber": "1.3.6.1.2.1.2.1.0",
        "ipForwarding": "1.3.6.1.2.1.4.1.0",
    }

    def __init__(self, community: str = "public", timeout: int = 2):
        self.community = community
        self.timeout = timeout

    def _snmpget(self, ip: str, oid: str) -> str | None:
        try:
            result = subprocess.run(
                ["snmpget", "-v2c", "-c", self.community, ip, oid],
                capture_output=True, text=True, timeout=self.timeout
            )
            if result.returncode != 0:
                return None
            # Parse output: SNMPv2-MIB::sysName.0 = STRING: MyDevice
            parts = result.stdout.split("=", 1)
            if len(parts) == 2:
                return parts[1].strip().split(":", 1)[-1].strip()
            return None
        except Exception:
            return None

    def collect(self, ip: str) -> SNMPResult | None:
        values = {name: self._snmpget(ip, oid) for name, oid in self.OIDS.items()}
        if all(values[item] is None for item in ("sysName", "sysDescr", "sysUpTime")):
            return None
        # Interfaces e rotas podem ser coletadas com snmpwalk (não implementado aqui)
        return SNMPResult(
            ip=ip,
            sys_name=values["sysName"],
            sys_descr=values["sysDescr"],
            sys_uptime=values["sysUpTime"],
            interfaces_count=None,
            interfaces=[],
            ip_forwarding=values["ipForwarding"],
            route_destinations=[],
        )
