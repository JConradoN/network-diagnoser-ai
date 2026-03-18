# Network Diagnoser AI

Projeto base para diagnostico inteligente de redes domesticas e SMB.

## Funcionalidades do scaffold

- ARP scan com fabricante via MAC OUI
- Coleta SNMP (sysName, sysDescr, sysUpTime, interfaces e sinais de roteamento)
- Descoberta mDNS e SSDP
- Classificacao heuristica de dispositivos (router, AP, switch, IoT, impressora)
- Testes de latencia, jitter, perda e DNS
- Deteccao inicial de problemas (DNS, latencia, perda, NAT multiplo, DHCP duplicado, AP em modo incorreto)
- Integracao opcional com Gemini API
- Geracao de relatorio JSON final

## Estrutura

```text
scanner/
analyzer/
utils/
output/
app.py
config.py
requirements.txt
PRD_Network_Diagnoser_AI.md
```

## Requisitos

- Python 3.10+
- Dependencias em requirements.txt

## Instalacao

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Execucao

```bash
python app.py
```

A execucao sem argumentos roda o comando scan por padrao.

## CLI robusta

Listar interfaces:

```bash
python cli.py interfaces
```

Executar scan completo e gerar relatorios JSON + Markdown:

```bash
python cli.py scan --interface wlan0 --json-output network_report.json --md-output network_report.md
```

Executar scan com ferramentas selecionadas:

```bash
python cli.py scan --disable-snmp --disable-mdns --disable-ssdp --disable-port-scan
```

Ler relatorio salvo com filtros:

```bash
python cli.py report --path network_report.json --severity high --device-ip 192.168.0.10
```

Benchmark ARP via CLI:

```bash
python cli.py benchmark --subnet 192.168.0.0/24 --interface eth0 --threshold 10
```

## Testes

Executar testes unitarios:

```bash
python3 -m pytest -q
```

## Benchmark de performance (RNF04)

Medir tempo de ARP scan na sub-rede alvo e comparar com limite de 10s:

```bash
python scripts/benchmark_arp_scan.py --subnet 192.168.0.0/24 --threshold 10 --interface eth0
```

O script retorna JSON com elapsed_seconds e passes_threshold.

## API REST (opcional)

Suba a API com uvicorn:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Se a API for iniciada dentro de uma sessao SSH, ela fica presa ao terminal atual. Para manter o processo vivo apos fechar a conexao, use `tmux`, `screen`, `nohup` ou um servico `systemd`.

Exemplo simples com `nohup`:

```bash
nohup uvicorn api:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &
```

Se aparecer algo como `client_loop: send disconnect: Connection reset`, isso normalmente indica que a sessao SSH caiu ou foi encerrada. Nessa situacao, um processo iniciado em foreground costuma parar junto com a sessao.

Endpoints principais:

- GET /health
- GET /interfaces
- POST /scan
- POST /scan/save
- GET /report/latest

Exemplo de filtro de findings:

```bash
curl "http://localhost:8000/report/latest?severity=high&device_ip=192.168.0.10"
```

Listar interfaces disponiveis antes do scan:

```bash
curl "http://localhost:8000/interfaces"
```



## Variaveis de ambiente

- ND_SUBNET: sub-rede em CIDR (ex: 192.168.0.0/24)
- ND_INTERFACE: interface de rede para scan (ex: eth0, wlan0)
- ND_SNMP_COMMUNITY: community SNMP (padrao: public)
- ND_SNMP_TIMEOUT: timeout SNMP em segundos
- ND_SNMP_ENABLED: habilita coleta SNMP (true/false)
- ND_PING_COUNT: quantidade de pings por host
- ND_LATENCY_ENABLED: habilita testes de latencia/jitter (true/false)
- ND_DNS_TEST_DOMAIN: dominio para teste DNS
- ND_DNS_ENABLED: habilita teste DNS (true/false)
- ND_TRACEROUTE_TARGET: alvo para inferencia de NAT multiplo
- ND_ROUTE_ENABLED: habilita analise de rota (true/false)
- ND_DHCP_DISCOVERY_TIMEOUT: tempo de escuta para ofertas DHCP
- ND_DHCP_ENABLED: habilita detector DHCP (true/false)
- ND_MDNS_ENABLED: habilita descoberta mDNS (true/false)
- ND_SSDP_ENABLED: habilita descoberta SSDP (true/false)
- ND_PORT_SCAN_ENABLED: habilita scan de portas (true/false)
- ND_PORT_SCAN_PORTS: lista CSV de portas para nmap
- ND_EXPECTED_ACTIVE_HOSTS: estimativa de hosts ativos para avaliar CA01 (90%)
- ND_API_CORS_ORIGINS: lista CSV de origens permitidas no CORS da API (ex: http://192.168.100.41:5173,http://192.168.100.41:5174)
- GEMINI_API_KEY: chave da API Gemini (opcional)
- GEMINI_MODEL: modelo Gemini (padrao: gemini-1.5-flash)

Exemplo de uso com interface especifica:

```bash
export ND_INTERFACE="wlan0"
python app.py
```

### Como configurar a chave Gemini

Linux/macOS (sessao atual):

```bash
export GEMINI_API_KEY="SUA_CHAVE_AQUI"
```

Linux/macOS (persistente em shell):

```bash
echo 'export GEMINI_API_KEY="SUA_CHAVE_AQUI"' >> ~/.bashrc
source ~/.bashrc
```

Windows PowerShell (sessao atual):

```powershell
$env:GEMINI_API_KEY="SUA_CHAVE_AQUI"
```

Windows PowerShell (persistente):

```powershell
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY","SUA_CHAVE_AQUI","User")
```

## Observacoes

- ARP scan pode exigir privilegios elevados.
- Em Linux, voce pode liberar ARP sem rodar tudo como root aplicando capacidades ao binario real do Python, por exemplo com `sudo setcap cap_net_raw,cap_net_admin+eip /usr/bin/python3.12`.
- Em alguns ambientes, nmap e SNMP podem depender de instalacao adicional no sistema operacional.
- O relatorio final inclui prd_acceptance com status dos criterios CA01-CA05.