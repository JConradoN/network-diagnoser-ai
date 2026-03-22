# FOX Network Diagnoser AI — Documentação Final

## Status do Projeto
- **Status:** Finalizado
- **Ambiente:** Produção
- **Data:** 22/03/2026

---

## Resumo das Principais Features
- Dashboard NOC em tempo real (Tailwind, Chart.js, Lucide)
- Detecção de topologia física e lógica (Internet > Modem > MikroTik > portas > dispositivos)
- Coleta de métricas: CPU, temperatura, dispositivos ativos
- Monitoramento de tráfego (SNMP MikroTik)
- Diagnóstico completo via IA (Gemini): latência, jitter, perda, análise heurística
- Detecção de failover WAN (Vivo → NIO) e alerta de NAT duplo
- Alerta de saída do modo bridge da Vivo (NAT privado na WAN)
- Ferramentas CLI: scan, benchmark, relatórios, interfaces
- Relatório PDF gerencial com diagnóstico de IA, inventário, saúde do roteador
- DNS estático no MikroTik — acesso por nome (http://fox-dev)
- IPs organizados: 200+ fixos, 100-199 dinâmicos

---

## Estrutura de Diretórios
- **app.py** — Entrypoint CLI
- **api.py** — Backend FastAPI (endpoints REST)
- **cli.py** — CLI robusta
- **config.py** — Configuração e variáveis de ambiente
- **database.py** — Persistência SQLite
- **performance.py** — Ping, jitter, DNS, traceroute
- **analyzer/** — Lógica de análise IA
- **collectors/** — Integrações MikroTik, SNMP, DHCP
- **output/** — Relatórios (JSON, Markdown)
- **scanner/** — Coleta: ARP, SNMP, DHCP, mDNS, SSDP, portas, latência
- **services/** — Orquestração da pipeline de diagnóstico
- **utils/** — Utilitários: logger, lookup MAC, helpers de rede
- **app/noc/index.html** — Dashboard frontend

---

## Endpoints REST Principais
- `/system/metrics` — CPU, temperatura, dispositivos
- `/performance/ping` — Latência, jitter, perda
- `/network/traffic` — Tráfego histórico
- `/topology/map` — Topologia física
- `/dashboard/stats` — Diagnóstico IA, relatório bruto
- `/scan/start` — Inicia diagnóstico

---

## Mudanças Relevantes (Resumo)
- Implementação do dashboard NOC com alertas críticos (ex: saída do bridge mode Vivo)
- Detecção automática de failover WAN e NAT duplo
- Pipeline de diagnóstico modular (CLI e API)
- Relatórios PDF e integração com IA Gemini
- Organização dos IPs e DNS estático
- Scripts de deploy (Docker, K3s, entrypoint)
- Testes unitários e integração

---

## Orientações Finais
- Para subir a API: `uvicorn api:app --host 0.0.0.0 --port 80`
- Para executar diagnóstico CLI: `python app.py`
- Para acessar o dashboard: `http://<ip-servidor>/app/noc/`
- Variáveis de ambiente em `config.py`
- Relatórios e logs em `output/`

---

## Observações
- Projeto modular, scanners podem ser usados isoladamente
- Backend serve dashboard e API REST na mesma porta
- Diagnóstico pode ser disparado via API ou CLI
- Sistema em produção, monitoramento ativo

---

_Para dúvidas ou manutenção, consulte os arquivos README.md e INSTALL.md._
