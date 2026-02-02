<div align="center">

# 📊 SD-WAN Health Monitor

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Web_Dashboard-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Cisco vManage](https://img.shields.io/badge/Cisco-vManage-1BA0D7?style=for-the-badge&logo=cisco&logoColor=white)](https://cisco.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

**Real-time SD-WAN monitoring dashboard with alerting for Cisco vManage/vEdge environments**

[Features](#-features) • [Installation](#-installation) • [Dashboard](#-dashboard) • [API Reference](#-api-reference)

---

<img src="https://img.shields.io/badge/Status-Production_Ready-success?style=for-the-badge" alt="Status"/>

</div>

## 🎯 Overview

The **SD-WAN Health Monitor** provides a comprehensive monitoring solution for Cisco SD-WAN (Viptela) environments. It connects to vManage REST API to collect real-time health metrics and presents them in an intuitive web dashboard.

### Key Benefits

| Benefit | Description |
|---------|-------------|
| 🔍 **Visibility** | Single-pane view of entire SD-WAN fabric |
| ⚡ **Real-time** | Live metrics with configurable refresh |
| 🚨 **Proactive** | Automated alerting before outages |
| 📈 **Historical** | Trend analysis and capacity planning |
| 🔧 **Actionable** | Direct links to vManage for remediation |

---

## ⚡ Features

### 📊 Monitoring Capabilities

```
┌─────────────────────────────────────────────────────────────────┐
│                    HEALTH METRICS                               │
├─────────────────────────────────────────────────────────────────┤
│  DEVICE HEALTH          │  TUNNEL HEALTH          │  APP SLA    │
│  ─────────────────────  │  ─────────────────────  │  ────────── │
│  • CPU Utilization      │  • BFD Status           │  • Latency  │
│  • Memory Usage         │  • IPSec State          │  • Jitter   │
│  • Disk Space           │  • Packet Loss          │  • Loss     │
│  • Control Connections  │  • Tunnel Uptime        │  • MOS      │
│  • Reachability         │  • Color Status         │  • SLA Met  │
├─────────────────────────────────────────────────────────────────┤
│  INTERFACE STATS        │  CONTROL PLANE          │  ALARMS     │
│  ─────────────────────  │  ─────────────────────  │  ────────── │
│  • TX/RX Throughput     │  • vSmart Connections   │  • Critical │
│  • Error Rates          │  • OMP Peering          │  • Major    │
│  • Utilization %        │  • vBond Status         │  • Minor    │
│  • Admin/Oper Status    │  • Certificate Health   │  • Warning  │
└─────────────────────────────────────────────────────────────────┘
```

### 🖥️ Dashboard Views

- **Overview** - Fabric-wide health summary
- **Devices** - Detailed device status grid
- **Tunnels** - IPSec tunnel health matrix
- **Applications** - SLA compliance tracking
- **Alarms** - Active alarm management
- **Reports** - Historical trend analysis

---

## 📦 Installation

```bash
# Clone repository
git clone https://github.com/tamersaid2022/sdwan-health-monitor.git
cd sdwan-health-monitor

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure vManage connection
cp config.example.yaml config.yaml
# Edit config.yaml with your vManage details

# Run application
python sdwan_monitor.py
```

### Requirements

```txt
flask>=3.0.0
requests>=2.31.0
pyyaml>=6.0
python-dotenv>=1.0.0
apscheduler>=3.10.0
flask-socketio>=5.3.0
redis>=5.0.0
pandas>=2.0.0
plotly>=5.18.0
```

---

## 🚀 Usage

### Quick Start

```python
from sdwan_monitor import SDWANMonitor

# Initialize monitor
monitor = SDWANMonitor(
    vmanage_host="vmanage.company.com",
    username="admin",
    password="password"
)

# Get fabric health
health = monitor.get_fabric_health()
print(f"Healthy devices: {health['healthy']}/{health['total']}")

# Get device details
devices = monitor.get_devices()
for device in devices:
    print(f"{device['hostname']}: CPU {device['cpu']}%, Memory {device['memory']}%")

# Check tunnel status
tunnels = monitor.get_tunnels()
for tunnel in tunnels:
    print(f"{tunnel['source']} -> {tunnel['dest']}: {tunnel['state']}")
```

### Run Dashboard

```bash
# Development mode
python sdwan_monitor.py --debug

# Production with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 sdwan_monitor:app

# With Docker
docker-compose up -d
```

### Access Dashboard

Open browser to: `http://localhost:5000`

Default credentials: `admin` / `admin` (change on first login)

---

## 📋 Configuration

### config.yaml

```yaml
# config.yaml
---
vmanage:
  host: vmanage.company.com
  port: 443
  username: ${VMANAGE_USER}
  password: ${VMANAGE_PASSWORD}
  verify_ssl: false
  
monitoring:
  refresh_interval: 60  # seconds
  history_retention: 30  # days
  
thresholds:
  cpu_warning: 70
  cpu_critical: 90
  memory_warning: 75
  memory_critical: 95
  tunnel_loss_warning: 1
  tunnel_loss_critical: 5
  latency_warning: 100
  latency_critical: 300
  
alerting:
  enabled: true
  email:
    smtp_server: smtp.company.com
    recipients:
      - netops@company.com
  slack:
    webhook_url: ${SLACK_WEBHOOK}
    channel: "#sdwan-alerts"
  
dashboard:
  host: 0.0.0.0
  port: 5000
  secret_key: ${FLASK_SECRET_KEY}
```

---

## 🖥️ Dashboard Screenshots

### Overview Page
```
╔══════════════════════════════════════════════════════════════════════╗
║  SD-WAN HEALTH MONITOR                              🟢 Connected     ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ ║
║  │   DEVICES    │  │   TUNNELS    │  │    ALARMS    │  │   SLA    │ ║
║  │     125      │  │     847      │  │      3       │  │   98.5%  │ ║
║  │  🟢 123 Up   │  │  🟢 842 Up   │  │  🔴 1 Crit   │  │          │ ║
║  │  🔴 2 Down   │  │  🔴 5 Down   │  │  🟠 2 Major  │  │  Target  │ ║
║  └──────────────┘  └──────────────┘  └──────────────┘  │   99%    │ ║
║                                                        └──────────┘ ║
║  ════════════════════════════════════════════════════════════════   ║
║                                                                      ║
║  TOP ISSUES                              RECENT EVENTS               ║
║  ─────────────────────────────────────   ─────────────────────────   ║
║  🔴 BR-NYC-01: Control disconnected      14:32 Tunnel up: DC1-DC2   ║
║  🟠 BR-LAX-02: CPU 94%                   14:28 Device reboot: BR5   ║
║  🟠 BR-CHI-01: Memory 88%                14:15 Alarm cleared: BR12  ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
```

### Device Health Grid
```
╔══════════════════════════════════════════════════════════════════════╗
║  DEVICE HEALTH                                    Filter: All Sites  ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  Device          Site       Status    CPU    Mem    Ctrl   Tunnels  ║
║  ─────────────────────────────────────────────────────────────────   ║
║  DC-vEdge-01     DC-East    🟢 Up     45%    62%    2/2    48/48    ║
║  DC-vEdge-02     DC-East    🟢 Up     38%    58%    2/2    48/48    ║
║  DC-vEdge-03     DC-West    🟢 Up     52%    71%    2/2    48/48    ║
║  BR-NYC-01       NYC        🔴 Down   --     --     0/2    0/24     ║
║  BR-NYC-02       NYC        🟢 Up     67%    75%    2/2    24/24    ║
║  BR-LAX-01       LAX        🟢 Up     72%    68%    2/2    24/24    ║
║  BR-LAX-02       LAX        🟠 Warn   94%    82%    2/2    24/24    ║
║  BR-CHI-01       Chicago    🟠 Warn   58%    88%    2/2    24/24    ║
║                                                                      ║
║  Showing 8 of 125 devices                          [1] 2 3 ... 16   ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## 🔌 API Reference

### REST Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Fabric health summary |
| `/api/devices` | GET | All device status |
| `/api/devices/<id>` | GET | Single device details |
| `/api/tunnels` | GET | All tunnel status |
| `/api/alarms` | GET | Active alarms |
| `/api/alarms/<id>/ack` | POST | Acknowledge alarm |
| `/api/sla` | GET | SLA compliance data |
| `/api/history/<metric>` | GET | Historical metrics |

### Example API Responses

```json
// GET /api/health
{
  "status": "healthy",
  "timestamp": "2024-01-15T14:30:00Z",
  "summary": {
    "devices": {"total": 125, "healthy": 123, "warning": 2, "critical": 0},
    "tunnels": {"total": 847, "up": 842, "down": 5},
    "alarms": {"critical": 1, "major": 2, "minor": 5, "warning": 12},
    "sla_compliance": 98.5
  }
}

// GET /api/devices
{
  "devices": [
    {
      "device_id": "10.1.1.1",
      "hostname": "DC-vEdge-01",
      "site_id": "100",
      "status": "reachable",
      "cpu_percent": 45,
      "memory_percent": 62,
      "disk_percent": 34,
      "control_connections": 2,
      "tunnels_up": 48,
      "tunnels_total": 48,
      "uptime": "45 days",
      "version": "20.9.3"
    }
  ]
}
```

---

## 🚨 Alerting

### Supported Channels

- **Email** - SMTP-based alerts with HTML templates
- **Slack** - Webhook integration with rich formatting
- **Microsoft Teams** - Incoming webhook connector
- **PagerDuty** - Incident creation for critical alerts
- **Syslog** - Forward to SIEM systems
- **Webhook** - Generic HTTP POST to any endpoint

### Alert Rules

```yaml
# Alert rule examples
alerts:
  - name: "Device Unreachable"
    condition: "device.status == 'unreachable'"
    severity: critical
    channels: [email, slack, pagerduty]
    cooldown: 300  # seconds
    
  - name: "High CPU"
    condition: "device.cpu_percent > 90"
    severity: major
    channels: [slack]
    cooldown: 600
    
  - name: "Tunnel Down"
    condition: "tunnel.state == 'down'"
    severity: major
    channels: [email, slack]
    cooldown: 60
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        BROWSER                                  │
│                   (Dashboard UI)                                │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FLASK APPLICATION                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Routes    │  │   API       │  │   WebSocket (SocketIO)  │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Monitoring Service                          │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │   │
│  │  │ Collector│  │ Analyzer │  │ Alerter  │  │ Reporter │ │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST API
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     CISCO vMANAGE                               │
│         (SD-WAN Controller REST API)                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
sdwan-health-monitor/
├── sdwan_monitor.py         # Main application
├── config.yaml              # Configuration file
├── requirements.txt         # Dependencies
├── templates/
│   ├── base.html           # Base template
│   ├── dashboard.html      # Main dashboard
│   ├── devices.html        # Device view
│   └── tunnels.html        # Tunnel view
├── static/
│   ├── css/
│   │   └── style.css       # Custom styles
│   └── js/
│       └── dashboard.js    # Frontend JavaScript
├── lib/
│   ├── vmanage_api.py      # vManage API client
│   ├── collector.py        # Metrics collector
│   └── alerter.py          # Alert manager
└── tests/
    └── test_monitor.py     # Unit tests
```

---

## 🔐 Security

| Feature | Implementation |
|---------|----------------|
| **Authentication** | Session-based with configurable backends |
| **API Security** | Token-based authentication for API |
| **Credentials** | Environment variables / Vault integration |
| **SSL/TLS** | HTTPS support with certificate validation |
| **RBAC** | Role-based access control |
| **Audit** | Full audit logging of user actions |

---

## 📈 Roadmap

- [ ] Multi-tenant support
- [ ] Custom dashboard widgets
- [ ] Meraki SD-WAN support
- [ ] VMware VeloCloud support
- [ ] Network topology visualization
- [ ] Capacity planning reports
- [ ] Mobile app (iOS/Android)

---

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

### 👨‍💻 Author

**Tamer Khalifa** - *Network Automation Engineer*

[![CCIE](https://img.shields.io/badge/CCIE-68867-1BA0D7?style=flat-square&logo=cisco&logoColor=white)](https://www.cisco.com/c/en/us/training-events/training-certifications/certifications/expert.html)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?style=flat-square&logo=linkedin)](https://linkedin.com/in/tamerkhalifa2022)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-181717?style=flat-square&logo=github)](https://github.com/tamersaid2022)

---

⭐ **Star this repo if you find it useful!** ⭐

</div>
