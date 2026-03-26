
# Guia de Instalação — Network Diagnoser AI


## 1. Pré-requisitos
- Python 3.12+
- Linux recomendado (funciona em Mac, parcial no Windows)
- Acesso root/sudo para instalar dependências de sistema (ex: scapy, nmap)
- Para recursos de WiFi mesh e qualidade de rede: acesso aos APs Twibi (endereços IP e credenciais)

## 2. Dependências do sistema
Instale os pacotes necessários:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip nmap net-tools lsof
```

## 3. Clone o repositório

```bash
git clone <URL_DO_REPOSITORIO>
cd network-scanner
```

## 4. Crie e ative o ambiente virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 5. Instale as dependências Python

```bash
pip install -r requirements.txt
```


## 6. Configure as variáveis de ambiente

Copie o exemplo:
```bash
cp .env.example .env
```
Edite o arquivo `.env` conforme sua rede e necessidades.

Principais variáveis:
- `ND_SUBNET` — Sub-rede a ser escaneada (ex: 192.168.88.0/24)
- `ND_INTERFACE` — Interface de rede (ex: wlan0)
- `GEMINI_API_KEY` — Chave da API Gemini para diagnóstico IA
- `TWIBI_HOST_PRINCIPAL`, `TWIBI_HOST_C44D`, `TWIBI_HOST_108B` — IPs dos APs Twibi
- `TWIBI_USER`, `TWIBI_PASS` — Usuário e senha dos APs Twibi
- `ND_MIKROTIK_HOST` — IP do MikroTik principal

Exemplo de export manual:
```bash
export ND_SUBNET="192.168.88.0/24"
export ND_INTERFACE="wlan0"
export GEMINI_API_KEY="sua-chave"
export TWIBI_HOST_PRINCIPAL="192.168.88.210"
export TWIBI_USER="admin"
export TWIBI_PASS="senha"
# ... demais variáveis
```

## 7. Teste a instalação

```bash
python app.py --help
```

Se aparecer o menu de comandos, está pronto para uso!
