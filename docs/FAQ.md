
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
- Os relatórios também são salvos automaticamente no banco SQLite (network_scanner.db) e podem ser exportados em PDF
- Use os endpoints `/scan/save`, `/report/latest`, `/network/report/pdf`, `/dashboard/stats`, `/network/topology`, `/network/performance` na API para consultar, filtrar, exportar e visualizar dados avançados do relatório


## 8. Como monitorar a qualidade da rede (packet loss, jitter, DNS)?
- Acesse o painel "Qualidade da Rede" no dashboard ou consulte o endpoint `/wifi/quality` para métricas em tempo real e histórico.
- Alertas automáticos são exibidos para perda de pacotes, jitter alto, DNS lento e APs offline.

## 9. Como analisar e corrigir interferência WiFi?
- Use a ferramenta "Análise de Canais WiFi" no dashboard ou via API (`/tools/run/wifi-channels`).
- Siga as recomendações de canal e, se necessário, aplique a troca de canal pelo dashboard/API.

## 10. Como funciona o suporte a dual-WAN (Vivo/NIO)?
- O sistema detecta automaticamente ambos os links, status de failover e load balance.
- A topologia física exibe badges e alertas para cada cenário.

## 11. Como usar as ferramentas avançadas?
- Bufferbloat Test: execute pelo dashboard ou API para analisar latência sob carga.
- Troca de canal Twibi: disponível no dashboard/API, requer credenciais dos APs.

## 12. Como rodar testes?
```bash
pytest
```

## 13. Como resetar a placa de rede ou backend?
- Use o script `reset_server.sh` (ajuste conforme sua interface)
