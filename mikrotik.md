# MikroTik — Documentação e Script de Recuperação

> **Gerado em:** 2026-03-23
> **Fonte:** dump direto do terminal RouterOS + dados do FOX NOC
> **Ambiente:** Rede doméstica · Dual-WAN (Vivo PPPoE + NIO DHCP) · Mesh Twibi Force AX

---

## 1. Hardware e Identidade

| Campo | Valor |
|---|---|
| Hostname | `MikroTik` |
| IP LAN | `192.168.88.1` |
| RouterOS | **v6** (sintaxe `routing-mark`, sem `/routing table`) |
| CPU idle | ~1% |
| Temperatura | ~48 °C |
| Tensão | 24.2 V |

### Interfaces físicas

| Nome | Default | Tipo | MAC | Comentário |
|---|---|---|---|---|
| `lan-ap1` | ether3 | ether | F4:1E:57:81:F4:BE | Intelbras Twibi 1 (Principal) |
| `lan-ap2` | ether4 | ether | F4:1E:57:81:F4:BF | Intelbras Twibi 2 (Quintal) |
| `lan-ap3` | ether5 | ether | F4:1E:57:81:F4:C0 | Intelbras Twibi 3 (Sala) |
| `wan-nio`  | ether2 | ether | F4:1E:57:81:F4:BD | ISP NIO – DHCP |
| `wan-vivo` | ether1 | ether | F4:1E:57:81:F4:BC | ISP Vivo – PPPoE |
| `bridge-lan` | — | bridge | F4:1E:57:81:F4:BE | LAN Bridge |
| `pppoe-vivo` | — | pppoe-out | — | PPPoE sobre wan-vivo |

---

## 2. Credenciais

| Usuário | Senha | Acesso |
|---|---|---|
| `admin` | `JC@mct21` | Full — console, WinBox, API |
| `homemonitor` | *(vazio)* | Read-only — FOX NOC via API porta 8728 |
| PPPoE Vivo | user: `cliente@cliente` / pass: `cliente` | Autenticação PPPoE ISP |

---

## 3. Diagrama Lógico da Rede

```
Internet
   │
   ├── Modem Vivo (modo bridge — PPPoE encerrado no MikroTik)
   │     └── wan-vivo (ether1)
   │           └── pppoe-vivo → IP real dinâmico (ex: 179.178.177.x)
   │
   └── Modem NIO (DHCP, double NAT — MikroTik em DMZ)
         └── wan-nio (ether2) → 192.168.100.100/24
                                  gateway: 192.168.100.1

                   ┌─────────────────────────────────┐
                   │  MikroTik  (192.168.88.1)        │
                   │  PCC Load Balance + Failover     │
                   └─────────────────────────────────┘
                                   │
                             bridge-lan
                        (192.168.88.0/24)
                   ┌───────┬────────────────┐
                 ether3   ether4          ether5
                lan-ap1  lan-ap2         lan-ap3
                Twibi    Twibi           Twibi
               Principal Quintal (C44D)  Sala (108B)
              .210       .211            .212
```

---

## 4. Endereçamento IP

| Interface | Endereço | Tipo | Observação |
|---|---|---|---|
| `bridge-lan` | 192.168.88.1/24 | estático | Gateway LAN |
| `pppoe-vivo` | 179.178.177.x/32 | dinâmico (PPPoE) | IP real Vivo |
| `wan-nio` | 192.168.100.100/24 | dinâmico (DHCP) | Double NAT NIO |

**DHCP Server LAN:** pool `192.168.88.2 – 192.168.88.254`
**DNS servido para clientes:** `192.168.88.1` (MikroTik com static entries + forward)
**DNS MikroTik (dinâmico, via PPPoE/NIO):** `187.50.250.115`, `187.50.250.215`, `192.168.100.1`
**Domínio local:** `lan`

---

## 5. Roteamento e Dual-WAN

### Tabela de rotas

| # | Destino | Gateway | Dist. | Routing-Mark | Tipo |
|---|---|---|---|---|---|
| 0 | 0.0.0.0/0 | pppoe-vivo | 1 | — | static (default Vivo) |
| 1 | 0.0.0.0/0 | 192.168.100.1 | 1 | — | static (default NIO — load balance) |
| 2 | 0.0.0.0/0 | pppoe-vivo | 1 | — | dynamic (do pppoe-client) |
| 3 | 0.0.0.0/0 | 192.168.100.1 | 2 | — | static (failover NIO) |
| 4 | 0.0.0.0/0 | 192.168.100.1 | 10 | — | dynamic |
| — | 0.0.0.0/0 | pppoe-vivo | 1 | `via-vivo` | static + check-gateway=ping |
| — | 0.0.0.0/0 | 192.168.100.1 | 1 | `via-nio` | static + check-gateway=ping |

> **Nota:** as rotas com `routing-mark` não aparecem no `print` padrão — use `/ip route print detail where routing-mark~"via"` para vê-las.

### Estratégia PCC (Per Connection Classifier)

- `both-addresses:2/0` → marca conexão como `vivo-conn` → routing-mark `via-vivo` → sai por `pppoe-vivo`
- `both-addresses:2/1` → marca conexão como `nio-conn` → routing-mark `via-nio` → sai por `wan-nio`
- Ambos os links com `check-gateway=ping`: se um cair, as rotas com aquele mark ficam inativas → failover automático

---

## 6. Issues Existentes na Config Atual ⚠️

Encontrados durante auditoria — **recomendado corrigir**:

```routeros
# 1. Remove NAT NIO duplicado (regras 2 e 3 são cópia da regra 0)
/ip firewall nat remove [find comment="NAT NIO" out-interface=wan-nio]
# Em seguida, adicione apenas uma:
/ip firewall nat add chain=srcnat action=masquerade out-interface=wan-nio comment="NAT NIO" place-before=0

# 2. Remove regra de firewall duplicada sem comentário (drop TCP 8728 sem comment)
/ip firewall filter remove [find chain=input action=drop protocol=tcp dst-port=8728 comment=""]

# 3. Desabilita api-ssl (porta 8729, sem restrição de IP — desnecessário)
/ip service set api-ssl disabled=yes
```

---

## 7. Script de Recuperação Completo (RouterOS v6)

Execute no terminal do MikroTik (**Winbox → New Terminal** ou SSH) em blocos, na ordem.

```routeros
# ═══════════════════════════════════════════════════════════════════
# BLOCO 1 — IDENTIDADE
# ═══════════════════════════════════════════════════════════════════

/system identity set name=MikroTik
```

```routeros
# ═══════════════════════════════════════════════════════════════════
# BLOCO 2 — BRIDGE LAN
# ═══════════════════════════════════════════════════════════════════

/interface bridge add name=bridge-lan comment="LAN Bridge"

/interface bridge port
add bridge=bridge-lan interface=lan-ap1 comment="Twibi Principal"
add bridge=bridge-lan interface=lan-ap2 comment="Twibi Quintal"
add bridge=bridge-lan interface=lan-ap3 comment="Twibi Sala"
```

```routeros
# ═══════════════════════════════════════════════════════════════════
# BLOCO 3 — COMENTÁRIOS DAS INTERFACES FÍSICAS
# ═══════════════════════════════════════════════════════════════════

/interface set ether1 name=wan-vivo  comment="ISP Vivo - PPPoE"
/interface set ether2 name=wan-nio   comment="ISP NIO - DHCP"
/interface set ether3 name=lan-ap1   comment="Intelbras TWibi 1"
/interface set ether4 name=lan-ap2   comment="Intelbras TWibi 2"
/interface set ether5 name=lan-ap3   comment="Intelbras TWibi 3"
```

```routeros
# ═══════════════════════════════════════════════════════════════════
# BLOCO 4 — PPPoE CLIENT (Vivo) + DHCP CLIENT (NIO)
# ═══════════════════════════════════════════════════════════════════

# PPPoE Vivo — encerra no MikroTik, modem em modo bridge
/interface pppoe-client
add name=pppoe-vivo interface=wan-vivo \
    user="cliente@cliente" password="cliente" \
    add-default-route=no use-peer-dns=yes \
    keepalive-timeout=10 disabled=no \
    comment="PPPoE Vivo"

# DHCP NIO — modem NIO entrega 192.168.100.100/24
/ip dhcp-client
add interface=wan-nio add-default-route=no use-peer-dns=yes \
    comment="WAN NIO"
```

```routeros
# ═══════════════════════════════════════════════════════════════════
# BLOCO 5 — ENDEREÇO IP LAN
# ═══════════════════════════════════════════════════════════════════

/ip address
add address=192.168.88.1/24 interface=bridge-lan comment="Gateway LAN"
```

```routeros
# ═══════════════════════════════════════════════════════════════════
# BLOCO 6 — DNS
# ═══════════════════════════════════════════════════════════════════

# Sem servidores estáticos — usa dinâmicos recebidos via PPPoE e NIO DHCP
/ip dns set allow-remote-requests=yes cache-size=2048KiB
```

```routeros
# ═══════════════════════════════════════════════════════════════════
# BLOCO 7 — DHCP SERVER (LAN)
# ═══════════════════════════════════════════════════════════════════

/ip pool add name=pool-lan ranges=192.168.88.2-192.168.88.254

/ip dhcp-server
add name=dhcp-lan interface=bridge-lan address-pool=pool-lan \
    lease-time=1d disabled=no

/ip dhcp-server network
add address=192.168.88.0/24 gateway=192.168.88.1 \
    dns-server=192.168.88.1 domain=lan comment="Rede LAN"
```

```routeros
# ═══════════════════════════════════════════════════════════════════
# BLOCO 8 — ROTEAMENTO DUAL-WAN
# ═══════════════════════════════════════════════════════════════════

# Rotas default (ECMP — ambas ativas com distance=1 para load balance)
/ip route
add dst-address=0.0.0.0/0 gateway=pppoe-vivo      distance=1 comment="Default Vivo"
add dst-address=0.0.0.0/0 gateway=192.168.100.1   distance=1 comment="Default NIO (load balance)"
add dst-address=0.0.0.0/0 gateway=192.168.100.1   distance=2 comment="Default NIO (failover)"

# Rotas por routing-mark (usadas pelo PCC mangle) com check-gateway=ping
add dst-address=0.0.0.0/0 gateway=pppoe-vivo    distance=1 \
    routing-mark=via-vivo check-gateway=ping     comment="Route via Vivo"
add dst-address=0.0.0.0/0 gateway=192.168.100.1 distance=1 \
    routing-mark=via-nio  check-gateway=ping     comment="Route via NIO"
```

```routeros
# ═══════════════════════════════════════════════════════════════════
# BLOCO 9 — MANGLE (PCC Load Balancing)
# ═══════════════════════════════════════════════════════════════════

/ip firewall mangle

# Bypass PCC — redes locais (não devem receber routing-mark)
add chain=prerouting in-interface=bridge-lan dst-address=192.168.100.0/24 \
    action=accept passthrough=no \
    comment="bypass PCC - rede NIO local"

add chain=prerouting in-interface=bridge-lan dst-address=192.168.88.0/24 \
    action=accept passthrough=no \
    comment="bypass PCC - LAN local"

# PCC — distribui novas conexões 50/50
add chain=prerouting in-interface=bridge-lan connection-state=new \
    per-connection-classifier=both-addresses:2/0 \
    action=mark-connection new-connection-mark=vivo-conn passthrough=yes \
    comment="PCC Vivo"

add chain=prerouting in-interface=bridge-lan connection-state=new \
    per-connection-classifier=both-addresses:2/1 \
    action=mark-connection new-connection-mark=nio-conn passthrough=yes \
    comment="PCC NIO"

# Aplica routing-mark nas conexões marcadas (apenas tráfego originado da LAN)
add chain=prerouting in-interface=bridge-lan connection-mark=vivo-conn \
    action=mark-routing new-routing-mark=via-vivo passthrough=no \
    comment="Route Vivo"

add chain=prerouting in-interface=bridge-lan connection-mark=nio-conn \
    action=mark-routing new-routing-mark=via-nio passthrough=no \
    comment="Route NIO"
```

```routeros
# ═══════════════════════════════════════════════════════════════════
# BLOCO 10 — NAT
# ═══════════════════════════════════════════════════════════════════

/ip firewall nat
add chain=srcnat action=masquerade out-interface=wan-nio   comment="NAT NIO"
add chain=srcnat action=masquerade out-interface=pppoe-vivo comment="NAT Vivo"
```

```routeros
# ═══════════════════════════════════════════════════════════════════
# BLOCO 11 — FIREWALL FILTER
# ═══════════════════════════════════════════════════════════════════

/ip firewall filter

# Permite estabelecido/relacionado
add chain=input action=accept connection-state=established,related \
    comment="aceita estabelecido/related"

# Descarta inválido
add chain=input action=drop connection-state=invalid \
    comment="descarta invalido"

# Bloqueia acesso à API de fora da LAN
add chain=input action=drop protocol=tcp \
    src-address=!192.168.88.0/24 dst-port=8728 \
    comment="API MikroTik apenas LAN"

# Aceita tudo da LAN
add chain=input action=accept in-interface=bridge-lan \
    comment="aceita tudo da LAN"

# DROP padrão (tudo que não passou pelas regras acima)
add chain=input action=drop comment="DROP tudo da WAN"

# Forward — permite saída da LAN para internet
add chain=forward action=accept connection-state=established,related \
    comment="forward estabelecido/related"
add chain=forward action=drop connection-state=invalid \
    comment="forward descarta invalido"
```

```routeros
# ═══════════════════════════════════════════════════════════════════
# BLOCO 12 — UPNP (NAT aberto para PS5 e jogos)
# ═══════════════════════════════════════════════════════════════════

/ip upnp set enabled=yes allow-disable-external-interface=no

/ip upnp interfaces
add interface=bridge-lan  type=internal
add interface=pppoe-vivo  type=external
add interface=wan-nio     type=external
```

```routeros
# ═══════════════════════════════════════════════════════════════════
# BLOCO 13 — SERVIÇOS (hardening)
# ═══════════════════════════════════════════════════════════════════

/ip service
set telnet   disabled=yes
set ftp      disabled=yes
set www      disabled=yes
set www-ssl  disabled=yes
set api-ssl  disabled=yes
set ssh      address=192.168.88.0/24 port=22
set api      address=192.168.88.0/24 port=8728
set winbox   address=192.168.88.0/24 port=8291
```

```routeros
# ═══════════════════════════════════════════════════════════════════
# BLOCO 14 — USUÁRIO DE MONITORAMENTO (FOX NOC)
# ═══════════════════════════════════════════════════════════════════

/user group add name=readonly policy=read,test,winbox,web

/user add name=homemonitor group=readonly password="" \
    comment="FOX NOC read-only"
```

```routeros
# ═══════════════════════════════════════════════════════════════════
# BLOCO 15 — SNMP
# ═══════════════════════════════════════════════════════════════════

/snmp set enabled=yes community=public
```

---

## 8. Verificações Pós-Restauração

```routeros
# Interfaces rodando
/interface print where running=yes

# IPs atribuídos
/ip address print

# PPPoE conectado
/interface pppoe-client print

# Rotas ativas
/ip route print where active=yes

# Rotas com routing-mark (PCC)
/ip route print detail where routing-mark~"via"

# Mangle (verifique a ordem!)
/ip firewall mangle print

# NAT (confirme que não há duplicatas)
/ip firewall nat print

# Firewall
/ip firewall filter print

# UPnP
/ip upnp print
/ip upnp interfaces print

# Serviços (confirme desabilitados)
/ip service print

# Teste de conectividade por link
/ping 8.8.8.8 routing-mark=via-vivo count=3
/ping 8.8.8.8 routing-mark=via-nio  count=3
```

---

## 9. Notas de Manutenção

### Modem Vivo — modo bridge
- O modem Vivo opera em **modo bridge**: encaminha o PPPoE diretamente ao MikroTik
- O MikroTik encerra o PPPoE em `pppoe-vivo` com `user=cliente@cliente / pass=cliente`
- Se o modem sair do modo bridge (IP privado na WAN), o FOX NOC exibe `⚠️ Vivo saiu do modo Bridge!`
- Para reativar: acesse o painel do modem Vivo e reative o bridge mode

### Modem NIO — double NAT com DMZ
- O modem NIO faz NAT próprio; o MikroTik tem IP `192.168.100.100` na DMZ
- DMZ configurada no modem NIO apontando para `192.168.100.100`
- O acesso ao painel do modem NIO é feito em `http://192.168.100.1` a partir da LAN
- O link NIO **sempre** opera em double NAT — afeta levemente VoIP e jogos

### PCC e bypass obrigatório
- As regras de **bypass PCC** (Bloco 9, primeiras posições) são críticas
- Sem elas, tráfego para `192.168.100.0/24` recebe routing-mark `via-vivo` e é descartado
- As rotas com `routing-mark` **não aparecem** no `/ip route print` padrão — use `detail where routing-mark~"via"`

### RouterOS v6
- Use `routing-mark=` nas rotas (não `routing-table=` que é v6/v7 syntax do RouterOS 7)
- O `/routing table add` **não existe** no v6
- Ao fazer upgrade para v7, revisar sintaxe de rotas e mangle

---

## 10. Referência Rápida de IPs

### IPs Fixos (estáticos)

| Comentário | IP | MAC |
|---|---|---|
| MikroTik (gateway) | 192.168.88.1 | F4:1E:57:81:F4:BE |
| fox-dev | 192.168.88.200 | 24:F5:AA:55:87:F7 |
| fox-note | 192.168.88.201 | 60:C7:27:09:A7:E9 |
| twibi-principal | 192.168.88.210 | 98:2A:0A:CB:C4:9D |
| twibi-quintal | 192.168.88.211 | 98:2A:0A:CB:C4:4D |
| twibi-sala | 192.168.88.212 | 30:E1:F1:8D:10:8B |
| emilia-pc-eth | 192.168.88.220 | D0:94:66:AD:A6:DC |
| epson | 192.168.88.230 | 38:9D:92:06:46:3A |
| lg-tv | 192.168.88.240 | 78:DD:12:73:B0:82 |
| ps5 | 192.168.88.241 | 00:E4:21:57:31:04 |
| alexa | 192.168.88.242 | 08:C2:24:E0:E9:8F |
| Modem NIO (painel) | 192.168.100.1 | — |
| MikroTik via NIO | 192.168.100.100 | F4:1E:57:81:F4:BD |

### IPs Dinâmicos (DHCP — comentados)

| Comentário | MAC |
|---|---|
| joao-tab-s6 | 52:94:61:4F:A3:A2 |
| fox-cel-edge50 | F8:EF:5D:37:AB:40 |
| emilia-cel-edge50 | F8:EF:5D:37:B0:D1 |
| motorola-edge-20 | 30:09:C0:09:21:EF |
| joao-pc | E8:F4:08:BD:AF:A1 |
| joao-edge30 | A0:46:5A:71:D1:E9 |
| lg-tv-malu | 78:DD:12:46:FA:E4 |

### Bloqueados

| Comentário | MAC | Motivo |
|---|---|---|
| BLOQUEADO | B2:A6:11:1D:9A:22 | Desconhecido — causou SER L1 no Twibi Principal |
| BLOQUEADO | F2:6A:21:AC:82:7F | Desconhecido |
