"""ARP scanner implementation."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import ipaddress
from typing import Optional

from utils.logger import get_logger
from utils.mac_lookup import lookup_vendor
from utils.network_utils import detect_local_subnet, sort_ip_strings

try:
    from scapy.all import ARP, Ether, get_if_addr, srp
    from scapy.error import Scapy_Exception
except ImportError:  # pragma: no cover
    ARP = Ether = get_if_addr = srp = None

    class Scapy_Exception(Exception):
        """Fallback exception when scapy is not installed."""


class ARPScannerError(Exception):
    """Base exception for ARP scanner errors."""


class ARPScannerDependencyError(ARPScannerError):
    """Raised when scapy dependency is missing."""


class ARPScannerExecutionError(ARPScannerError):
    """Raised when ARP scan fails."""


@dataclass(frozen=True)
class Device:
    """Represents a discovered network device."""

    ip: str
    mac: str
    vendor: str

    def to_dict(self) -> dict:
        """Serialize device object to dictionary."""
        return asdict(self)


class ARPScanner:
    """Run ARP scans against a local subnet."""

    def __init__(
        self,
        subnet: Optional[str] = None,
        timeout: int = 2,
        retry: int = 1,
        iface: Optional[str] = None,
    ) -> None:
        self.subnet = subnet
        self.timeout = timeout
        self.retry = retry
        self.iface = iface
        self.logger = get_logger(self.__class__.__name__)

    def scan(self) -> list[Device]:
        """Execute ARP scan and return discovered devices."""
        if ARP is None or Ether is None or srp is None:
            raise ARPScannerDependencyError(
                "Dependencia ausente: instale scapy com 'pip install scapy'."
            )

        target_subnet = self.subnet or self._detect_target_subnet()
        self.logger.info("Iniciando ARP scan em %s (iface=%s)", target_subnet, self.iface or "default")

        packet = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=target_subnet)

        try:
            srp_kwargs = {
                "timeout": self.timeout,
                "retry": self.retry,
                "verbose": False,
            }
            if self.iface:
                srp_kwargs["iface"] = self.iface

            answered, _ = srp(
                packet,
                **srp_kwargs,
            )
        except PermissionError as exc:
            raise ARPScannerExecutionError(
                "Permissao negada para ARP scan. Execute com privilegios elevados."
            ) from exc
        except (Scapy_Exception, OSError) as exc:
            raise ARPScannerExecutionError(f"Falha durante ARP scan: {exc}") from exc

        unique_by_ip: dict[str, Device] = {}
        for _, received in answered:
            ip_address = getattr(received, "psrc", "")
            mac_address = getattr(received, "hwsrc", "")
            if not ip_address or not mac_address:
                continue

            vendor = lookup_vendor(mac_address)
            if isinstance(vendor, tuple):
                vendor = vendor[1] if len(vendor) > 1 else vendor[0]
            unique_by_ip[ip_address] = Device(
                ip=ip_address,
                mac=mac_address,
                vendor=vendor,
            )

        devices = [unique_by_ip[ip] for ip in sort_ip_strings(list(unique_by_ip.keys()))]
        self.logger.info("ARP scan finalizado com %d dispositivos", len(devices))
        return devices

    def _detect_target_subnet(self) -> str:
        """Detect target subnet, preferring explicit interface when provided."""
        if self.iface and get_if_addr is not None:
            try:
                interface_ip = get_if_addr(self.iface)
                network = ipaddress.ip_network(f"{interface_ip}/24", strict=False)
                return str(network)
            except Exception:
                self.logger.warning(
                    "Nao foi possivel detectar sub-rede da interface %s; usando rota padrao.",
                    self.iface,
                )

        return detect_local_subnet()
