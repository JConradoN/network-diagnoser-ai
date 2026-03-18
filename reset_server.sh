#!/bin/bash
# reset_server.sh: Reinicia o backend na porta 8000 e reseta a placa de rede Wi-Fi

set -e

WIFI_IFACE="wlp1s0"
PORT=8000
VENV_PATH=".venv/bin/uvicorn"
API_MODULE="api:app"

# Encontrar e matar processos na porta 8000
PIDS=$(lsof -ti tcp:$PORT || true)
if [ -n "$PIDS" ]; then
    echo "Matando processos na porta $PORT: $PIDS"
    kill -9 $PIDS
else
    echo "Nenhum processo rodando na porta $PORT."
fi

# Resetar a placa de rede Wi-Fi
if [ -n "$WIFI_IFACE" ]; then
    echo "Resetando interface Wi-Fi: $WIFI_IFACE"
    sudo ip link set "$WIFI_IFACE" down
    sleep 2
    sudo ip link set "$WIFI_IFACE" up
    sleep 2
else
    echo "Interface Wi-Fi não especificada."
fi

# Subir o backend
echo "Iniciando backend: $VENV_PATH $API_MODULE --host 0.0.0.0 --port $PORT"
$VENV_PATH $API_MODULE --host 0.0.0.0 --port $PORT
