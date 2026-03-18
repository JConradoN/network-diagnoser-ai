# Guia de Uso — Network Diagnoser AI

## 1. Executando o Diagnóstico (CLI)

```bash
python app.py scan --interface wlan0 --json-output network_report.json --md-output network_report.md
```

Ou diretamente pela CLI:
```bash
python cli.py scan --interface wlan0 --json-output network_report.json --md-output network_report.md
```

## 2. Usando a API REST (FastAPI)

Suba o backend:
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Endpoints principais:
- `POST /scan` — executa diagnóstico
- `POST /scan/save` — executa e salva relatório
- `GET /report/latest` — último relatório
- `GET /interfaces` — interfaces de rede

Exemplo de chamada via curl:
```bash
curl -X POST http://localhost:8000/scan/save -H 'Content-Type: application/json' -d '{"subnet": "192.168.88.0/24"}'
```

## 3. Variáveis de Ambiente

Veja `.env.example` para todas as opções.

## 4. Rodando em produção (systemd/nohup/tmux)

### Com nohup:
```bash
nohup uvicorn api:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &
```

### Com tmux:
```bash
tmux new -s diagnoser
uvicorn api:app --host 0.0.0.0 --port 8000
```

### Com systemd:
Veja docs/SYSTEMD.md

## 5. Rodando testes

```bash
pytest
```

## 6. Atualizando dependências

```bash
pip install --upgrade -r requirements.txt
```
