import subprocess
import statistics
import time
import socket
from typing import Dict, Any
import asyncio

async def ping_stats(host="8.8.8.8", count=10) -> Dict[str, Any]:
    """Retorna latência média, jitter (desvio padrão) e perda de pacotes."""
    latencies = []
    lost = 0
    async def ping_one():
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", "1", host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            out = stdout.decode()
            if "time=" in out:
                ms = float(out.split("time=")[1].split(" ")[0])
                return ms
        except:
            return None
        return None

    tasks = [ping_one() for _ in range(count)]
    results = await asyncio.gather(*tasks)
    for r in results:
        if r is not None:
            latencies.append(r)
        else:
            lost += 1
    
    avg = statistics.mean(latencies) if latencies else 0
    jitter = statistics.stdev(latencies) if len(latencies) > 1 else 0
    return {"latency": avg, "jitter": jitter, "loss": lost, "samples": len(latencies)}

async def dns_bench(dns1: str, dns2: str = "8.8.8.8", domain: str = "google.com") -> Dict[str, Any]:
    """Compara tempo de resposta do DNS configurado vs Google DNS."""
    async def query(dns):
        start = time.time()
        try:
            loop = asyncio.get_event_loop()
            def udp_query():
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(2.0)
                # DNS Query básica para o domínio
                s.sendto(b"\x00\x00\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00" + domain.encode() + b"\x00\x00\x01\x00\x01", (dns, 53))
                s.recvfrom(512)
            await loop.run_in_executor(None, udp_query)
            return (time.time() - start) * 1000
        except:
            return 999 # Timeout

    t1, t2 = await asyncio.gather(query(dns1), query(dns2))
    return {"dns1": dns1, "dns1_time": t1, "dns2": dns2, "dns2_time": t2}

def hop_analysis(target="8.8.8.8") -> Dict[str, Any]:
    """Executa traceroute e retorna latência do gateway e primeiro salto."""
    try:
        output = subprocess.run(["traceroute", "-n", "-m", "5", target], capture_output=True, text=True, timeout=5)
        lines = output.stdout.splitlines()
        res = {"modem_latency": 0.0, "first_external_latency": 0.0}
        for line in lines:
            if " 1 " in line: # Primeiro salto (Geralmente o Modem/MikroTik)
                parts = line.split()
                if len(parts) > 3: res["modem_latency"] = float(parts[3])
            if " 2 " in line or " 3 " in line: # Saltos externos
                parts = line.split()
                if len(parts) > 3 and "ms" in line:
                    res["first_external_latency"] = float(parts[3])
                    break
        return res
    except:
        return {"modem_latency": 0.0, "first_external_latency": 0.0}