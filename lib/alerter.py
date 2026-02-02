"""
SD-WAN Health Monitor - Alert Manager
Author: Tamer Khalifa (CCIE #68867)

Manages alert thresholds, notifications, and alert history.
"""

import json
import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    device: str
    severity: str           # critical, warning, info
    message: str
    metric: str = ""
    value: float = 0.0
    threshold: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class AlertManager:
    """Manages alerts and notifications"""

    def __init__(self, thresholds: Dict, notify_config: Dict = None):
        self.thresholds = thresholds
        self.notify_config = notify_config or {}
        self.active_alerts: List[Alert] = []
        self.alert_history: List[Alert] = []

    def evaluate_device(self, device) -> List[Alert]:
        """Evaluate device metrics against thresholds"""
        new_alerts = []

        # CPU check
        cpu_thresh = self.thresholds.get("cpu", {})
        if device.cpu >= cpu_thresh.get("critical", 90):
            new_alerts.append(Alert(
                device=device.hostname, severity="critical",
                message=f"CPU at {device.cpu}% (threshold: {cpu_thresh['critical']}%)",
                metric="cpu", value=device.cpu, threshold=cpu_thresh["critical"]
            ))
        elif device.cpu >= cpu_thresh.get("warning", 70):
            new_alerts.append(Alert(
                device=device.hostname, severity="warning",
                message=f"CPU at {device.cpu}% (threshold: {cpu_thresh['warning']}%)",
                metric="cpu", value=device.cpu, threshold=cpu_thresh["warning"]
            ))

        # Memory check
        mem_thresh = self.thresholds.get("memory", {})
        if device.memory >= mem_thresh.get("critical", 90):
            new_alerts.append(Alert(
                device=device.hostname, severity="critical",
                message=f"Memory at {device.memory}% (threshold: {mem_thresh['critical']}%)",
                metric="memory", value=device.memory, threshold=mem_thresh["critical"]
            ))
        elif device.memory >= mem_thresh.get("warning", 75):
            new_alerts.append(Alert(
                device=device.hostname, severity="warning",
                message=f"Memory at {device.memory}% (threshold: {mem_thresh['warning']}%)",
                metric="memory", value=device.memory, threshold=mem_thresh["warning"]
            ))

        # Reachability check
        if device.reachability != "reachable":
            new_alerts.append(Alert(
                device=device.hostname, severity="critical",
                message=f"Device unreachable (status: {device.reachability})",
                metric="reachability", value=0, threshold=1
            ))

        for alert in new_alerts:
            self.active_alerts.append(alert)
            self.alert_history.append(alert)
            self._send_notification(alert)

        return new_alerts

    def evaluate_tunnel(self, tunnel) -> List[Alert]:
        """Evaluate tunnel metrics against thresholds"""
        new_alerts = []
        tunnel_name = f"{tunnel.source_ip} -> {tunnel.dest_ip}"

        loss_thresh = self.thresholds.get("tunnel_loss", {})
        if tunnel.loss >= loss_thresh.get("critical", 5.0):
            new_alerts.append(Alert(
                device=tunnel_name, severity="critical",
                message=f"Tunnel loss at {tunnel.loss}%",
                metric="tunnel_loss", value=tunnel.loss
            ))

        latency_thresh = self.thresholds.get("tunnel_latency", {})
        if tunnel.latency >= latency_thresh.get("critical", 300):
            new_alerts.append(Alert(
                device=tunnel_name, severity="critical",
                message=f"Tunnel latency at {tunnel.latency}ms",
                metric="tunnel_latency", value=tunnel.latency
            ))

        for alert in new_alerts:
            self.active_alerts.append(alert)
            self._send_notification(alert)

        return new_alerts

    def _send_notification(self, alert: Alert):
        """Send alert notification via configured channels"""
        # Slack
        slack_cfg = self.notify_config.get("slack", {})
        if slack_cfg.get("enabled"):
            try:
                emoji = "🔴" if alert.severity == "critical" else "⚠️"
                payload = {
                    "channel": slack_cfg.get("channel", "#sdwan-alerts"),
                    "text": f"{emoji} *SD-WAN Alert* [{alert.severity.upper()}]\n"
                            f"Device: {alert.device}\n{alert.message}"
                }
                requests.post(slack_cfg["webhook_url"], json=payload, timeout=5)
            except Exception as e:
                logger.error(f"Slack notification failed: {e}")

    def get_active_alerts(self, limit: int = 50) -> List[Dict]:
        """Get active alerts sorted by timestamp"""
        sorted_alerts = sorted(self.active_alerts, key=lambda a: a.timestamp, reverse=True)
        return [a.to_dict() for a in sorted_alerts[:limit]]

    def acknowledge_alert(self, index: int):
        """Acknowledge an alert"""
        if 0 <= index < len(self.active_alerts):
            self.active_alerts[index].acknowledged = True

    def clear_acknowledged(self):
        """Clear all acknowledged alerts"""
        self.active_alerts = [a for a in self.active_alerts if not a.acknowledged]
