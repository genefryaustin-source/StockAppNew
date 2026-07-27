"""
modules/forex/forex_release_manager.py

Coordinates release readiness and deployment of the Forex subsystem.
"""

from __future__ import annotations
from datetime import datetime, timezone

try:
    from modules.forex.forex_production_readiness_suite import run_forex_production_readiness_suite
except Exception:
    run_forex_production_readiness_suite=None


class ForexReleaseManager:

    def __init__(self, db=None):
        self.db=db

    def preflight(self):
        if run_forex_production_readiness_suite is None:
            return {
                "status":"ERROR",
                "message":"Production readiness suite unavailable."
            }
        return run_forex_production_readiness_suite(db=self.db)

    def build_release_manifest(self):
        return {
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "module":"Forex",
            "version":"1.0.0",
            "artifacts":[
                "Analytics Engines",
                "Execution Engines",
                "Dashboards",
                "Validation Suites",
                "Production Readiness Suite",
            ]
        }

    def deploy(self):
        report=self.preflight()
        if report.get("production_status")!="READY_FOR_DEPLOYMENT":
            return {
                "status":"BLOCKED",
                "reason":"Preflight checks did not pass.",
                "preflight":report,
            }
        return {
            "status":"DEPLOYED",
            "timestamp":datetime.now(timezone.utc).isoformat(),
            "manifest":self.build_release_manifest(),
        }


_MANAGER=None

def get_forex_release_manager(db=None):
    global _MANAGER
    if _MANAGER is None:
        _MANAGER=ForexReleaseManager(db=db)
    return _MANAGER
