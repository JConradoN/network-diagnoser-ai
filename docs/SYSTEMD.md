# Exemplo de Serviço systemd para Network Diagnoser AI

Crie o arquivo `/etc/systemd/system/network-diagnoser.service` com o conteúdo:

```
[Unit]
Description=Network Diagnoser AI Backend
After=network.target

[Service]
User=conrado
WorkingDirectory=/opt/network-scanner
EnvironmentFile=/opt/network-scanner/.env
ExecStart=/opt/network-scanner/.venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## Comandos úteis

```bash
sudo systemctl daemon-reload
sudo systemctl enable network-diagnoser
sudo systemctl start network-diagnoser
sudo systemctl status network-diagnoser
sudo journalctl -u network-diagnoser -f
```

Ajuste o caminho do WorkingDirectory, EnvironmentFile e ExecStart conforme sua instalação.
