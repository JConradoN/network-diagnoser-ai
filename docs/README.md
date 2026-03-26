
# Network Diagnoser AI — Documentação Completa

## Visão Geral
Diagnóstico inteligente de redes domésticas e SMB, com coleta ARP, SNMP, DHCP, análise de topologia, detecção de problemas e diagnóstico via IA (Gemini API). Gera relatórios detalhados em JSON, Markdown, PDF e salva automaticamente no banco SQLite (network_scanner.db). Inclui dashboard, topologia, performance, histórico, filtros avançados e exportação.

### Novidades e Melhorias Recentes
- **Monitoramento de Qualidade de Rede (WiFi/WAN):** Métricas em tempo real de perda de pacotes, jitter, latência DNS e status dos APs Twibi, com histórico e alertas automáticos (endpoint `/wifi/quality`).
- **Diagnóstico WiFi Mesh Avançado:** Coleta de interferência por nó/rádio, sugestão de melhores canais, ferramenta para troca de canal Twibi e alertas visuais no dashboard.
- **Dual-WAN e Topologia Física:** Visualização detalhada dos links Vivo/NIO, status de failover, load balance e badges de alerta.
- **Ferramentas Avançadas:** Bufferbloat Test, análise e troca de canais WiFi, recomendações automáticas.
- **Banco de Dados:** Histórico de qualidade de rede salvo em `wifi_metrics` para gráficos e análises.
- **Frontend:** Painel de qualidade de rede, status dos APs, interferência, badges de firmware e topologia física aprimorada.


## Estrutura do Projeto
- `app.py` — CLI principal
- `cli.py` — comandos detalhados
- `api.py` — API REST (FastAPI)
- `scanner/` — módulos de coleta (ARP, SNMP, DHCP, etc)
- `analyzer/` — análise, topologia, IA
- `output/` — geração de relatórios (JSON, Markdown, PDF)
- `database.py` — persistência dos relatórios em SQLite
- `network_scanner.db` — banco de dados SQLite (histórico de scans)
- `collectors/` — integrações MikroTik, SNMP, Twibi, WiFi Quality
- `services/` — orquestração da pipeline
- `tests/` — testes automatizados
- `requirements.txt` — dependências Python
- `.env.example` — exemplo de variáveis de ambiente
- `reset_server.sh` — script utilitário
- `docs/` — documentação detalhada

## Instalação
Veja `docs/INSTALL.md`

## Uso
Veja `docs/USAGE.md`

## Execução em Produção
Veja `docs/SYSTEMD.md`

## FAQ e Troubleshooting
Veja `docs/FAQ.md`

## Dependências principais
Veja `requirements.txt` (já revisado e atualizado)

## Atualização de dependências
```bash
pip install --upgrade -r requirements.txt
```

## Testes
```bash
pytest
```


## Observações
- Para diagnóstico IA, configure a variável `GEMINI_API_KEY`.
- Para máxima detecção, rode como root/sudo.
- Relatórios são salvos em JSON, Markdown, PDF e SQLite (network_scanner.db).
- O banco permite histórico, filtros, consultas rápidas via API/CLI e exportação em PDF.
- Endpoints avançados: dashboard, topologia, performance, scan em background, filtros por severidade/IP.
- **Qualidade de Rede:** Utilize o endpoint `/wifi/quality` para métricas em tempo real e histórico.
- **WiFi Mesh:** Ferramentas para análise de interferência, troca de canal e recomendações automáticas.
- **Topologia Física:** Visualização de dual-WAN, status de failover e load balance no dashboard.
