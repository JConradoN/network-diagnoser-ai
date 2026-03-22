"""ARP network scanner module.

This module scans the local network and returns discovered devices with
IP address, MAC address and manufacturer information.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import ipaddress
import socket
from typing import List, Optional

try:
    from scapy.all import ARP, Ether, conf, srp
    from scapy.error import Scapy_Exception
except ImportError:  # pragma: no cover - depends on runtime environment
    ARP = Ether = conf = srp = None

    class Scapy_Exception(Exception):
        """Fallback exception when scapy is not installed."""


class NetworkScannerError(Exception):
    """Base exception for scanner-related errors."""


class DependencyError(NetworkScannerError):
    """Raised when required dependencies are missing."""


class SubnetDetectionError(NetworkScannerError):
    """Raised when local subnet detection fails."""


class ScanExecutionError(NetworkScannerError):
    """Raised when ARP scan execution fails."""


@dataclass(frozen=True)
class DeviceInfo:
    """Represents a device discovered on the network."""

    ip: str
    mac: str
    vendor: str

    def to_dict(self) -> dict:
        """Return a dictionary representation of the discovered device."""
        return asdict(self)


class NetworkScanner:
    """Scans local networks using ARP and returns discovered devices."""

    def __init__(self, subnet: Optional[str] = None, timeout: int = 2, retry: int = 1) -> None:
        """Initialize scanner configuration.

        Args:
            subnet: Optional CIDR subnet, e.g. "192.168.0.0/24".
            timeout: Timeout in seconds for ARP replies.
            retry: Number of retries used by scapy's srp.
        """
        self.timeout = timeout
        self.retry = retry
        self.subnet = self._validate_subnet(subnet) if subnet else None

    @staticmethod
    def _validate_subnet(subnet: str) -> str:
        """Validate and normalize a subnet in CIDR format."""
        try:
            network = ipaddress.ip_network(subnet, strict=False)
        except ValueError as exc:
            raise SubnetDetectionError(f"Sub-rede invalida: {subnet}") from exc

        if network.version != 4:
            raise SubnetDetectionError("Somente IPv4 e suportado para ARP scan.")

        return str(network)

    @staticmethod
    def _detect_local_subnet() -> str:
        """Best-effort detection of local subnet.

        Uses the default outbound interface IP and assumes /24 when netmask
        cannot be inferred without extra dependencies.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
        except OSError as exc:
            raise SubnetDetectionError("Nao foi possivel detectar o IP local.") from exc
        finally:
            sock.close()

        try:
            network = ipaddress.ip_network(f"{local_ip}/24", strict=False)
            return str(network)
        except ValueError as exc:
            raise SubnetDetectionError("Falha ao calcular a sub-rede local.") from exc

    @staticmethod
    def _resolve_vendor(mac_address: str) -> str:
        """Resolve device vendor from MAC address using scapy manuf DB."""
        if conf is None or getattr(conf, "manufdb", None) is None:
            return "Unknown"

        manufdb = conf.manufdb

        # Different scapy versions expose different methods.
        for method_name in ("_get_manuf", "lookup", "_resolve_MAC"):
            method = getattr(manufdb, method_name, None)
            if callable(method):
                try:
                    value = method(mac_address)
                except Exception:
                    continue
                if value:
                    vendor = str(value).strip()
                    if vendor and vendor.lower() not in {"unknown", mac_address.lower()}:
                        return vendor

        return "Unknown"

    def scan(self, subnet: Optional[str] = None) -> List[DeviceInfo]:
        """Run ARP scan and return discovered devices.

        Args:
            subnet: Optional subnet override in CIDR format.

        Returns:
            List of discovered DeviceInfo objects.

        Raises:
            DependencyError: If scapy is not installed.
            SubnetDetectionError: If subnet is invalid or cannot be detected.
            ScanExecutionError: If scan execution fails.
        """
        if ARP is None or Ether is None or srp is None:
            raise DependencyError(
                "Dependencia ausente: instale scapy com 'pip install scapy'."
            )

        target_subnet = self.subnet
        if subnet:
            target_subnet = self._validate_subnet(subnet)
        if not target_subnet:
            target_subnet = self._detect_local_subnet()

        packet = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=target_subnet)

        try:
            answered, _ = srp(
                packet,
                timeout=self.timeout,
                retry=self.retry,
                verbose=False,
            )
        except PermissionError as exc:
            raise ScanExecutionError(
                "Permissao negada para ARP scan. Execute com privilegios elevados."
            ) from exc
        except (Scapy_Exception, OSError) as exc:
            raise ScanExecutionError(f"Falha durante ARP scan: {exc}") from exc

        devices_by_ip = {}
        for _, received in answered:
            ip_address = getattr(received, "psrc", "")
            mac_address = getattr(received, "hwsrc", "")

            if not ip_address or not mac_address:
                continue

            devices_by_ip[ip_address] = DeviceInfo(
                ip=ip_address,
                mac=mac_address,
                vendor=self._resolve_vendor(mac_address),
            )

        return [
            devices_by_ip[ip]
            for ip in sorted(devices_by_ip.keys(), key=lambda value: ipaddress.ip_address(value))
        ]

    def scan_as_dicts(self, subnet: Optional[str] = None) -> List[dict]:
        """Run scan and return devices as plain dictionaries."""
        return [device.to_dict() for device in self.scan(subnet=subnet)]


__all__ = [
    "DeviceInfo",
    "DependencyError",
    "NetworkScanner",
    "NetworkScannerError",
    "ScanExecutionError",
    "SubnetDetectionError",
]
