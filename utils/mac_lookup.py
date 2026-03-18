"""MAC vendor lookup helper."""

from __future__ import annotations

try:
    from scapy.all import conf
except ImportError:  # pragma: no cover
    conf = None


def lookup_vendor(mac_address: str) -> str:
    """Return vendor name for a MAC address using scapy manuf database."""
    if conf is None or getattr(conf, "manufdb", None) is None:
        return "Unknown"

    manufdb = conf.manufdb
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
