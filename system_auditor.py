import subprocess
import requests
import json
import os
import asyncio
import sys
from datetime import datetime

# Novo nome de arquivo para evitar conflitos de cache
LOG_FILE = "debug_report_final.log"
API_URL = "http://localhost:8181"
PYTHON_EXEC = "/opt/network-scanner/.venv/bin/python3"

def log_to_file(title, content):
    timestamp = datetime.now().strftime('%H:%M:%S')
    divider = "\n" + "="*50 + "\n"
    header = f"{divider}📡 [{timestamp}] {title}\n{divider}\n"
    
    # Exibe no terminal para garantir que você veja o dado
    print(f"写入 (Writing): {title}...")
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(header + content + "\n")
            f.flush()
    except Exception as e:
        print(f"❌ Erro ao escrever no log: {e}")

async def run_internal_tests():
    # 1. Teste de Banco de Dados
    try:
        import database
        res = database.get_last_scan()
        log_to_file("DATABASE: get_last_scan", json.dumps(res, indent=2, ensure_ascii=False))
    except Exception as e:
        log_to_file("DATABASE ERROR", str(e))

    # 2. Teste de Performance
    try:
        from performance import ping_stats
        res = await ping_stats("8.8.8.8", count=2)
        log_to_file("PERFORMANCE: ping_stats", json.dumps(res, indent=2))
    except Exception as e:
        log_to_file("PERFORMANCE ERROR", str(e))

    # 3. Teste de Topologia / SNMP
    try:
        from analyzer.topology_builder import TopologyBuilder
        # Testando apenas se a classe instancia e o módulo carrega
        log_to_file("MODULE CHECK: TopologyBuilder", "Carregado com sucesso.")
    except Exception as e:
        log_to_file("TOPOLOGY MODULE ERROR", str(e))

def run_cli(cmd, label):
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = "."
        result = subprocess.run([PYTHON_EXEC] + cmd, capture_output=True, text=True, timeout=40, env=env)
        out = result.stdout if result.returncode == 0 else f"ERR: {result.stderr}"
        log_to_file(f"CLI: {label}", out)
    except Exception as e:
        log_to_file(f"CLI ERROR: {label}", str(e))

async def main():
    # Não usamos mode="w" aqui para não apagar nada
    log_to_file("INÍCIO DA AUDITORIA", f"Iniciando em {datetime.now()}")

    # Executa os testes
    run_cli(["cli.py", "interfaces"], "Interfaces")
    await run_internal_tests()
    run_cli(["verify_core.py"], "Verify Core (Gemini)")
    
    # Teste de API (Se o serviço estiver rodando)
    try:
        r = requests.get(f"{API_URL}/network/performance", timeout=5)
        log_to_file("API: /network/performance", json.dumps(r.json(), indent=2))
    except Exception as e:
        log_to_file("API OFFLINE", "Servidor na 8181 não respondeu.")

    print(f"\n✅ FIM. Verifique o arquivo: {LOG_FILE}")

if __name__ == "__main__":
    asyncio.run(main())