# FAQ & Troubleshooting — Network Diagnoser AI

## 1. O scan não encontra todos os dispositivos
- Certifique-se de rodar como root/sudo (necessário para ARP/Scapy)
- Desative firewalls locais temporariamente
- Verifique se a interface correta está configurada
- Dispositivos podem estar offline ou em modo de economia de energia

## 2. SNMP não retorna dados
- Confirme a comunidade SNMP e se o serviço está ativo no MikroTik
- Ajuste o timeout SNMP se a rede for lenta

## 3. API não sobe ou porta ocupada
- Verifique se já existe outro processo usando a porta 8000: `lsof -i :8000`
- Use outro valor de porta se necessário

## 4. Erro: "GEMINI_API_KEY nao configurada."
- Exporte a variável de ambiente com sua chave Gemini
- Veja `.env.example` para detalhes

## 5. Como atualizar dependências?
```bash
pip install --upgrade -r requirements.txt
```

## 6. Como rodar em background?
- Use `nohup`, `tmux` ou `systemd` (veja docs/SYSTEMD.md)

## 7. Como salvar e ler relatórios?
- Use as opções `--json-output` e `--md-output` na CLI
- Use os endpoints `/scan/save` e `/report/latest` na API

## 8. Como rodar testes?
```bash
pytest
```

## 9. Como resetar a placa de rede ou backend?
- Use o script `reset_server.sh` (ajuste conforme sua interface)
