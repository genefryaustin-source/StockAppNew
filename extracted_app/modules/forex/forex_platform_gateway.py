"""
modules/forex/forex_platform_gateway.py

Single gateway for integrating the Forex Enterprise Platform into the
broader StockApp ecosystem.
"""

from __future__ import annotations
from datetime import datetime, timezone

from modules.forex.forex_enterprise_platform import get_forex_enterprise_platform


class ForexPlatformGateway:
    def __init__(self, db=None):
        self.db=db
        self.platform=get_forex_enterprise_platform(db=db)

    def startup(self):
        return self.platform.startup()

    def shutdown(self):
        return self.platform.shutdown()

    def health(self):
        return self.platform.health()

    def status(self):
        return self.platform.status()

    def snapshot(self):
        return self.platform.enterprise_snapshot()

    def validate(self):
        return self.platform.run_full_operational_check()

    def metadata(self):
        return {
            "component":"Forex Enterprise Platform",
            "gateway":"ForexPlatformGateway",
            "generated_at":datetime.now(timezone.utc).isoformat(),
        }

_GATEWAY=None

def get_forex_platform_gateway(db=None):
    global _GATEWAY
    if _GATEWAY is None or (db is not None and _GATEWAY.db is None):
        _GATEWAY=ForexPlatformGateway(db=db)
    return _GATEWAY
