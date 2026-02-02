"""
SD-WAN Health Monitor - vManage API Client
Author: Tamer Khalifa (CCIE #68867)

Handles authentication and API interactions with Cisco vManage.
"""

import requests
import urllib3
import logging
from typing import Dict, List, Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)


class vManageAPI:
    """Cisco vManage REST API client"""

    def __init__(self, host: str, username: str, password: str,
                 port: int = 443, verify_ssl: bool = False):
        self.base_url = f"https://{host}:{port}"
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.authenticated = False

    def authenticate(self) -> bool:
        """Authenticate to vManage and get session token"""
        try:
            # Step 1: Get JSESSIONID
            login_url = f"{self.base_url}/j_security_check"
            payload = {"j_username": self.username, "j_password": self.password}
            resp = self.session.post(login_url, data=payload)

            if resp.status_code != 200 or "html" in resp.text.lower():
                logger.error("Authentication failed")
                return False

            # Step 2: Get XSRF token
            token_url = f"{self.base_url}/dataservice/client/token"
            resp = self.session.get(token_url)
            if resp.status_code == 200:
                self.session.headers["X-XSRF-TOKEN"] = resp.text.strip()

            self.authenticated = True
            logger.info(f"Authenticated to vManage: {self.base_url}")
            return True

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    def _get(self, endpoint: str) -> Optional[Dict]:
        """Make GET request to vManage API"""
        if not self.authenticated:
            self.authenticate()

        url = f"{self.base_url}/dataservice/{endpoint}"
        try:
            resp = self.session.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"API GET {endpoint} failed: {e}")
            return None

    def get_devices(self) -> List[Dict]:
        """Get all SD-WAN edge devices"""
        data = self._get("device")
        return data.get("data", []) if data else []

    def get_device_status(self) -> List[Dict]:
        """Get device status/health"""
        data = self._get("device/monitor")
        return data.get("data", []) if data else []

    def get_tunnel_stats(self) -> List[Dict]:
        """Get IPsec tunnel statistics"""
        data = self._get("tunnel/stats")
        return data.get("data", []) if data else []

    def get_interface_stats(self, device_id: str) -> List[Dict]:
        """Get interface statistics for a device"""
        data = self._get(f"device/interface?deviceId={device_id}")
        return data.get("data", []) if data else []

    def get_alarms(self, hours: int = 24) -> List[Dict]:
        """Get recent alarms"""
        data = self._get(f"alarms?query={{\"condition\":\"new\",\"size\":100}}")
        return data.get("data", []) if data else []

    def get_control_status(self) -> List[Dict]:
        """Get control connection status"""
        data = self._get("device/control/synced/connections")
        return data.get("data", []) if data else []

    def logout(self):
        """Logout from vManage"""
        try:
            self.session.get(f"{self.base_url}/logout")
            self.authenticated = False
        except:
            pass
