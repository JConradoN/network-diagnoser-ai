# Instruções de Migração — fox-server

> **Documento gerado em:** 2026-03-25
> **Objetivo:** Migrar todos os serviços do fox-dev para o fox-server recém-formatado, assumindo o IP 192.168.88.200 e o papel de servidor principal da rede doméstica FOX.

---

## 1. Contexto da Rede

| Campo | Valor |
|---|---|
| Roteador | MikroTik (RouterOS v6) — 192.168.88.1 |
| DNS local | MikroTik com static entries |
| LAN | 192.168.88.0/24 |
| IPs reservados | .200 em diante (fixos/estáticos) |
| Dual-WAN | Vivo PPPoE (principal) + NIO DHCP (load balance / failover) |
| Mesh Wi-Fi | 3x Intelbras Twibi Force AX (.210, .211, .212) |
| Credential MikroTik | admin / `JC@mct21` (full) · homemonitor / (vazio) (read-only, porta 8728) |

### Dispositivos fixos da rede

| Nome | IP | MAC |
|---|---|---|
| fox-dev *(a desligar)* | 192.168.88.200 | 24:F5:AA:55:87:F7 |
| fox-server *(este)* | 192.168.88.202 → **migrar para .200** | D8:5E:D3:F3:B4:8F |
| fox-note | 192.168.88.201 | 60:C7:27:09:A7:E9 |
| emilia-pc-eth | 192.168.88.220 | D0:94:66:AD:A6:DC |
| twibi-principal | 192.168.88.210 | 98:2A:0A:CB:C4:9D |
| twibi-quintal | 192.168.88.211 | 98:2A:0A:CB:C4:4D |
| twibi-sala | 192.168.88.212 | 30:E1:F1:8D:10:8B |
| epson | 192.168.88.230 | 38:9D:92:06:46:3A |
| lg-tv | 192.168.88.240 | 78:DD:12:73:B0:82 |
| ps5 | 192.168.88.241 | 00:E4:21:57:31:04 |
| alexa | 192.168.88.242 | 08:C2:24:E0:E9:8F |

---

## 2. Hardware do fox-server

| Componente | Especificação |
|---|---|
| CPU | Intel Core i5 (geração recente) |
| RAM | 32 GB DDR4 2666 MHz |
| GPU | NVIDIA GeForce RTX 3060 12 GB VRAM |
| Armazenamento | 1 TB M.2 NVMe Kingston |
| SO | Ubuntu 24.04 LTS (Server + desktop opcional) |
| Driver NVIDIA | 570.211.01 |
| CUDA | 12.8 |
| Interface de rede | `enp3s0` — MAC D8:5E:D3:F3:B4:8F |

**Propósito principal:** Rodar LLMs locais via Ollama com aceleração GPU, e hospedar todos os serviços da rede doméstica.

---

## 3. O que existe no fox-dev hoje (a migrar)

### 3.1 FOX NOC — Network Scanner / Diagnoser AI

- **Localização:** `/opt/network-scanner/`
- **Stack:** FastAPI (Python) + Uvicorn + SQLite
- **Frontend:** `/opt/network-scanner/app/noc/index.html` (dashboard NOC)
- **Porta:** 80 (hostNetwork)
- **Como roda hoje:** k3s (Kubernetes single-node), Deployment `network-diagnoser`, hostNetwork=true
- **Como migrar:** Docker Compose (mais simples, sem overhead k3s)
- **Depende de:** nmap, traceroute, NET_RAW, NET_ADMIN (capabilities), acesso à rede física

#### Variáveis de ambiente (.env)
```
TWIBI_USER=admin
TWIBI_HOST_PRINCIPAL=192.168.88.210
TWIBI_HOST_C44D=192.168.88.211
TWIBI_HOST_108B=192.168.88.212
ND_MIKROTIK_HOST=192.168.88.1
ND_MIKROTIK_USER=homemonitor
ND_SNMP_COMMUNITY=public
ND_INTERFACE=enp3s0          # ← ATUALIZAR para interface do fox-server
ND_EXPECTED_ACTIVE_HOSTS=30
ND_DNS_TEST_DOMAIN=google.com
ND_PORT_SCAN_ENABLED=true
ND_PORT_SCAN_PORTS=22,53,67,68,80,443
GEMINI_API_KEY=              # ← preencher com a chave atual (ver .env no fox-dev)
```

> **IMPORTANTE:** A `GEMINI_API_KEY` é lida em tempo de execução de `/app/.env` pelo `diagnosis_service.py`. Não codificar no Dockerfile nem no Compose.

#### Dockerfile (já existe em /opt/network-scanner/Dockerfile)
Base: `python:3.12-slim`. Instala: nmap, iputils-ping, iproute2, traceroute, libpcap-dev, snmp, curl.

#### Docker Compose a criar (novo — não existe ainda)
```yaml
services:
  noc:
    build: .
    container_name: fox-noc
    network_mode: host
    privileged: true
    cap_add:
      - NET_RAW
      - NET_ADMIN
    volumes:
      - /opt/network-scanner:/app
    restart: unless-stopped
    environment:
      - PYTHONUNBUFFERED=1
      - PYTHONDONTWRITEBYTECODE=1
```

### 3.2 home-net-monitor

- **Localização no fox-dev:** `/home/conrado/projects/home-net-monitor/`
- **Repositório:** https://github.com/JConradoN/home-net-monitor
- **Porta:** 8080
- **Como roda:** systemd service `home-net-monitor.service`
- **Usuário:** conrado
- **Config:** `config.json` (ver abaixo)

#### config.json
```json
{
    "host": "0.0.0.0",
    "port": 8080,
    "db_path": "data/home_net_monitor.db",
    "icmp_interval": 30,
    "dns_interval": 60,
    "snmp_interval": 60,
    "fingerprint_interval": 300,
    "snmp_host": null,
    "snmp_community": "public",
    "log_level": "INFO",
    "thresholds": {
        "gw_latency_high": 50,
        "internet_latency_high": 150,
        "dns_slow": 100,
        "dns_fast": 30,
        "cpu_critical": 80,
        "cpu_duration": 60,
        "channel_util": 70,
        "retries": 15,
        "noise_floor": -75,
        "bufferbloat_delta": 30,
        "outage_duration": 30
    }
}
```

#### home-net-monitor.service
```ini
[Unit]
Description=Home Net Monitor — Diagnóstico de rede doméstica
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=conrado
WorkingDirectory=/home/conrado/projects/home-net-monitor
ExecStart=/home/conrado/projects/home-net-monitor/.venv/bin/python main.py --config /home/conrado/projects/home-net-monitor/config.json
Restart=on-failure
RestartSec=10
CPUQuota=20%
MemoryMax=256M

[Install]
WantedBy=multi-user.target
```

### 3.3 rsyslog — Logs dos Twibis

Os Twibis (192.168.88.210/211/212) enviam syslog UDP para o servidor na porta 514.

#### /etc/rsyslog.d/10-twibi.conf
```
module(load="imudp")
input(type="imudp" port="514")

if $fromhost-ip startswith "192.168.88." then {
  action(type="omfile" file="/var/log/twibi/all.log")
  stop
}
```

**Após instalar:** criar o diretório e ajustar permissões:
```bash
sudo mkdir -p /var/log/twibi
sudo chown syslog:syslog /var/log/twibi
sudo systemctl restart rsyslog
```

**Após migrar:** atualizar o IP de destino do syslog em cada Twibi (interface web) de 192.168.88.200 (fox-dev) para 192.168.88.200 (fox-server — mesmo IP após migração, não precisa mudar se o IP for mantido).

### 3.4 Ollama (já instalado no fox-server)

- Rodar com aceleração GPU (RTX 3060 12GB VRAM)
- Verificar se o serviço Ollama está usando GPU: `ollama ps` e `nvidia-smi`
- Instalar Open WebUI via Docker para interface web:
```bash
docker run -d --network=host \
  --gpus all \
  -v open-webui:/app/backend/data \
  --name open-webui \
  --restart unless-stopped \
  ghcr.io/open-webui/open-webui:cuda
```

---

## 4. Plano de Migração — Passo a Passo

### Fase 1 — Instalar o fox-server do zero

```bash
# 1. Ubuntu 24.04 Server (ou Desktop se quiser jogar)
# Durante instalação: usuário conrado, hostname fox-server

# 2. Pós-instalação básica
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget htop net-tools rsyslog

# 3. NVIDIA drivers (se não instalados pelo Ubuntu)
sudo ubuntu-drivers install
# OU
sudo apt install -y nvidia-driver-570

# 4. Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker conrado
# (fazer logout e login)

# 5. Verificar GPU + CUDA
nvidia-smi

# 6. NVIDIA Container Toolkit (para Docker usar GPU)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 7. Ollama (se não instalado)
curl -fsSL https://ollama.com/install.sh | sh
# Verificar GPU
ollama run llama3.2 "olá"   # deve usar GPU
```

### Fase 2 — Migrar FOX NOC

```bash
# No fox-dev: copiar /opt/network-scanner para fox-server
sudo rsync -av /opt/network-scanner/ conrado@192.168.88.202:/opt/network-scanner/

# No fox-server:
sudo chown -R conrado:conrado /opt/network-scanner

# Criar docker-compose.yml em /opt/network-scanner/
# (conteúdo descrito na seção 3.1)

# Ajustar .env: trocar ND_INTERFACE=enp2s0 → enp3s0
nano /opt/network-scanner/.env

# Buildar e subir
cd /opt/network-scanner
docker compose build
docker compose up -d

# Verificar
curl http://localhost/system/metrics
```

### Fase 3 — Migrar home-net-monitor

```bash
# Clonar repositório
cd /home/conrado/projects
git clone https://github.com/JConradoN/home-net-monitor

# Criar venv e instalar dependências
cd home-net-monitor
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Criar config.json (conteúdo da seção 3.2)
# Criar o serviço systemd (conteúdo da seção 3.2)
sudo nano /etc/systemd/system/home-net-monitor.service
sudo systemctl daemon-reload
sudo systemctl enable --now home-net-monitor
```

### Fase 4 — Configurar rsyslog para Twibis

```bash
sudo nano /etc/rsyslog.d/10-twibi.conf
# (conteúdo da seção 3.3)

sudo mkdir -p /var/log/twibi
sudo chown syslog:syslog /var/log/twibi
sudo systemctl restart rsyslog

# Testar recebimento
tail -f /var/log/twibi/all.log
```

### Fase 5 — Atualizar MikroTik (trocar IPs)

Rodar no terminal MikroTik (WinBox ou SSH para 192.168.88.1, user admin):

```routeros
# 1. Remover lease estático do fox-dev (.200) e do fox-server (.202)
/ip dhcp-server lease print
# anotar os numbers dos dois e remover:
/ip dhcp-server lease remove numbers=X,Y

# 2. Adicionar fox-server no .200
/ip dhcp-server lease add address=192.168.88.200 mac-address=D8:5E:D3:F3:B4:8F comment="fox-server"

# 3. Atualizar DNS estático
/ip dns static remove [find name=fox-dev]
/ip dns static set [find name=fox-server] address=192.168.88.200

# 4. Verificar NAT (porta 80 deve apontar para 192.168.88.200)
/ip firewall nat print
# Se tiver regra de port-forward para fox-dev, atualizar para 192.168.88.200
```

### Fase 6 — Renovar IP no fox-server

Após configurar o MikroTik, renovar o IP no fox-server:

```bash
sudo nmcli device disconnect enp3s0 && sudo nmcli device connect enp3s0
ip addr show enp3s0   # deve mostrar 192.168.88.200
```

### Fase 7 — Verificar tudo e desligar fox-dev

```bash
# No fox-server — checar todos os serviços
curl http://localhost/system/metrics          # FOX NOC API
curl http://localhost:8080                    # home-net-monitor
docker ps                                     # containers rodando
systemctl is-active home-net-monitor
systemctl is-active rsyslog
ollama ps                                     # modelos carregados

# Verificar NOC no browser: http://192.168.88.200
```

```routeros
# No MikroTik — remover entradas do fox-dev
/ip dhcp-server lease remove [find comment="fox-dev"]
/ip dns static remove [find name=fox-dev]
```

```bash
# No fox-dev — desligar
sudo shutdown -h now
```

---

## 5. O que NÃO migrar

| Item | Motivo |
|---|---|
| k3s | Substituído por Docker Compose — mais simples |
| n8n | Descontinuado por ora — futuro: LangChain + LangGraph |
| thermal-fan-control | Específico do Samsung 270E5G (fox-dev) |
| fox-noc.tar | Arquivo temporário, já deletado |

---

## 6. Portas e Serviços no fox-server após migração

| Serviço | Porta | Protocolo |
|---|---|---|
| FOX NOC (dashboard + API) | 80 | HTTP |
| home-net-monitor | 8080 | HTTP |
| Ollama API | 11434 | HTTP |
| Open WebUI | 3000 | HTTP |
| rsyslog Twibi | 514 | UDP |

---

## 7. Observações Importantes

- O `diagnosis_service.py` lê a `GEMINI_API_KEY` diretamente do arquivo `.env` em tempo de execução (não na inicialização). Isso foi feito para suportar troca de chave sem reiniciar o serviço.
- O Twibi Principal (SER L1) estava travando por conta de um dispositivo com MAC randomizado (B2:A6:11:1D:9A:22) que foi bloqueado no MikroTik. Monitorar se o problema voltou.
- Os Twibis estão logando em nível DEBUG no rsyslog. Após estabilização, subir o nível para Critical/Emergency.
- O fox-dev (Samsung 270E5G) tinha problema de cooler não girando automaticamente. Foi resolvido com um serviço `thermal-fan-control` — não relevante para o fox-server.
- A rede tem dois dispositivos com MAC randomizado bloqueados no MikroTik (.103 e .109) — nunca identificados.
