# FOX Network Diagnoser AI — Resumo Técnico

## Visão Geral
O FOX Network Diagnoser AI é uma solução completa para diagnóstico, monitoramento e análise de redes, voltada para equipes de TI e gerentes de infraestrutura. O sistema integra coleta de dados, análise inteligente e visualização moderna, facilitando a identificação de problemas e a tomada de decisões.

---

## Stack Tecnológico
- **Backend:** Python 3.12, FastAPI
- **Frontend:** Dashboard web (HTML, Tailwind CSS, Chart.js, Lucide)
- **Banco de Dados:** SQLite (persistência local de resultados)
- **Coleta de Dados:** scapy (ARP), pysnmp (SNMP), requests, zeroconf (mDNS), integração MikroTik
- **Análise Inteligente:** Integração com IA Gemini para sumarização e insights
- **CLI:** Interface de linha de comando robusta para automação e integração
- **Containerização:** Docker, suporte a Kubernetes (K3s)

---

## Principais Ferramentas e Módulos
- **Coleta:** ARP scan, SNMP scan, mDNS, SSDP, DHCP, análise de portas, latência, jitter, tráfego
- **Análise:** Heurísticas, detecção de problemas, sumarização por IA
- **Relatórios:** Geração de relatórios em JSON, Markdown e visualização web
- **Dashboard:** Visualização em tempo real de métricas, topologia física, tráfego e status dos dispositivos
- **Integração MikroTik:** Coleta de tráfego, interfaces e DHCP

---

## Usabilidade
- **API REST:** Endpoints para métricas, performance, topologia, tráfego e relatórios
- **Dashboard Web:** Interface amigável para visualização de status, gráficos e relatórios
- **CLI:** Comandos para scan, benchmark, relatórios e automação
- **Modularidade:** Cada scanner pode ser utilizado isoladamente ou em pipeline
- **Automação:** Diagnóstico pode ser disparado via API, CLI ou agendado
- **Deploy Simples:** Pronto para rodar em ambiente local, Docker ou Kubernetes

---

## Exemplos de Uso
- **Subir API:** `uvicorn api:app --host 0.0.0.0 --port 80`
- **Executar Diagnóstico CLI:** `python cli.py scan --interface eth0 --json-output out.json`
- **Acessar Dashboard:** Navegar até `/app/noc/index.html` ou endpoint configurado

---

## Benefícios
- Diagnóstico rápido e preciso de redes
- Redução do tempo de troubleshooting
- Visualização clara da topologia e status
- Relatórios detalhados para auditoria e compliance
- Fácil integração com infraestrutura existente

---

## Contato
Para dúvidas técnicas ou contribuições, consulte a documentação ou entre em contato com o time de desenvolvimento.
