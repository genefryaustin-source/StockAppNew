from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _safe_import(path,name):
    m=__import__(path,fromlist=[name]); return getattr(m,name)

class ForexValidationReleaseManager:
    def approve(self)->Dict[str,Any]:
        Gate=_safe_import("modules.forex.forex_deployment_gate","ForexDeploymentGate")
        return Gate().evaluate()
