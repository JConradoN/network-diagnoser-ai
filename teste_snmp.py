import asyncio
from pysnmp.hlapi.v3arch.asyncio import get_cmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity

async def run_test():
    snmp_engine = SnmpEngine()
    
    try:
        # Criando o transporte
        transport = await UdpTransportTarget.create(('192.168.88.1', 161))
        
        # Na v7, get_cmd é uma corrotina: usamos await diretamente
        # Ela retorna uma tupla (errorIndication, errorStatus, errorIndex, varBinds)
        result = await get_cmd(
            snmp_engine,
            CommunityData('public', mpModel=0),
            transport,
            ContextData(),
            ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0'))
        )

        errorIndication, errorStatus, errorIndex, varBinds = result

        if errorIndication:
            print(f"Erro de Rede: {errorIndication}")
        elif errorStatus:
            print(f"Erro SNMP: {errorStatus.prettyPrint()} em {errorIndex}")
        else:
            for varBind in varBinds:
                print(f"SUCESSO TOTAL! Resposta do MikroTik: {varBind.prettyPrint()}")
    
    finally:
        # Garante que o motor seja fechado mesmo se houver erro
        snmp_engine.transport_dispatcher.close_dispatcher()

if __name__ == "__main__":
    print("Iniciando teste SNMP v7 (Async Await Pattern)...")
    asyncio.run(run_test())