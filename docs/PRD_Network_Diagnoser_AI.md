# PRD - Network Diagnoser AI

Versao: 1.0  
Autor: Joao  
Objetivo: Criar uma aplicacao inteligente capaz de escanear redes domesticas, diagnosticar problemas, identificar gargalos, sugerir topologias ideais e gerar recomendacoes de configuracao usando IA (Gemini API).

## 1. Visao Geral do Produto

O Network Diagnoser AI sera uma ferramenta que:

- Descobre automaticamente todos os dispositivos da rede
- Identifica roteadores, APs, switches, Mikrotik, TWIBI, PS5, PCs etc
- Coleta informacoes via ARP, SNMP, mDNS, SSDP, DHCP, ping e testes de DNS
- Detecta problemas como:
  - NAT multiplo
  - DHCP duplicado
  - APs em modo errado
  - latencia anormal
  - perda de pacotes
  - backhaul ruim
- Gera diagnosticos detalhados usando Gemini API
- Sugere a topologia ideal para a rede
- Sugere acoes de correcao

O produto deve funcionar em redes domesticas e pequenas empresas.

## 2. Objetivos do Produto

### 2.1 Objetivos principais

- Mapear automaticamente a rede local
- Identificar problemas de configuracao
- Gerar diagnostico inteligente
- Sugerir topologia ideal
- Ajudar usuarios a corrigir problemas de rede

### 2.2 Objetivos secundarios

- Facilitar troubleshooting
- Criar documentacao automatica da rede
- Servir como ferramenta de aprendizado

## 3. Arquitetura Geral

```text
Network Diagnoser AI
│
├── Scanner Layer
│   ├── ARP Scanner
│   ├── SNMP Collector
│   ├── Port Scanner
│   ├── mDNS/SSDP Discovery
│   ├── DHCP Lease Reader (opcional)
│   ├── Latency Tester
│   └── DNS Tester
│
├── Analyzer Layer
│   ├── Topology Builder
│   ├── Problem Detector
│   └── Gemini AI Analyzer
│
├── Output Layer
│   ├── Diagnostico
│   ├── Topologia ideal
│   ├── Acoes recomendadas
│   └── Relatorio final
│
└── Interface
    ├── CLI
    └── API REST (opcional)
```

## 4. Requisitos Funcionais (RF)

### RF01 - Escanear rede via ARP

O sistema deve identificar todos os dispositivos ativos na sub-rede.

### RF02 - Identificar fabricante via MAC OUI

O sistema deve mapear o fabricante de cada dispositivo.

### RF03 - Coletar informacoes via SNMP

Quando disponivel, coletar:

- sysName
- sysDescr
- sysUpTime
- interfaces
- roteamento

### RF04 - Descobrir servicos via mDNS/SSDP

Identificar:

- roteadores
- APs
- Chromecast
- impressoras
- IoT

### RF05 - Testar latencia entre nos

Executar ping com:

- jitter
- perda
- media

### RF06 - Testar DNS

Resolver dominios e medir tempo.

### RF07 - Detectar NAT multiplo

Analisar rotas e IPs WAN.

### RF08 - Detectar DHCP duplicado

Identificar multiplos servidores DHCP.

### RF09 - Detectar APs em modo errado

Ex.: TWIBI roteando em vez de AP.

### RF10 - Gerar diagnostico via Gemini

Enviar dados coletados e receber:

- analise
- problemas
- solucoes
- topologia ideal

### RF11 - Gerar relatorio final

Salvar relatório final em JSON, Markdown e banco SQLite (network_scanner.db).

## 5. Requisitos Nao Funcionais (RNF)

### RNF01 - Linguagem

Python 3.10+

### RNF02 - Portabilidade

Rodar em Windows, Linux e macOS.

### RNF03 - Seguranca

Nunca executar comandos destrutivos.

### RNF04 - Performance

Escanear redes de ate 254 hosts em < 10s.

## 6. Tecnologias

- Python
- Scapy (ARP)
- python-nmap (port scan)
- pysnmp
- zeroconf (mDNS)
- requests (Gemini API)
- FastAPI (opcional)

## 7. Estrutura do Projeto

```text
network-diagnoser/
│
├── scanner/
│   ├── arp_scanner.py
│   ├── snmp_scanner.py
│   ├── port_scanner.py
│   ├── mdns_scanner.py
│   ├── ssdp_scanner.py
│   ├── latency_tester.py
│   └── dns_tester.py
│
├── analyzer/
│   ├── topology_builder.py
│   ├── problem_detector.py
│   └── gemini_analyzer.py
│
├── utils/
│   ├── mac_lookup.py
│   ├── network_utils.py
│   └── logger.py
│
├── output/
│   ├── report_generator.py
│   └── templates/
├── database.py
├── network_scanner.db
├── app.py
├── config.py
└── requirements.txt
```

## 8. Fluxo de Funcionamento

1. Usuario executa app.py
2. Sistema detecta sub-rede local
3. Executa ARP scan
4. Identifica fabricantes
5. Executa SNMP (se disponivel)
6. Executa mDNS/SSDP
7. Executa testes de latencia
8. Executa testes de DNS
9. Constrói topologia
10. Detecta problemas
11. Envia tudo ao Gemini
12. Recebe diagnostico
13. Gera relatorio final

## 9. Modelo de Prompt para o Gemini

```text
Voce e um especialista em redes domesticas e corporativas.

Aqui estao os dados coletados da rede:

{devices}
{links}
{latency}
{dns}
{snmp}
{routes}

Com base nisso, gere:

1. Diagnostico detalhado
2. Lista de problemas encontrados
3. Causas provaveis
4. Sugestoes de correcao
5. Topologia ideal recomendada
6. Lista de acoes passo a passo
7. Riscos se nada for corrigido

Responda em formato JSON estruturado.
```

## 10. Criterios de Aceitacao

- CA01: O sistema deve identificar pelo menos 90% dos dispositivos ativos
- CA02: O sistema deve detectar NAT multiplo
- CA03: O sistema deve detectar DHCP duplicado
- CA04: O sistema deve gerar diagnostico via Gemini
- CA05: O relatorio final deve ser JSON valido

## 11. Backlog Inicial

### Sprint 1 - Scanner basico

- ARP scanner
- MAC lookup
- Latency tester
- DNS tester

### Sprint 2 - Descoberta avancada

- SNMP
- mDNS
- SSDP
- Port scan

### Sprint 3 - Analise

- Topology builder
- Problem detector

### Sprint 4 - IA

- Integracao Gemini
- Geracao de diagnostico

### Sprint 5 - Relatorio

- JSON final
- CLI

## 12. Prompts recomendados para o GitHub Copilot

### Criar modulo ARP

```text
Implemente o arquivo scanner/arp_scanner.py com uma classe ARPScanner que:
- recebe uma sub-rede
- executa ARP scan usando scapy
- retorna lista de dispositivos com IP, MAC e fabricante
- inclui logs e tratamento de erros
```

### Criar modulo SNMP

```text
Implemente scanner/snmp_scanner.py com uma classe SNMPScanner que:
- recebe IP e community
- coleta sysName, sysDescr, sysUpTime
- retorna JSON
```

### Criar integracao Gemini

```text
Implemente analyzer/gemini_analyzer.py com uma classe GeminiAnalyzer que:
- recebe dados da rede
- monta prompt
- envia para Gemini API
- retorna diagnostico estruturado
```
