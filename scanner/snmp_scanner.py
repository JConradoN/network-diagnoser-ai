"""SNMP data collection module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from utils.logger import get_logger

try:
    from pysnmp.hlapi import (
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        getCmd,
        nextCmd,
    )
except Exception as exc:
    import sys
    print(f"[SNMPScanner] Falha ao importar pysnmp.hlapi: {exc}", file=sys.stderr)
    CommunityData = ContextData = ObjectIdentity = ObjectType = None
    SnmpEngine = UdpTransportTarget = getCmd = nextCmd = None


class SNMPScannerError(Exception):
    """Base exception for SNMP scanner errors."""


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


class SNMPScanner:
    """Collect common SNMP system OIDs from a host."""

    OIDS = {
        "sysName": "1.3.6.1.2.1.1.5.0",
        "sysDescr": "1.3.6.1.2.1.1.1.0",
        "sysUpTime": "1.3.6.1.2.1.1.3.0",
        "ifNumber": "1.3.6.1.2.1.2.1.0",
        "ipForwarding": "1.3.6.1.2.1.4.1.0",
    }

    IF_DESCR_OID = "1.3.6.1.2.1.2.2.1.2"
    IF_OPER_STATUS_OID = "1.3.6.1.2.1.2.2.1.8"
    ROUTE_DEST_OID = "1.3.6.1.2.1.4.21.1.1"

    def __init__(self, community: str = "public", timeout: int = 2) -> None:
        self.community = community
        self.timeout = timeout
        self.logger = get_logger(self.__class__.__name__)

    def collect(self, ip: str) -> SNMPResult | None:
        """Collect SNMP fields for a target IP; returns None if unavailable."""
        if getCmd is None:
            self.logger.warning("pysnmp nao instalado, pulando SNMP para %s", ip)
            return None

        values: dict[str, str | None] = {
            "sysName": None,
            "sysDescr": None,
            "sysUpTime": None,
            "ifNumber": None,
            "ipForwarding": None,
        }

        for name, oid in self.OIDS.items():
            values[name] = self._get_oid_value(ip, oid)

        if all(values[item] is None for item in ("sysName", "sysDescr", "sysUpTime")):
            return None

        if_descr = self._walk_column(ip, self.IF_DESCR_OID)
        if_status = self._walk_column(ip, self.IF_OPER_STATUS_OID)
        route_destinations = list(self._walk_column(ip, self.ROUTE_DEST_OID).values())

        interfaces = []
        for index, name in if_descr.items():
            interfaces.append(
                {
                    "index": index,
                    "name": name,
                    "operStatus": self._normalize_oper_status(if_status.get(index)),
                }
            )

        interfaces = sorted(interfaces, key=lambda item: item["index"])

        interfaces_count = None
        if values["ifNumber"] is not None:
            try:
                interfaces_count = int(str(values["ifNumber"]))
            except ValueError:
                interfaces_count = len(interfaces) if interfaces else None
        elif interfaces:
            interfaces_count = len(interfaces)

        return SNMPResult(
            ip=ip,
            sys_name=values["sysName"],
            sys_descr=values["sysDescr"],
            sys_uptime=values["sysUpTime"],
            interfaces_count=interfaces_count,
            interfaces=interfaces,
            ip_forwarding=self._normalize_ip_forwarding(values["ipForwarding"]),
            route_destinations=sorted(set(route_destinations)),
        )

    def _get_oid_value(self, ip: str, oid: str) -> str | None:
        """Get single OID value from target; returns None on SNMP read errors."""
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(self.community, mpModel=1),
            UdpTransportTarget((ip, 161), timeout=self.timeout, retries=0),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )

        try:
            error_indication, error_status, _, var_binds = next(iterator)
        except Exception:
            return None

        if error_indication or error_status or not var_binds:
            return None

        return str(var_binds[0][1])

    def _walk_column(self, ip: str, base_oid: str, limit: int = 64) -> dict[int, str]:
        """Walk an SNMP column and return values by index."""
        if nextCmd is None:
            return {}

        results: dict[int, str] = {}
        try:
            iterator = nextCmd(
                SnmpEngine(),
                CommunityData(self.community, mpModel=1),
                UdpTransportTarget((ip, 161), timeout=self.timeout, retries=0),
                ContextData(),
                ObjectType(ObjectIdentity(base_oid)),
                lexicographicMode=False,
                maxRows=limit,
            )

            for error_indication, error_status, _, var_binds in iterator:
                if error_indication or error_status or not var_binds:
                    break

                oid_obj, value_obj = var_binds[0]
                oid_str = str(oid_obj)
                if not oid_str.startswith(base_oid + "."):
                    break

                index_str = oid_str.split(".")[-1]
                try:
                    index = int(index_str)
                except ValueError:
                    continue

                results[index] = str(value_obj)
        except Exception:
            return {}

        return results

    @staticmethod
    def _normalize_oper_status(value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip().lower()
        status_map = {
            "1": "up",
            "2": "down",
            "3": "testing",
            "4": "unknown",
            "5": "dormant",
            "6": "notPresent",
            "7": "lowerLayerDown",
        }
        return status_map.get(normalized, value)

    @staticmethod
    def _normalize_ip_forwarding(value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip().lower()
        if normalized == "1":
            return "forwarding"
        if normalized == "2":
            return "not-forwarding"
        return value
