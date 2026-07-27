"""
modules/forex/forex_operations_control_center.py

Unified operational control center for the Forex subsystem.
"""

from __future__ import annotations
from datetime import datetime, timezone

try:
    from modules.forex.forex_lifecycle_manager import get_forex_lifecycle_manager
except Exception:
    get_forex_lifecycle_manager=None

try:
    from modules.forex.forex_deployment_orchestrator import get_forex_deployment_orchestrator
except Exception:
    get_forex_deployment_orchestrator=None


class ForexOperationsControlCenter:

    def __init__(self, db=None):
        self.db=db
        self.lifecycle=get_forex_lifecycle_manager(db=db) if get_forex_lifecycle_manager else None
        self.deployment=get_forex_deployment_orchestrator(db=db) if get_forex_deployment_orchestrator else None

    def dashboard(self):
        return {
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "runtime": self.lifecycle.health() if self.lifecycle else {"status":"UNKNOWN"},
            "deployment": self.deployment.deployment_status() if self.deployment else {"status":"UNKNOWN"},
        }

    def startup(self):
        return self.lifecycle.startup() if self.lifecycle else {"status":"UNAVAILABLE"}

    def shutdown(self):
        return self.lifecycle.shutdown() if self.lifecycle else {"status":"UNAVAILABLE"}

    def deploy_staging(self):
        return self.deployment.deploy_staging() if self.deployment else {"status":"UNAVAILABLE"}

    def deploy_production(self):
        return self.deployment.deploy_production() if self.deployment else {"status":"UNAVAILABLE"}

_CENTER=None

def get_forex_operations_control_center(db=None):
    global _CENTER
    if _CENTER is None or (db is not None and _CENTER.db is None):
        _CENTER=ForexOperationsControlCenter(db=db)
    return _CENTER
