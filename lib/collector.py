"""
SD-WAN Health Monitor - Metrics Collector
Author: Tamer Khalifa (CCIE #68867)

Collects and caches metrics from vManage API.
"""

import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DeviceMetrics:
    hostname: str = ""
    system_ip: str = ""
    site_id: str = ""
    reachability: str = "unknown"
    model: str = ""
    version: str = ""
    cpu: float = 0.0
    memory: float = 0.0
    uptime: str = ""
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class TunnelMetrics:
    source_ip: str = ""
    dest_ip: str = ""
    color: str = ""
    state: str = "down"
    latency: float = 0.0
    loss: float = 0.0
    jitter: float = 0.0
    tx_rate: float = 0.0
    rx_rate: float = 0.0


class MetricsCollector:
    """Collects and caches SD-WAN metrics from vManage"""

    def __init__(self, api_client, cache_ttl: int = 60):
        self.api = api_client
        self.cache_ttl = cache_ttl
        self._device_cache: List[DeviceMetrics] = []
        self._tunnel_cache: List[TunnelMetrics] = []
        self._last_fetch: float = 0

    def _is_cache_valid(self) -> bool:
        return (time.time() - self._last_fetch) < self.cache_ttl

    def collect_devices(self, force: bool = False) -> List[DeviceMetrics]:
        """Collect device metrics from vManage"""
        if self._is_cache_valid() and not force:
            return self._device_cache

        try:
            raw_devices = self.api.get_device_status()
            self._device_cache = []

            for d in raw_devices:
                metrics = DeviceMetrics(
                    hostname=d.get("host-name", ""),
                    system_ip=d.get("system-ip", ""),
                    site_id=d.get("site-id", ""),
                    reachability=d.get("reachability", "unknown"),
                    model=d.get("device-model", ""),
                    version=d.get("version", ""),
                    cpu=float(d.get("cpu-load", 0)),
                    memory=float(d.get("mem-usage", 0)),
                    uptime=d.get("uptime-date", ""),
                )
                self._device_cache.append(metrics)

            self._last_fetch = time.time()
            logger.info(f"Collected metrics for {len(self._device_cache)} devices")

        except Exception as e:
            logger.error(f"Device collection failed: {e}")

        return self._device_cache

    def collect_tunnels(self, force: bool = False) -> List[TunnelMetrics]:
        """Collect tunnel metrics from vManage"""
        if self._is_cache_valid() and not force:
            return self._tunnel_cache

        try:
            raw_tunnels = self.api.get_tunnel_stats()
            self._tunnel_cache = []

            for t in raw_tunnels:
                metrics = TunnelMetrics(
                    source_ip=t.get("local-system-ip", ""),
                    dest_ip=t.get("remote-system-ip", ""),
                    color=t.get("local-color", ""),
                    state=t.get("state", "down"),
                    latency=float(t.get("latency", 0)),
                    loss=float(t.get("loss-percentage", 0)),
                    jitter=float(t.get("jitter", 0)),
                    tx_rate=float(t.get("tx-kbps", 0)) / 1000,
                    rx_rate=float(t.get("rx-kbps", 0)) / 1000,
                )
                self._tunnel_cache.append(metrics)

            logger.info(f"Collected metrics for {len(self._tunnel_cache)} tunnels")

        except Exception as e:
            logger.error(f"Tunnel collection failed: {e}")

        return self._tunnel_cache

    def get_health_summary(self) -> Dict:
        """Get overall health summary"""
        devices = self.collect_devices()
        tunnels = self.collect_tunnels()

        return {
            "total_devices": len(devices),
            "reachable": sum(1 for d in devices if d.reachability == "reachable"),
            "unreachable": sum(1 for d in devices if d.reachability != "reachable"),
            "active_tunnels": sum(1 for t in tunnels if t.state == "up"),
            "degraded_tunnels": sum(1 for t in tunnels if t.loss > 1 or t.latency > 100),
        }
