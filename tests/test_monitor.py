"""
SD-WAN Health Monitor - Unit Tests
Author: Tamer Khalifa (CCIE #68867)
Run: python -m pytest tests/test_monitor.py -v
"""

import unittest
from unittest.mock import MagicMock, patch
from lib.collector import MetricsCollector, DeviceMetrics, TunnelMetrics
from lib.alerter import AlertManager, Alert


class TestMetricsCollector(unittest.TestCase):
    """Test MetricsCollector class"""

    def setUp(self):
        self.mock_api = MagicMock()
        self.collector = MetricsCollector(self.mock_api, cache_ttl=0)

    def test_collect_devices_returns_list(self):
        self.mock_api.get_device_status.return_value = [
            {"host-name": "router-01", "system-ip": "10.0.0.1",
             "reachability": "reachable", "cpu-load": 45, "mem-usage": 60}
        ]
        devices = self.collector.collect_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].hostname, "router-01")
        self.assertEqual(devices[0].cpu, 45.0)

    def test_collect_devices_handles_empty(self):
        self.mock_api.get_device_status.return_value = []
        devices = self.collector.collect_devices()
        self.assertEqual(len(devices), 0)

    def test_health_summary(self):
        self.mock_api.get_device_status.return_value = [
            {"host-name": "r1", "reachability": "reachable", "cpu-load": 10, "mem-usage": 20},
            {"host-name": "r2", "reachability": "unreachable", "cpu-load": 0, "mem-usage": 0},
        ]
        self.mock_api.get_tunnel_stats.return_value = []
        summary = self.collector.get_health_summary()
        self.assertEqual(summary["total_devices"], 2)
        self.assertEqual(summary["reachable"], 1)
        self.assertEqual(summary["unreachable"], 1)


class TestAlertManager(unittest.TestCase):
    """Test AlertManager class"""

    def setUp(self):
        self.thresholds = {
            "cpu": {"warning": 70, "critical": 90},
            "memory": {"warning": 75, "critical": 90},
            "tunnel_loss": {"warning": 1.0, "critical": 5.0},
            "tunnel_latency": {"warning": 100, "critical": 300},
        }
        self.alerter = AlertManager(self.thresholds)

    def test_cpu_critical_alert(self):
        device = DeviceMetrics(hostname="test-router", cpu=95.0, memory=50.0, reachability="reachable")
        alerts = self.alerter.evaluate_device(device)
        critical = [a for a in alerts if a.severity == "critical" and a.metric == "cpu"]
        self.assertEqual(len(critical), 1)

    def test_no_alert_normal_metrics(self):
        device = DeviceMetrics(hostname="test-router", cpu=30.0, memory=40.0, reachability="reachable")
        alerts = self.alerter.evaluate_device(device)
        self.assertEqual(len(alerts), 0)

    def test_unreachable_alert(self):
        device = DeviceMetrics(hostname="test-router", cpu=0, memory=0, reachability="unreachable")
        alerts = self.alerter.evaluate_device(device)
        self.assertTrue(any(a.metric == "reachability" for a in alerts))

    def test_tunnel_loss_alert(self):
        tunnel = TunnelMetrics(source_ip="10.0.0.1", dest_ip="10.0.0.2", loss=8.0, latency=50)
        alerts = self.alerter.evaluate_tunnel(tunnel)
        self.assertTrue(any(a.metric == "tunnel_loss" for a in alerts))

    def test_get_active_alerts(self):
        device = DeviceMetrics(hostname="test-router", cpu=95.0, memory=95.0, reachability="unreachable")
        self.alerter.evaluate_device(device)
        active = self.alerter.get_active_alerts()
        self.assertTrue(len(active) > 0)


if __name__ == "__main__":
    unittest.main()
