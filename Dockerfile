
# ATENÇÃO: Para ARP Scan e Traceroute funcionarem, rode o container com:
# --cap-add=NET_RAW --cap-add=NET_ADMIN
FROM python:3.12-slim

# 1. Instala dependências de SISTEMA (Essencial para compilar Scapy, Cryptography, etc)
RUN apt-get update && apt-get install -y \
    nmap \
    iputils-ping \
    iproute2 \
    traceroute \
    iputils-tracepath \
    libpcap-dev \
    gcc \
    python3-dev \
    musl-dev \
    net-tools \
    curl \
    libssl-dev \
    libffi-dev \
    snmp \
    && rm -rf /var/lib/apt/lists/*

# 2. Configurações de ambiente
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# 3. TRUQUE DE MESTRE: Copia APENAS o requirements primeiro
# Isso garante que o Docker faça cache das bibliotecas. 
# Ele só baixará tudo de novo se você alterar o requirements.txt.
COPY requirements.txt .

# 4. Instala as dependências do sistema no Python global do container
# (Como o container é isolado, não precisamos de venv interna, 
# mas manteremos a compatibilidade com seu script se desejar)
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y traceroute


# 5. Copia arquivos estáticos primeiro para garantir estrutura correta
COPY ./app /app
# 6. Copia o restante do código (API, scripts, etc)
COPY . .


# 7. Garante permissão de execução no script de boot
RUN chmod +x /app/entrypoint.sh


# 8. Healthcheck para o endpoint principal da API
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fs http://localhost/dashboard/stats | grep -q 'ai_summary'

ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
EXPOSE 80