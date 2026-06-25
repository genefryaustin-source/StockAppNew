from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict

def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def _safe_import(path,name):
    m=__import__(path,fromlist=[name]); return getattr(m,name)

class ForexPredeploymentValidator:
    def run(self)->Dict[str,Any]:
        Release=_safe_import("modules.forex.forex_release_validator","ForexReleaseValidator")
        Regression=_safe_import("modules.forex.forex_regression_engine","ForexRegressionEngine")
        rel=Release().validate()
        reg=Regression().compare()
        return {"status":"pass" if rel.get("release_ready") else "fail",
                "release":rel,
                "regression":reg,
                "completed_at":_utc_now()}
