# Guia de Instalação — Network Diagnoser AI

## 1. Pré-requisitos
- Python 3.12+
- Linux recomendado (funciona em Mac, parcial no Windows)
- Acesso root/sudo para instalar dependências de sistema (ex: scapy, nmap)

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

Ou exporte manualmente:
```bash
export ND_SUBNET="192.168.88.0/24"
export ND_INTERFACE="wlan0"
# ... demais variáveis
```

## 7. Teste a instalação

```bash
python app.py --help
```

Se aparecer o menu de comandos, está pronto para uso!
