#!/bin/bash
echo "🚀 [FOX NOC] Ativando Cérebro Persistente..."

# Ativa a venv que criamos na pasta mapeada
source /app/.venv_container/bin/activate

# Tenta instalar o Nmap (única coisa que o apt precisa fazer, é rápido)
# Se o apt-get falhar (sem internet), o script continua
apt-get update && apt-get install -y nmap || echo "⚠️ Falha ao instalar Nmap, mas continuando..."

echo "✅ [FOX NOC] Ambiente pronto. Lançando Maestro..."

# Inicia o servidor Python usando o python da venv
exec python3 /app/main.py

