"""
modules/forex/forex_platform_service.py

Canonical application service for the Forex Enterprise Platform.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from modules.forex.forex_platform_gateway import get_forex_platform_gateway


class ForexPlatformService:
    def __init__(self, db=None):
        self.db=db
        self.gateway=get_forex_platform_gateway(db=db)
        self._initialized=False

    def initialize(self)->Dict[str,Any]:
        self._initialized=True
        return {
            "status":"INITIALIZED",
            "timestamp":datetime.now(timezone.utc).isoformat(),
        }

    def startup(self): return self.gateway.startup()
    def shutdown(self): return self.gateway.shutdown()
    def health(self): return self.gateway.health()
    def status(self): return self.gateway.status()
    def snapshot(self): return self.gateway.snapshot()
    def validate(self): return self.gateway.validate()

    def deploy_staging(self):
        return self.gateway.platform.deploy_staging()

    def deploy_production(self):
        return self.gateway.platform.deploy_production()

    def rollback(self,deployment_id:Optional[str]=None,reason:str=""):
        return self.gateway.platform.rollback(deployment_id=deployment_id,reason=reason)

    def metadata(self)->Dict[str,Any]:
        return {
            "service":"ForexPlatformService",
            "gateway":"ForexPlatformGateway",
            "initialized":self._initialized,
            "generated_at":datetime.now(timezone.utc).isoformat(),
        }


_SERVICE:Optional[ForexPlatformService]=None

def get_forex_platform_service(db=None)->ForexPlatformService:
    global _SERVICE
    if _SERVICE is None or (db is not None and _SERVICE.db is None):
        _SERVICE=ForexPlatformService(db=db)
    return _SERVICE
