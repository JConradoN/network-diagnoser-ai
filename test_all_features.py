import subprocess
import requests
import json
import os
from datetime import datetime

RESULTS_MD = "test_results.md"
API_URL = "http://localhost:8000"


def write_section(title, content):
    with open(RESULTS_MD, "a", encoding="utf-8") as f:
        f.write(f"\n## {title}\n\n")
        f.write(content)
        f.write("\n---\n")


def run_cli_command(cmd, section):
    try:
        # Timeout padrão: 30s, mas para scan aumentamos para 120s
        timeout = 120 if section == "CLI: scan" else 30
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        output = result.stdout.strip() or result.stderr.strip()
        write_section(section, "---")
        write_section(section, output)
        write_section(section, "---")
    except Exception as e:
        write_section(section, f"Erro: {e}")


def call_api(endpoint, method="GET", data=None, section=None):
    url = f"{API_URL}{endpoint}"
    try:
        if method == "GET":
            resp = requests.get(url)
        else:
            resp = requests.post(url, json=data)
        content = json.dumps(resp.json(), ensure_ascii=False, indent=2)
        write_section(section or endpoint, "---")
        write_section(section or endpoint, content)
        write_section(section or endpoint, "---")
    except Exception as e:
        write_section(section or endpoint, f"Erro: {e}")


def main():
    # Limpa arquivo de resultados
    with open(RESULTS_MD, "w", encoding="utf-8") as f:
        f.write(f"# Teste Completo — Network Diagnoser AI\n\nData: {datetime.now()}\n\n---\n")

    # CLI
    run_cli_command(["python3", "cli.py", "interfaces"], "CLI: interfaces")
    # Usar interface e subnet válidas detectadas
    run_cli_command(["python3", "cli.py", "scan", "--subnet", "192.168.88.0/24", "--interface", "wlp1s0", "--json-output", "network_report.json", "--md-output", "network_report.md", "--print-json"], "CLI: scan")
    # Report sem filter_findings
    run_cli_command(["python3", "cli.py", "report", "--path", "network_report.json"], "CLI: report")
    # Benchmark com interface válida
    run_cli_command(["python3", "cli.py", "benchmark", "--subnet", "192.168.88.0/24", "--interface", "wlp1s0", "--threshold", "10"], "CLI: benchmark")

    # API
    call_api("/network/interfaces", section="API: /network/interfaces")
    call_api("/scan/start", method="POST", data={"interface": "wlp1s0", "subnet": "192.168.88.0/24", "expected_hosts": 10}, section="API: /scan/start")
    call_api("/network/topology", section="API: /network/topology")
    call_api("/network/performance", section="API: /network/performance")
    call_api("/dashboard/stats", section="API: /dashboard/stats")
    # PDF endpoint (deve existir relatório)
    try:
        resp = requests.get(f"{API_URL}/network/report/pdf")
        if resp.status_code == 200:
            write_section("API: /network/report/pdf", "PDF gerado com sucesso.")
        else:
            write_section("API: /network/report/pdf", f"Status: {resp.status_code} — {resp.text}")
    except Exception as e:
        write_section("API: /network/report/pdf", f"Erro: {e}")

    # Teste de integração Gemini (diagnóstico AI)
    run_cli_command(["python3", "verify_core.py"], "Sanity Check: verify_core.py")

    # Teste de banco de dados
    try:
        import database
        last_scan = database.get_last_scan()
        write_section("Banco de Dados: get_last_scan", "---")
        write_section("Banco de Dados: get_last_scan", json.dumps(last_scan, ensure_ascii=False, indent=2))
        write_section("Banco de Dados: get_last_scan", "---")
    except Exception as e:
        write_section("Banco de Dados: get_last_scan", f"Erro: {e}")

    # Teste de performance
    try:
        from performance import ping_stats, dns_bench
        import asyncio
        async def run_perf_tests():
            perf = await ping_stats("8.8.8.8", count=3)
            dns = await dns_bench("192.168.88.1", "8.8.8.8")
            return perf, dns
        perf, dns = asyncio.run(run_perf_tests())
        write_section("Performance: ping_stats", "---")
        write_section("Performance: ping_stats", json.dumps(perf, ensure_ascii=False, indent=2))
        write_section("Performance: ping_stats", "---")
        write_section("Performance: dns_bench", "---")
        write_section("Performance: dns_bench", json.dumps(dns, ensure_ascii=False, indent=2))
        write_section("Performance: dns_bench", "---")
    except Exception as e:
        write_section("Performance", f"Erro: {e}")

    # Chamada ao endpoint Gemini (diagnóstico AI)
    try:
        resp = requests.get(f"{API_URL}/dashboard/stats")
        if resp.status_code == 200:
            content = json.dumps(resp.json(), ensure_ascii=False, indent=2)
            write_section("API: /dashboard/stats (Gemini)", "---")
            write_section("API: /dashboard/stats (Gemini)", content)
            write_section("API: /dashboard/stats (Gemini)", "---")
        else:
            write_section("API: /dashboard/stats (Gemini)", f"Status: {resp.status_code} — {resp.text}")
    except Exception as e:
        write_section("API: /dashboard/stats (Gemini)", f"Erro: {e}")

    print(f"\nTeste completo finalizado. Veja o arquivo {RESULTS_MD} para os resultados.")

if __name__ == "__main__":
    main()
