
#!/bin/bash

# Limpa logs antigos antes de iniciar
find /app -name '*.log' -delete

cd /app
export PYTHONPATH=$PYTHONPATH:/app

# Carrega variáveis do .env
if [ -f /app/.env ]; then
    set -a
    source /app/.env
    set +a
    echo "✅ .env carregado"
fi

# Verifica venv
if [ ! -d "/app/venv_k3s" ]; then
    echo "Criando nova venv e instalando dependências..."
    python3 -m venv /app/venv_k3s
    /app/venv_k3s/bin/pip install -r requirements.txt
else
    echo "✅ Venv já existe. Pulando instalação."
fi

echo "🚀 FOX NOC em órbita..."
/app/venv_k3s/bin/pip install psutil


# Resiliência: verifica se a porta 80 está ocupada antes de subir o Uvicorn
if lsof -Pi :80 -sTCP:LISTEN -t >/dev/null ; then
    echo "[ERRO] Porta 80 já está em uso!"
    PID=$(lsof -Pi :80 -sTCP:LISTEN -t)
    echo "Processo ocupando a porta 80: $PID"
    if command -v fuser >/dev/null 2>&1; then
        echo "Tentando matar o processo com fuser..."
        fuser -k 80/tcp || echo "[WARN] Não foi possível matar o processo."
    else
        echo "[WARN] fuser não disponível."
    fi
    sleep 2
    if lsof -Pi :80 -sTCP:LISTEN -t >/dev/null ; then
        echo "[FATAL] Porta 80 ainda está ocupada. Abortando startup."
        exit 1
    fi
fi

# Otimização: monitora apenas pastas de código para reload
exec /app/venv_k3s/bin/python3 -m uvicorn api:app \
    --host 0.0.0.0 --port 80 --reload \
    --reload-dir /app/analyzer \
    --reload-dir /app/services \
    --reload-dir /app/utils \
    --reload-dir /app/collectors
