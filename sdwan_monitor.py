#!/usr/bin/env python3
"""
SD-WAN Health Monitor
Real-time monitoring dashboard for Cisco vManage SD-WAN environments

Author: Tamer Khalifa (CCIE #68867)
GitHub: https://github.com/tamersaid2022
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from threading import Thread
import urllib3

import yaml
import requests
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

# Suppress SSL warnings for lab environments
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sdwan_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class Config:
    """Application configuration"""
    vmanage_host: str = ""
    vmanage_port: int = 443
    vmanage_username: str = ""
    vmanage_password: str = ""
    verify_ssl: bool = False
    refresh_interval: int = 60
    cpu_warning: int = 70
    cpu_critical: int = 90
    memory_warning: int = 75
    memory_critical: int = 95
    flask_host: str = "0.0.0.0"
    flask_port: int = 5000
    flask_secret: str = "change-me-in-production"
    
    @classmethod
    def from_file(cls, filepath: str) -> "Config":
        """Load config from YAML file"""
        config = cls()
        
        if os.path.exists(filepath):
            with open(filepath) as f:
                data = yaml.safe_load(f)
            
            vmanage = data.get("vmanage", {})
            config.vmanage_host = os.path.expandvars(vmanage.get("host", ""))
            config.vmanage_port = vmanage.get("port", 443)
            config.vmanage_username = os.path.expandvars(vmanage.get("username", ""))
            config.vmanage_password = os.path.expandvars(vmanage.get("password", ""))
            config.verify_ssl = vmanage.get("verify_ssl", False)
            
            monitoring = data.get("monitoring", {})
            config.refresh_interval = monitoring.get("refresh_interval", 60)
            
            thresholds = data.get("thresholds", {})
            config.cpu_warning = thresholds.get("cpu_warning", 70)
            config.cpu_critical = thresholds.get("cpu_critical", 90)
            config.memory_warning = thresholds.get("memory_warning", 75)
            config.memory_critical = thresholds.get("memory_critical", 95)
            
            dashboard = data.get("dashboard", {})
            config.flask_host = dashboard.get("host", "0.0.0.0")
            config.flask_port = dashboard.get("port", 5000)
            config.flask_secret = os.path.expandvars(dashboard.get("secret_key", "change-me"))
        
        # Override with environment variables
        config.vmanage_host = os.getenv("VMANAGE_HOST", config.vmanage_host)
        config.vmanage_username = os.getenv("VMANAGE_USER", config.vmanage_username)
        config.vmanage_password = os.getenv("VMANAGE_PASSWORD", config.vmanage_password)
        
        return config


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class DeviceHealth:
    """Device health metrics"""
    device_id: str
    hostname: str
    site_id: str
    status: str
    reachability: str
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    control_connections: int = 0
    control_connections_expected: int = 2
    tunnels_up: int = 0
    tunnels_total: int = 0
    uptime: str = ""
    version: str = ""
    model: str = ""
    board_serial: str = ""
    last_updated: datetime = field(default_factory=datetime.now)
    
    @property
    def health_status(self) -> str:
        """Calculate overall health status"""
        if self.status != "reachable":
            return "critical"
        if self.cpu_percent >= 90 or self.memory_percent >= 95:
            return "critical"
        if self.cpu_percent >= 70 or self.memory_percent >= 75:
            return "warning"
        if self.control_connections < self.control_connections_expected:
            return "warning"
        return "healthy"


@dataclass
class TunnelHealth:
    """IPSec tunnel health metrics"""
    source_ip: str
    dest_ip: str
    source_color: str
    dest_color: str
    state: str
    source_site: str
    dest_site: str
    latency_ms: float = 0.0
    jitter_ms: float = 0.0
    loss_percent: float = 0.0
    tx_bytes: int = 0
    rx_bytes: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class Alarm:
    """vManage alarm"""
    alarm_id: str
    severity: str
    type: str
    rule_name: str
    component: str
    device_id: str
    hostname: str
    message: str
    timestamp: datetime
    acknowledged: bool = False


@dataclass
class FabricHealth:
    """Overall fabric health summary"""
    total_devices: int = 0
    healthy_devices: int = 0
    warning_devices: int = 0
    critical_devices: int = 0
    unreachable_devices: int = 0
    total_tunnels: int = 0
    tunnels_up: int = 0
    tunnels_down: int = 0
    total_alarms: int = 0
    critical_alarms: int = 0
    major_alarms: int = 0
    minor_alarms: int = 0
    sla_compliance: float = 100.0
    last_updated: datetime = field(default_factory=datetime.now)


# =============================================================================
# VMANAGE API CLIENT
# =============================================================================

class VManageAPI:
    """Cisco vManage REST API client"""
    
    def __init__(self, host: str, username: str, password: str, port: int = 443, verify_ssl: bool = False):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.base_url = f"https://{host}:{port}"
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.token = None
        self.jsessionid = None
    
    def login(self) -> bool:
        """Authenticate to vManage"""
        try:
            # Get JSESSIONID
            login_url = f"{self.base_url}/j_security_check"
            payload = {
                "j_username": self.username,
                "j_password": self.password
            }
            
            response = self.session.post(login_url, data=payload, timeout=30)
            
            if response.status_code != 200 or "html" in response.text.lower():
                logger.error("vManage authentication failed")
                return False
            
            # Get CSRF token
            token_url = f"{self.base_url}/dataservice/client/token"
            token_response = self.session.get(token_url, timeout=30)
            
            if token_response.status_code == 200:
                self.token = token_response.text
                self.session.headers.update({"X-XSRF-TOKEN": self.token})
            
            logger.info(f"✅ Connected to vManage: {self.host}")
            return True
            
        except Exception as e:
            logger.error(f"vManage connection error: {e}")
            return False
    
    def logout(self):
        """Logout from vManage"""
        try:
            self.session.get(f"{self.base_url}/logout", timeout=10)
        except:
            pass
    
    def _get(self, endpoint: str) -> Optional[Dict]:
        """Make GET request to vManage API"""
        try:
            url = f"{self.base_url}/dataservice{endpoint}"
            response = self.session.get(url, timeout=60)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"API request failed: {endpoint} - {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"API request error: {endpoint} - {e}")
            return None
    
    def _post(self, endpoint: str, data: Dict) -> Optional[Dict]:
        """Make POST request to vManage API"""
        try:
            url = f"{self.base_url}/dataservice{endpoint}"
            response = self.session.post(url, json=data, timeout=60)
            
            if response.status_code in [200, 201]:
                return response.json()
            else:
                logger.warning(f"API POST failed: {endpoint} - {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"API POST error: {endpoint} - {e}")
            return None
    
    def get_devices(self) -> List[Dict]:
        """Get all devices from vManage"""
        result = self._get("/device")
        return result.get("data", []) if result else []
    
    def get_device_status(self) -> List[Dict]:
        """Get device status/health"""
        result = self._get("/device/monitor")
        return result.get("data", []) if result else []
    
    def get_device_counters(self, device_id: str) -> Dict:
        """Get device counters (CPU, memory, etc.)"""
        result = self._get(f"/device/counters?deviceId={device_id}")
        data = result.get("data", []) if result else []
        return data[0] if data else {}
    
    def get_control_connections(self) -> List[Dict]:
        """Get control connections status"""
        result = self._get("/device/control/connections")
        return result.get("data", []) if result else []
    
    def get_bfd_sessions(self) -> List[Dict]:
        """Get BFD sessions (tunnel health)"""
        result = self._get("/device/bfd/sessions")
        return result.get("data", []) if result else []
    
    def get_tunnel_statistics(self) -> List[Dict]:
        """Get tunnel statistics"""
        result = self._get("/statistics/approute/fec/aggregation")
        return result.get("data", []) if result else []
    
    def get_alarms(self, hours: int = 24) -> List[Dict]:
        """Get alarms from last N hours"""
        query = {
            "query": {
                "condition": "AND",
                "rules": [
                    {
                        "field": "entry_time",
                        "type": "date",
                        "value": [str(int((datetime.now() - timedelta(hours=hours)).timestamp() * 1000))],
                        "operator": "last_n_hours"
                    }
                ]
            }
        }
        result = self._post("/alarms", query)
        return result.get("data", []) if result else []
    
    def get_active_alarms(self) -> List[Dict]:
        """Get currently active (uncleared) alarms"""
        result = self._get("/alarms?cleared=false")
        return result.get("data", []) if result else []
    
    def acknowledge_alarm(self, alarm_id: str) -> bool:
        """Acknowledge an alarm"""
        result = self._post("/alarms/acknowledge", {"alarmId": alarm_id})
        return result is not None
    
    def get_interface_statistics(self, device_id: str) -> List[Dict]:
        """Get interface statistics for a device"""
        result = self._get(f"/statistics/interface?deviceId={device_id}")
        return result.get("data", []) if result else []
    
    def get_app_route_statistics(self) -> List[Dict]:
        """Get application-aware routing statistics (SLA)"""
        result = self._get("/statistics/approute")
        return result.get("data", []) if result else []


# =============================================================================
# MONITORING SERVICE
# =============================================================================

class SDWANMonitor:
    """SD-WAN monitoring service"""
    
    def __init__(self, config: Config):
        self.config = config
        self.api = VManageAPI(
            host=config.vmanage_host,
            username=config.vmanage_username,
            password=config.vmanage_password,
            port=config.vmanage_port,
            verify_ssl=config.verify_ssl
        )
        self.connected = False
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 30  # seconds
    
    def connect(self) -> bool:
        """Connect to vManage"""
        self.connected = self.api.login()
        return self.connected
    
    def disconnect(self):
        """Disconnect from vManage"""
        self.api.logout()
        self.connected = False
    
    def _get_cached(self, key: str, fetcher: callable, ttl: int = None) -> Any:
        """Get cached data or fetch new"""
        ttl = ttl or self._cache_ttl
        
        if key in self._cache:
            if datetime.now().timestamp() - self._cache_time.get(key, 0) < ttl:
                return self._cache[key]
        
        data = fetcher()
        self._cache[key] = data
        self._cache_time[key] = datetime.now().timestamp()
        return data
    
    def get_fabric_health(self) -> FabricHealth:
        """Get overall fabric health summary"""
        health = FabricHealth()
        
        # Get device health
        devices = self.get_devices()
        health.total_devices = len(devices)
        
        for device in devices:
            status = device.health_status
            if status == "healthy":
                health.healthy_devices += 1
            elif status == "warning":
                health.warning_devices += 1
            elif status == "critical":
                health.critical_devices += 1
            
            if device.reachability != "reachable":
                health.unreachable_devices += 1
            
            health.total_tunnels += device.tunnels_total
            health.tunnels_up += device.tunnels_up
        
        health.tunnels_down = health.total_tunnels - health.tunnels_up
        
        # Get alarms
        alarms = self.get_alarms()
        health.total_alarms = len(alarms)
        for alarm in alarms:
            if alarm.severity == "Critical":
                health.critical_alarms += 1
            elif alarm.severity == "Major":
                health.major_alarms += 1
            elif alarm.severity == "Minor":
                health.minor_alarms += 1
        
        # Calculate SLA compliance
        if health.total_tunnels > 0:
            health.sla_compliance = (health.tunnels_up / health.total_tunnels) * 100
        
        health.last_updated = datetime.now()
        return health
    
    def get_devices(self) -> List[DeviceHealth]:
        """Get all device health information"""
        def fetch():
            devices = []
            raw_devices = self.api.get_devices()
            status_data = self.api.get_device_status()
            
            # Index status by device ID
            status_index = {s.get("deviceId"): s for s in status_data}
            
            for raw in raw_devices:
                device_id = raw.get("deviceId", raw.get("system-ip", ""))
                status = status_index.get(device_id, {})
                
                device = DeviceHealth(
                    device_id=device_id,
                    hostname=raw.get("host-name", raw.get("hostname", "Unknown")),
                    site_id=str(raw.get("site-id", "")),
                    status=raw.get("status", raw.get("reachability", "unknown")),
                    reachability=raw.get("reachability", "unknown"),
                    cpu_percent=float(status.get("cpuLoad", raw.get("cpu-load", 0)) or 0),
                    memory_percent=float(status.get("memUsage", raw.get("mem-usage", 0)) or 0),
                    disk_percent=float(status.get("diskUsage", raw.get("disk-usage", 0)) or 0),
                    control_connections=int(status.get("controlConnections", raw.get("controlConnections", 0)) or 0),
                    tunnels_up=int(status.get("omp-peers-up", raw.get("bfd-sessions-up", 0)) or 0),
                    tunnels_total=int(status.get("omp-peers", raw.get("bfd-sessions", 0)) or 0),
                    uptime=raw.get("uptime-date", raw.get("uptime", "")),
                    version=raw.get("version", ""),
                    model=raw.get("device-model", raw.get("model", "")),
                    board_serial=raw.get("board-serial", raw.get("serialNumber", ""))
                )
                devices.append(device)
            
            return devices
        
        return self._get_cached("devices", fetch)
    
    def get_device(self, device_id: str) -> Optional[DeviceHealth]:
        """Get single device health"""
        devices = self.get_devices()
        for device in devices:
            if device.device_id == device_id:
                return device
        return None
    
    def get_tunnels(self) -> List[TunnelHealth]:
        """Get tunnel health information"""
        def fetch():
            tunnels = []
            bfd_sessions = self.api.get_bfd_sessions()
            
            for bfd in bfd_sessions:
                tunnel = TunnelHealth(
                    source_ip=bfd.get("local-system-ip", bfd.get("src-ip", "")),
                    dest_ip=bfd.get("remote-system-ip", bfd.get("dst-ip", "")),
                    source_color=bfd.get("local-color", ""),
                    dest_color=bfd.get("remote-color", bfd.get("color", "")),
                    state=bfd.get("state", "unknown"),
                    source_site=str(bfd.get("site-id", "")),
                    dest_site=str(bfd.get("remote-site-id", "")),
                    latency_ms=float(bfd.get("average-latency", 0) or 0),
                    jitter_ms=float(bfd.get("average-jitter", 0) or 0),
                    loss_percent=float(bfd.get("loss", 0) or 0)
                )
                tunnels.append(tunnel)
            
            return tunnels
        
        return self._get_cached("tunnels", fetch)
    
    def get_alarms(self) -> List[Alarm]:
        """Get active alarms"""
        def fetch():
            alarms = []
            raw_alarms = self.api.get_active_alarms()
            
            for raw in raw_alarms:
                alarm = Alarm(
                    alarm_id=raw.get("uuid", ""),
                    severity=raw.get("severity", "Unknown"),
                    type=raw.get("type", ""),
                    rule_name=raw.get("ruleName", raw.get("rule-name-display", "")),
                    component=raw.get("component", ""),
                    device_id=raw.get("system-ip", ""),
                    hostname=raw.get("host-name", "Unknown"),
                    message=raw.get("message", raw.get("eventname", "")),
                    timestamp=datetime.fromtimestamp(raw.get("entry_time", 0) / 1000),
                    acknowledged=raw.get("acknowledged", False)
                )
                alarms.append(alarm)
            
            return alarms
        
        return self._get_cached("alarms", fetch, ttl=15)
    
    def acknowledge_alarm(self, alarm_id: str) -> bool:
        """Acknowledge an alarm"""
        return self.api.acknowledge_alarm(alarm_id)


# =============================================================================
# FLASK APPLICATION
# =============================================================================

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global monitor instance
monitor: Optional[SDWANMonitor] = None
config: Optional[Config] = None


def init_monitor(config_file: str = "config.yaml"):
    """Initialize the monitor with configuration"""
    global monitor, config
    config = Config.from_file(config_file)
    app.secret_key = config.flask_secret
    
    monitor = SDWANMonitor(config)
    if not monitor.connect():
        logger.warning("Failed to connect to vManage - running in demo mode")


# HTML Template (embedded for single-file deployment)
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SD-WAN Health Monitor</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        .status-healthy { color: #22c55e; }
        .status-warning { color: #f59e0b; }
        .status-critical { color: #ef4444; }
        .bg-healthy { background-color: #22c55e; }
        .bg-warning { background-color: #f59e0b; }
        .bg-critical { background-color: #ef4444; }
        .pulse { animation: pulse 2s infinite; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    </style>
</head>
<body class="bg-gray-900 text-white min-h-screen">
    <nav class="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div class="flex items-center justify-between">
            <div class="flex items-center space-x-4">
                <h1 class="text-2xl font-bold">📊 SD-WAN Health Monitor</h1>
                <span id="connection-status" class="px-3 py-1 rounded-full text-sm bg-green-600">● Connected</span>
            </div>
            <div class="text-sm text-gray-400">
                Last updated: <span id="last-updated">--</span>
            </div>
        </div>
    </nav>
    
    <main class="container mx-auto px-6 py-8">
        <!-- Summary Cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div class="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <div class="text-gray-400 text-sm mb-2">DEVICES</div>
                <div class="text-4xl font-bold" id="total-devices">--</div>
                <div class="text-sm mt-2">
                    <span class="status-healthy">● <span id="healthy-devices">--</span> Healthy</span>
                    <span class="ml-2 status-critical">● <span id="critical-devices">--</span> Critical</span>
                </div>
            </div>
            <div class="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <div class="text-gray-400 text-sm mb-2">TUNNELS</div>
                <div class="text-4xl font-bold" id="total-tunnels">--</div>
                <div class="text-sm mt-2">
                    <span class="status-healthy">● <span id="tunnels-up">--</span> Up</span>
                    <span class="ml-2 status-critical">● <span id="tunnels-down">--</span> Down</span>
                </div>
            </div>
            <div class="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <div class="text-gray-400 text-sm mb-2">ALARMS</div>
                <div class="text-4xl font-bold" id="total-alarms">--</div>
                <div class="text-sm mt-2">
                    <span class="status-critical">● <span id="critical-alarms">--</span> Critical</span>
                    <span class="ml-2 status-warning">● <span id="major-alarms">--</span> Major</span>
                </div>
            </div>
            <div class="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <div class="text-gray-400 text-sm mb-2">SLA COMPLIANCE</div>
                <div class="text-4xl font-bold"><span id="sla-percent">--</span>%</div>
                <div class="w-full bg-gray-700 rounded-full h-2 mt-3">
                    <div id="sla-bar" class="bg-green-500 h-2 rounded-full" style="width: 0%"></div>
                </div>
            </div>
        </div>
        
        <!-- Device Table -->
        <div class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
            <div class="px-6 py-4 border-b border-gray-700 flex justify-between items-center">
                <h2 class="text-lg font-semibold">Device Health</h2>
                <input type="text" id="device-search" placeholder="Search devices..." 
                       class="bg-gray-700 border border-gray-600 rounded px-3 py-1 text-sm">
            </div>
            <div class="overflow-x-auto">
                <table class="w-full">
                    <thead class="bg-gray-750">
                        <tr class="text-left text-gray-400 text-sm">
                            <th class="px-6 py-3">Device</th>
                            <th class="px-6 py-3">Site</th>
                            <th class="px-6 py-3">Status</th>
                            <th class="px-6 py-3">CPU</th>
                            <th class="px-6 py-3">Memory</th>
                            <th class="px-6 py-3">Control</th>
                            <th class="px-6 py-3">Tunnels</th>
                        </tr>
                    </thead>
                    <tbody id="device-table">
                        <tr><td colspan="7" class="px-6 py-8 text-center text-gray-500">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Alarms Section -->
        <div class="mt-8 bg-gray-800 rounded-lg border border-gray-700">
            <div class="px-6 py-4 border-b border-gray-700">
                <h2 class="text-lg font-semibold">Active Alarms</h2>
            </div>
            <div id="alarms-list" class="divide-y divide-gray-700">
                <div class="px-6 py-4 text-gray-500">No active alarms</div>
            </div>
        </div>
    </main>
    
    <script>
        const socket = io();
        
        socket.on('connect', () => {
            document.getElementById('connection-status').innerHTML = '● Connected';
            document.getElementById('connection-status').className = 'px-3 py-1 rounded-full text-sm bg-green-600';
        });
        
        socket.on('disconnect', () => {
            document.getElementById('connection-status').innerHTML = '● Disconnected';
            document.getElementById('connection-status').className = 'px-3 py-1 rounded-full text-sm bg-red-600';
        });
        
        socket.on('health_update', (data) => {
            updateDashboard(data);
        });
        
        function updateDashboard(data) {
            // Update summary cards
            document.getElementById('total-devices').textContent = data.health.total_devices;
            document.getElementById('healthy-devices').textContent = data.health.healthy_devices;
            document.getElementById('critical-devices').textContent = data.health.critical_devices + data.health.unreachable_devices;
            document.getElementById('total-tunnels').textContent = data.health.total_tunnels;
            document.getElementById('tunnels-up').textContent = data.health.tunnels_up;
            document.getElementById('tunnels-down').textContent = data.health.tunnels_down;
            document.getElementById('total-alarms').textContent = data.health.total_alarms;
            document.getElementById('critical-alarms').textContent = data.health.critical_alarms;
            document.getElementById('major-alarms').textContent = data.health.major_alarms;
            document.getElementById('sla-percent').textContent = data.health.sla_compliance.toFixed(1);
            document.getElementById('sla-bar').style.width = data.health.sla_compliance + '%';
            
            // Update device table
            const tbody = document.getElementById('device-table');
            if (data.devices.length > 0) {
                tbody.innerHTML = data.devices.map(device => `
                    <tr class="border-b border-gray-700 hover:bg-gray-750">
                        <td class="px-6 py-4">
                            <div class="font-medium">${device.hostname}</div>
                            <div class="text-xs text-gray-500">${device.device_id}</div>
                        </td>
                        <td class="px-6 py-4">${device.site_id}</td>
                        <td class="px-6 py-4">
                            <span class="px-2 py-1 rounded-full text-xs ${getStatusClass(device.health_status)}">
                                ${device.status}
                            </span>
                        </td>
                        <td class="px-6 py-4">${getProgressBar(device.cpu_percent)}</td>
                        <td class="px-6 py-4">${getProgressBar(device.memory_percent)}</td>
                        <td class="px-6 py-4">${device.control_connections}/${device.control_connections_expected}</td>
                        <td class="px-6 py-4">${device.tunnels_up}/${device.tunnels_total}</td>
                    </tr>
                `).join('');
            }
            
            // Update alarms
            const alarmsList = document.getElementById('alarms-list');
            if (data.alarms.length > 0) {
                alarmsList.innerHTML = data.alarms.map(alarm => `
                    <div class="px-6 py-4 flex items-center justify-between">
                        <div class="flex items-center space-x-4">
                            <span class="w-3 h-3 rounded-full ${getSeverityBg(alarm.severity)}"></span>
                            <div>
                                <div class="font-medium">${alarm.hostname}: ${alarm.rule_name}</div>
                                <div class="text-sm text-gray-500">${alarm.message}</div>
                            </div>
                        </div>
                        <div class="text-sm text-gray-500">${alarm.severity}</div>
                    </div>
                `).join('');
            } else {
                alarmsList.innerHTML = '<div class="px-6 py-4 text-gray-500">No active alarms</div>';
            }
            
            document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();
        }
        
        function getStatusClass(status) {
            switch(status) {
                case 'healthy': return 'bg-green-600';
                case 'warning': return 'bg-yellow-600';
                case 'critical': return 'bg-red-600';
                default: return 'bg-gray-600';
            }
        }
        
        function getSeverityBg(severity) {
            switch(severity) {
                case 'Critical': return 'bg-red-500';
                case 'Major': return 'bg-orange-500';
                case 'Minor': return 'bg-yellow-500';
                default: return 'bg-blue-500';
            }
        }
        
        function getProgressBar(value) {
            const color = value > 90 ? 'bg-red-500' : value > 70 ? 'bg-yellow-500' : 'bg-green-500';
            return `
                <div class="flex items-center space-x-2">
                    <div class="w-16 bg-gray-700 rounded-full h-2">
                        <div class="${color} h-2 rounded-full" style="width: ${value}%"></div>
                    </div>
                    <span class="text-sm">${value.toFixed(0)}%</span>
                </div>
            `;
        }
        
        // Initial load
        fetch('/api/health')
            .then(r => r.json())
            .then(data => {
                Promise.all([
                    fetch('/api/devices').then(r => r.json()),
                    fetch('/api/alarms').then(r => r.json())
                ]).then(([devices, alarms]) => {
                    updateDashboard({
                        health: data,
                        devices: devices.devices || [],
                        alarms: alarms.alarms || []
                    });
                });
            });
    </script>
</body>
</html>
'''


# =============================================================================
# ROUTES
# =============================================================================

@app.route('/')
def index():
    """Dashboard home page"""
    return DASHBOARD_HTML


@app.route('/api/health')
def api_health():
    """Get fabric health summary"""
    if monitor and monitor.connected:
        health = monitor.get_fabric_health()
        return jsonify(asdict(health))
    else:
        # Demo data
        return jsonify({
            "total_devices": 125,
            "healthy_devices": 120,
            "warning_devices": 3,
            "critical_devices": 1,
            "unreachable_devices": 1,
            "total_tunnels": 847,
            "tunnels_up": 842,
            "tunnels_down": 5,
            "total_alarms": 8,
            "critical_alarms": 1,
            "major_alarms": 2,
            "minor_alarms": 5,
            "sla_compliance": 98.5,
            "last_updated": datetime.now().isoformat()
        })


@app.route('/api/devices')
def api_devices():
    """Get all devices"""
    if monitor and monitor.connected:
        devices = monitor.get_devices()
        return jsonify({"devices": [asdict(d) for d in devices]})
    else:
        # Demo data
        demo_devices = [
            {"device_id": "10.1.1.1", "hostname": "DC-vEdge-01", "site_id": "100", "status": "reachable",
             "reachability": "reachable", "cpu_percent": 45, "memory_percent": 62, "disk_percent": 34,
             "control_connections": 2, "control_connections_expected": 2, "tunnels_up": 48, "tunnels_total": 48,
             "uptime": "45 days", "version": "20.9.3", "model": "vEdge-2000", "health_status": "healthy"},
            {"device_id": "10.1.1.2", "hostname": "DC-vEdge-02", "site_id": "100", "status": "reachable",
             "reachability": "reachable", "cpu_percent": 38, "memory_percent": 58, "disk_percent": 28,
             "control_connections": 2, "control_connections_expected": 2, "tunnels_up": 48, "tunnels_total": 48,
             "uptime": "45 days", "version": "20.9.3", "model": "vEdge-2000", "health_status": "healthy"},
            {"device_id": "10.2.1.1", "hostname": "BR-NYC-01", "site_id": "200", "status": "unreachable",
             "reachability": "unreachable", "cpu_percent": 0, "memory_percent": 0, "disk_percent": 0,
             "control_connections": 0, "control_connections_expected": 2, "tunnels_up": 0, "tunnels_total": 24,
             "uptime": "--", "version": "20.9.3", "model": "vEdge-1000", "health_status": "critical"},
            {"device_id": "10.2.1.2", "hostname": "BR-LAX-01", "site_id": "201", "status": "reachable",
             "reachability": "reachable", "cpu_percent": 94, "memory_percent": 82, "disk_percent": 45,
             "control_connections": 2, "control_connections_expected": 2, "tunnels_up": 24, "tunnels_total": 24,
             "uptime": "12 days", "version": "20.9.3", "model": "vEdge-1000", "health_status": "critical"},
        ]
        return jsonify({"devices": demo_devices})


@app.route('/api/devices/<device_id>')
def api_device(device_id: str):
    """Get single device"""
    if monitor and monitor.connected:
        device = monitor.get_device(device_id)
        if device:
            return jsonify(asdict(device))
        return jsonify({"error": "Device not found"}), 404
    return jsonify({"error": "Not connected"}), 503


@app.route('/api/tunnels')
def api_tunnels():
    """Get tunnel health"""
    if monitor and monitor.connected:
        tunnels = monitor.get_tunnels()
        return jsonify({"tunnels": [asdict(t) for t in tunnels]})
    return jsonify({"tunnels": []})


@app.route('/api/alarms')
def api_alarms():
    """Get active alarms"""
    if monitor and monitor.connected:
        alarms = monitor.get_alarms()
        return jsonify({"alarms": [asdict(a) for a in alarms]})
    else:
        # Demo data
        demo_alarms = [
            {"alarm_id": "1", "severity": "Critical", "type": "System", "rule_name": "Control Connection Down",
             "component": "Control", "device_id": "10.2.1.1", "hostname": "BR-NYC-01",
             "message": "Control connection to vSmart lost", "timestamp": datetime.now().isoformat(), "acknowledged": False},
            {"alarm_id": "2", "severity": "Major", "type": "System", "rule_name": "High CPU",
             "component": "CPU", "device_id": "10.2.1.2", "hostname": "BR-LAX-01",
             "message": "CPU utilization above 90%", "timestamp": datetime.now().isoformat(), "acknowledged": False},
        ]
        return jsonify({"alarms": demo_alarms})


@app.route('/api/alarms/<alarm_id>/ack', methods=['POST'])
def api_ack_alarm(alarm_id: str):
    """Acknowledge an alarm"""
    if monitor and monitor.connected:
        success = monitor.acknowledge_alarm(alarm_id)
        return jsonify({"success": success})
    return jsonify({"error": "Not connected"}), 503


# =============================================================================
# WEBSOCKET EVENTS
# =============================================================================

def background_monitor():
    """Background task to push updates via WebSocket"""
    while True:
        try:
            if monitor and monitor.connected:
                health = monitor.get_fabric_health()
                devices = monitor.get_devices()
                alarms = monitor.get_alarms()
                
                socketio.emit('health_update', {
                    'health': asdict(health),
                    'devices': [asdict(d) for d in devices],
                    'alarms': [asdict(a) for a in alarms]
                })
            
            time.sleep(config.refresh_interval if config else 60)
            
        except Exception as e:
            logger.error(f"Background monitor error: {e}")
            time.sleep(30)


@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    logger.info("Client connected")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    logger.info("Client disconnected")


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="SD-WAN Health Monitor Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Start dashboard:
    python sdwan_monitor.py --config config.yaml
    
  Debug mode:
    python sdwan_monitor.py --debug
    
  Custom port:
    python sdwan_monitor.py --port 8080

Author: Tamer Khalifa (CCIE #68867)
        """
    )
    
    parser.add_argument("--config", "-c", default="config.yaml", help="Configuration file")
    parser.add_argument("--host", "-H", default="0.0.0.0", help="Listen host")
    parser.add_argument("--port", "-p", type=int, default=5000, help="Listen port")
    parser.add_argument("--debug", "-d", action="store_true", help="Debug mode")
    
    args = parser.parse_args()
    
    # Initialize monitor
    init_monitor(args.config)
    
    # Start background monitor thread
    monitor_thread = Thread(target=background_monitor, daemon=True)
    monitor_thread.start()
    
    # Run Flask app
    host = args.host or (config.flask_host if config else "0.0.0.0")
    port = args.port or (config.flask_port if config else 5000)
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           SD-WAN Health Monitor Dashboard                    ║
╠══════════════════════════════════════════════════════════════╣
║  Dashboard URL: http://{host}:{port}                     ║
║  API Endpoint:  http://{host}:{port}/api/health          ║
║  vManage:       {config.vmanage_host if config else 'Not configured':40} ║
║  Status:        {'Connected' if (monitor and monitor.connected) else 'Demo Mode':40} ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    socketio.run(app, host=host, port=port, debug=args.debug)


if __name__ == "__main__":
    main()
