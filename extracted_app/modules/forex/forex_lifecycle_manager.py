"""
modules/forex/forex_lifecycle_manager.py

Coordinates the complete lifecycle of the Forex subsystem.
"""

from __future__ import annotations
from datetime import datetime, timezone

try:
    from modules.forex.forex_deployment_orchestrator import get_forex_deployment_orchestrator
except Exception:
    get_forex_deployment_orchestrator=None

try:
    from modules.forex.forex_runtime_manager import get_forex_runtime_manager
except Exception:
    get_forex_runtime_manager=None

class ForexLifecycleManager:

    def __init__(self, db=None):
        self.db=db
        self.runtime=get_forex_runtime_manager() if get_forex_runtime_manager else None
        self.deployer=get_forex_deployment_orchestrator(db=db) if get_forex_deployment_orchestrator else None

    def startup(self):
        runtime={}
        if self.runtime:
            try:
                self.runtime.start()
                runtime={"status":"STARTED"}
            except Exception as exc:
                runtime={"status":"ERROR","error":str(exc)}
        return {
            "timestamp":datetime.now(timezone.utc).isoformat(),
            "phase":"startup",
            "runtime":runtime,
        }

    def health(self):
        if self.runtime and hasattr(self.runtime,"status"):
            return self.runtime.status()
        return {"status":"UNKNOWN"}

    def deploy(self, production=False):
        if not self.deployer:
            return {"status":"UNAVAILABLE"}
        return self.deployer.deploy_production() if production else self.deployer.deploy_staging()

    def shutdown(self):
        if self.runtime and hasattr(self.runtime,"stop"):
            try:
                self.runtime.stop()
            except Exception:
                pass
        return {
            "timestamp":datetime.now(timezone.utc).isoformat(),
            "phase":"shutdown",
            "status":"STOPPED",
        }

_MANAGER=None

def get_forex_lifecycle_manager(db=None):
    global _MANAGER
    if _MANAGER is None or (db is not None and _MANAGER.db is None):
        _MANAGER=ForexLifecycleManager(db=db)
    return _MANAGER
