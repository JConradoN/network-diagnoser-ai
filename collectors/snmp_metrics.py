
import asyncio
from pysnmp.hlapi.v3arch.asyncio import get_cmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity

def format_uptime(seconds: int) -> str:
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    parts = []
    if days:
        parts.append(f"{days} dias")
    if hours:
        parts.append(f"{hours} horas")
    if minutes:
        parts.append(f"{minutes} min")
    if secs or not parts:
        parts.append(f"{secs} seg")
    return ', '.join(parts)

OID_CPU = '1.3.6.1.2.1.25.3.3.1.2.1'
OID_UPTIME = '1.3.6.1.2.1.1.3.0'
OID_MEM_FREE = '1.3.6.1.2.1.25.2.3.1.6.65536'
OID_TEMP = '1.3.6.1.4.1.14988.1.1.3.10.0'
OID_VOLTAGE = '1.3.6.1.4.1.14988.1.1.3.8.0'

async def get_mikrotik_health(host, community='public', port=161):
    oids = [OID_CPU, OID_UPTIME, OID_MEM_FREE, OID_TEMP, OID_VOLTAGE]
    results = {}

    try:
        transport = await UdpTransportTarget.create((host, port))
        for oid in oids:
            try:
                errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
                    SnmpEngine(),
                    CommunityData(community, mpModel=0),
                    transport,
                    ContextData(),
                    ObjectType(ObjectIdentity(oid))
                )
                if errorIndication:
                    results[oid] = f"SNMP error: {errorIndication}"
                elif errorStatus:
                    results[oid] = f"SNMP error: {errorStatus.prettyPrint()} at {errorIndex}"
                else:
                    for name, val in varBinds:
                        try:
                            results[str(name)] = int(val)
                        except Exception:
                            results[str(name)] = str(val)
            except Exception as exc:
                results[oid] = f"Exception: {exc}"
    except Exception as exc:
        return {
            'snmp_error': f"Timeout ou erro de transporte: {exc}",
            'cpu_usage': None,
            'uptime': None,
            'uptime_str': None,
            'mem_free': None,
            'temperature': None,
            'voltage': None,
        }

    # Verifica se todos os OIDs falharam (SNMP indisponível)
    all_errors = all(isinstance(v, str) for v in results.values())
    if all_errors:
        first_err = next(iter(results.values()), "SNMP indisponível")
        return {
            'snmp_error': str(first_err),
            'cpu_usage': None,
            'uptime': None,
            'uptime_str': None,
            'mem_free': None,
            'temperature': None,
            'voltage': None,
        }

    # Ajuste do uptime: timeticks (centésimos de segundo) para segundos e string formatada
    raw_uptime = results.get(OID_UPTIME)
    uptime_seconds = None
    uptime_str = None
    if isinstance(raw_uptime, int):
        uptime_seconds = raw_uptime // 100
        uptime_str = format_uptime(uptime_seconds)
    elif raw_uptime is not None and not isinstance(raw_uptime, str):
        uptime_str = str(raw_uptime)

    # Temperatura e voltagem
    temp_raw = results.get(OID_TEMP)
    voltage_raw = results.get(OID_VOLTAGE)
    temperature = None
    voltage = None
    try:
        if isinstance(temp_raw, int):
            temperature = temp_raw / 10
        elif temp_raw is not None and not isinstance(temp_raw, str):
            temperature = float(temp_raw) / 10
    except Exception:
        pass
    try:
        if isinstance(voltage_raw, int):
            voltage = voltage_raw / 10
        elif voltage_raw is not None and not isinstance(voltage_raw, str):
            voltage = float(voltage_raw) / 10
    except Exception:
        pass

    cpu_raw = results.get(OID_CPU)
    cpu_val = cpu_raw if isinstance(cpu_raw, int) else None
    mem_raw = results.get(OID_MEM_FREE)
    mem_val = mem_raw if isinstance(mem_raw, int) else None

    return {
        'cpu_usage': cpu_val,
        'uptime': uptime_seconds,
        'uptime_str': uptime_str,
        'mem_free': mem_val,
        'temperature': temperature,
        'voltage': voltage,
    }
