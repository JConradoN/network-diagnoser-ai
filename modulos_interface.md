# Sugestões de Módulos para Interface e Relatório

## Módulos Disponíveis para Seleção na Interface

- ARP Scanner (descoberta de dispositivos)
- Port Scanner (detecção de portas abertas)
- SNMP Collector (coleta de informações do MikroTik e outros dispositivos)
- mDNS Discovery (descoberta de serviços multicast)
- SSDP Discovery (descoberta de dispositivos UPnP)
- Latency Tester (teste de ping, jitter, perda)
- DNS Tester (resolução de domínio e tempo)
- OS Detection (identificação do sistema operacional)
- DHCP Lease Reader (leitura de leases DHCP)
- Topology Builder (construção da topologia da rede)
- Problem Detector (detecção de problemas e anomalias)
- Gemini AI Analyzer (diagnóstico inteligente via IA)

## Módulos que Podem Ser Chamados Obrigatoriamente

- ARP Scanner (base para todos os relatórios)
- Latency Tester (diagnóstico de qualidade de rede)
- DNS Tester (verificação de resolução)
- Problem Detector (identificação de anomalias)
- Gemini AI Analyzer (diagnóstico avançado)

## Módulos Avançados/Opcionais

- Port Scanner
- SNMP Collector
- mDNS/SSDP Discovery
- OS Detection
- DHCP Lease Reader
- Topology Builder

## Sugestão de Interface

- Permitir seleção dos módulos opcionais (checkbox)
- Módulos obrigatórios sempre executados
- Exibir descrição breve de cada módulo

## Exemplos de Checkbox na Interface

- [x] ARP Scanner (sempre ativo)
- [x] Latency Tester (sempre ativo)
- [x] DNS Tester (sempre ativo)
- [ ] Port Scanner
- [ ] SNMP Collector
- [ ] mDNS Discovery
- [ ] SSDP Discovery
- [ ] OS Detection
- [ ] DHCP Lease Reader
- [ ] Topology Builder
- [x] Problem Detector (sempre ativo)
- [x] Gemini AI Analyzer (sempre ativo)

## Observações
- ARP, Latency, DNS, Problem Detector e Gemini AI são essenciais para o relatório.
- Port scan, SNMP, mDNS/SSDP, OS detection, DHCP e topologia podem ser opcionais conforme necessidade.
- Interface pode ser expandida para permitir customização do relatório.
