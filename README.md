# FOX Network Diagnoser AI

> AI-powered network diagnostics, real-time NOC dashboard, and infrastructure monitoring — built for engineers who need answers, not just data.

![NOC Dashboard — Engage Mission configuration](docs/screenshots/fox-noc_engage.jpg)

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-blue?logo=docker)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## The Problem

Traditional network monitoring tools tell you **what** is happening — high latency, a downed interface, packet loss. What they rarely tell you is **why**, and what to do about it.

FOX Network Diagnoser AI combines deep multi-protocol network scanning with LLM-powered analysis to deliver actionable diagnostics in plain language. Built and running in production since March 2026.

---

## Key Features

### Intelligent Diagnostics
- **AI-powered root cause analysis** — sends collected metrics to an LLM (Gemini / LiteLLM) for natural language interpretation and recommendations
- **Automatic anomaly detection** — heuristics detect double NAT, WAN failover events, ISP bridge mode changes before they cause support calls
- **Correlates multiple data sources** simultaneously: latency, SNMP counters, ARP tables, DNS resolution times

### Deep Protocol Coverage
- **ARP scan** — full Layer 2 host discovery with MAC vendor lookup
- **SNMP (MikroTik native)** — CPU, temperature, interface traffic, DHCP leases, wireless metrics
- **mDNS / SSDP** — detects IoT devices and services that don't respond to ARP
- **ICMP** — latency, jitter, packet loss to multiple targets in parallel
- **Port scanning** — targeted service detection

### Real-Time NOC Dashboard
- Live metrics with Chart.js (latency, jitter, traffic)
- Physical topology map: Internet → Modem → Router → switch ports → devices
- Critical alerts: WAN failover (ISP A → ISP B), double NAT detected, bridge mode exit
- Device inventory with status indicators

### Modular Architecture
- Each collector runs independently — use only what you need
- REST API + CLI + dashboard all served from a single process
- Schedulable diagnostics via API or cron
- Reports exported as PDF, JSON, or Markdown

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI |
| Frontend | HTML5, Tailwind CSS, Chart.js |
| Network scanning | Scapy (ARP), pysnmp, zeroconf, Scapy |
| AI analysis | Gemini API / LiteLLM (OpenAI-compatible) |
| Storage | SQLite |
| Deploy | Docker, Kubernetes (K3s) |

---

## Architecture

```
┌─────────────────────────────────────────────┐
│                  Collectors                  │
│  ARP │ SNMP │ mDNS │ SSDP │ ICMP │ Ports   │
└────────────────────┬────────────────────────┘
                     │ raw data
                     ▼
┌─────────────────────────────────────────────┐
│              Analysis Pipeline               │
│  Heuristics → Anomaly Detection → LLM API   │
└────────────────────┬────────────────────────┘
                     │ structured insights
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       REST API    Dashboard    CLI
       (FastAPI)   (NOC web)  (reports)
```

---

## Quick Start

```bash
git clone https://github.com/JConradoN/network-diagnoser-ai.git
cd fox-network-diagnoser
cp .env.example .env          # edit: set your interface, subnet, SNMP, API key
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

**Run the API + dashboard:**
```bash
uvicorn api:app --host 0.0.0.0 --port 8080
# Dashboard: http://localhost:8080/app/noc/
```

**Run a full diagnostic from CLI:**
```bash
python cli.py scan --interface eth0 --output report.json
python cli.py scan --interface eth0 --pdf-report
```

**Docker:**
```bash
docker build -t fox-diagnoser .
docker run --rm --net=host --cap-add=NET_RAW --cap-add=NET_ADMIN \
  --env-file .env fox-diagnoser
```

---

## API Reference (key endpoints)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/scan/start` | Trigger full network scan |
| `GET` | `/system/metrics` | CPU, temperature, active devices |
| `GET` | `/performance/ping` | Latency, jitter, packet loss |
| `GET` | `/network/traffic` | Historical SNMP traffic data |
| `GET` | `/topology/map` | Physical topology graph |
| `GET` | `/dashboard/stats` | Aggregated stats + AI diagnostic summary |

---

## Real-World Alerts (in production)

These are events the system detects automatically in a live home/SMB network:

- **WAN failover** — primary ISP (Vivo fiber) drops, router switches to 4G backup. Alert fires within 30 seconds.
- **ISP bridge mode exit** — ISP modem stops bridging and starts NAT-ing, creating double NAT. The system detects the private IP on the WAN interface and alerts.
- **Rogue DHCP / unexpected device** — new MAC address joins the network outside expected range.

---

## Project Structure

```
├── api.py              # FastAPI REST backend
├── cli.py              # Command-line interface
├── config.py           # Configuration (SNMP, AI API keys, targets)
├── database.py         # SQLite persistence
├── performance.py      # Ping, jitter, DNS, traceroute
├── analyzer/           # AI analysis + heuristics engine
├── collectors/         # MikroTik, SNMP, DHCP integrations
├── scanner/            # ARP, mDNS, SSDP, port scanners
├── services/           # Diagnostic pipeline orchestration
├── utils/              # MAC lookup, logger, network helpers
├── app/noc/            # NOC dashboard frontend
└── output/             # Generated reports (JSON, PDF, Markdown)
```

---

## Background

Built by a network engineer with 30 years of infrastructure experience who got tired of tools that show graphs but don't explain problems.

The AI integration goes beyond "summarize this data" — the LLM receives structured context about the network topology, current metrics, and historical baselines, and produces specific, actionable recommendations grounded in the actual state of the network.

Running in production monitoring a real home network with MikroTik hEX RB750Gr3 router, dual-ISP failover, and 20+ devices since March 2026.

---

## License

[MIT](LICENSE) — use it, fork it, build on it.
