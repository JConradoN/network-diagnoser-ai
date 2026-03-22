# FOX Network Diagnoser AI — Estrutura Completa do Sistema

## Visão Geral
Sistema de diagnóstico e monitoramento de redes, com backend FastAPI, CLI robusta, coleta ARP/SNMP, análise via IA (Gemini), frontend dashboard moderno e integração com dispositivos MikroTik.

---

## Estrutura de Diretórios e Arquivos

- **app.py** — Entrypoint principal CLI. Executa comandos de diagnóstico.
- **api.py** — Backend FastAPI. Expõe endpoints REST para dashboard e integrações.
- **cli.py** — CLI robusta: scan, benchmark, relatórios, interfaces.
- **config.py** — Carrega variáveis de ambiente e define AppConfig.
- **database.py** — Persistência de resultados (SQLite), helpers para relatórios.
- **performance.py** — Funções de ping, jitter, DNS bench, traceroute.
- **network_scanner.py** — (Legacy) Entrypoint alternativo.
- **requirements.txt** — Dependências Python (FastAPI, scapy, pysnmp, etc).
- **Dockerfile, entrypoint.sh, k3s-diagnoser.yaml** — Deploy container/K8s.
- **app/noc/index.html** — Dashboard frontend (Tailwind, Chart.js, Lucide).

### Principais Pastas:
- **analyzer/** — Lógica de análise, heurísticas, integração Gemini.
- **collectors/** — Integrações MikroTik, SNMP, DHCP.
- **output/** — Geração de relatórios (JSON, Markdown).
- **scanner/** — Coleta de dados: ARP, SNMP, DHCP, mDNS, SSDP, portas, latência.
- **services/** — Orquestração da pipeline de diagnóstico.
- **utils/** — Utilitários: logger, lookup MAC, helpers de rede.
- **tests/** — Testes unitários e de integração.

---

## Endpoints REST (api.py)

### 1. Telemetria Rápida
```python
@app.get("/system/metrics")
async def get_system_metrics():
    return {"cpu": ..., "temp": ..., "temp_status": ..., "devices": ...}
```
- **Retorna:** Uso de CPU, temperatura, status térmico, dispositivos ativos.

### 2. Performance e Latência
```python
@app.get("/performance/ping")
async def get_performance_ping():
    return {"latency": ..., "jitter": ..., "loss": ...}
```
- **Retorna:** Latência, jitter, perda de pacotes (via ping_stats).

### 3. Tráfego de Rede
```python
@app.get("/network/traffic")
async def get_network_traffic():
    return {"history": [{"download": Mbps, "upload": Mbps}, ...]}
```
- **Retorna:** Histórico de Mbps (SNMP MikroTik).

### 4. Topologia Física
```python
@app.get("/topology/map")
async def get_topology_map():
    return {"children": [{...}]}
```
- **Retorna:** Hierarquia física (Internet > Modem > MikroTik > portas > dispositivos).

### 5. Diagnóstico e Relatórios
```python
@app.get("/dashboard/stats")
async def get_dashboard_stats():
    return {"stats": {"timestamp": ..., "ai_summary": ...}, "raw_report": ...}
```
- **Retorna:** Último diagnóstico IA, resumo, timestamp, relatório bruto.

### 6. Iniciar Diagnóstico
```python
@app.post("/scan/start")
async def start_scan(config: ScanConfig, background_tasks: BackgroundTasks):
    ...
```
- **Parâmetros:** interface, subnet, módulos.
- **Executa:** Pipeline de diagnóstico em background.

---

## Principais Funções e Fluxos

### ARP Scan (scanner/arp_scanner.py)
- Classe `ARPScanner`: executa ARP scan, retorna lista de dispositivos (IP, MAC, vendor).
- Exemplo:
```python
arp = ARPScanner(subnet="192.168.100.0/24")
devices = arp.scan()
```

### SNMP Scan (scanner/snmp_scanner.py)
- Classe `SNMPScanner`: coleta sysName, sysDescr, sysUpTime, interfaces, RX/TX.
- Exemplo:
```python
snmp = SNMPScanner(ip="192.168.100.1", community="public")
result = await snmp.scan_interfaces()
```

### Diagnóstico (services/diagnosis_service.py)
- Classe `DiagnosisService`: orquestra pipeline (ARP, SNMP, mDNS, SSDP, latência, análise Gemini).
- Função `run()`: executa diagnóstico completo.

### CLI (cli.py)
- Comandos: `interfaces`, `scan`, `report`, `benchmark`.
- Exemplo:
```bash
python cli.py scan --interface eth0 --json-output out.json
```

---

## Frontend (app/noc/index.html)
- Dashboard moderno (Tailwind, Chart.js, Lucide).
- Consome endpoints REST para exibir status, gráficos, topologia.
- IDs importantes: `cpu-val`, `temp-val`, `ping-val`, `devices-val`, `trafficChart`, `ai-report`, `actions-list`.

---

## Exemplos de Uso

### Subir API
```bash
uvicorn api:app --host 0.0.0.0 --port 80
```

### Executar Diagnóstico CLI
```bash
python app.py
```

### Testar Endpoints
```bash
curl http://localhost:80/system/metrics
curl http://localhost:80/performance/ping
curl http://localhost:80/network/traffic
curl http://localhost:80/topology/map
```

---

## Dependências (requirements.txt)
- fastapi, uvicorn, scapy, pysnmp, pydantic, requests, zeroconf, pytest, etc.

---

## Observações
- Variáveis de ambiente configuram subnet, interface, SNMP, etc (ver config.py).
- O sistema é modular: cada scanner pode ser usado isoladamente.
- O backend serve arquivos estáticos do dashboard e API REST na mesma porta.
- O diagnóstico pode ser disparado via API ou CLI.

---

## Para Claude
Este documento descreve toda a arquitetura, endpoints, funções e exemplos do FOX Network Diagnoser AI. Use este contexto para responder dúvidas, sugerir melhorias ou gerar código para novas features.
