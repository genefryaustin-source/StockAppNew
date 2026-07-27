from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _safe_import(path,name):
    m=__import__(path,fromlist=[name]); return getattr(m,name)

class ForexDeploymentGate:
    def evaluate(self)->Dict[str,Any]:
        Validator=_safe_import("modules.forex.forex_release_validator","ForexReleaseValidator")
        result=Validator().validate()
        return {"status":"approved" if result.get("release_ready") else "blocked","result":result,"evaluated_at":_utc_now()}
