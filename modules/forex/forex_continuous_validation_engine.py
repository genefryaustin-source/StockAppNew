from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict

def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def _safe_import(path,name):
    m=__import__(path,fromlist=[name]); return getattr(m,name)

class ForexContinuousValidationEngine:
    def run_cycle(self, include_stress: bool=False)->Dict[str,Any]:
        Center=_safe_import("modules.forex.forex_validation_center","ForexValidationCenter")
        result=Center().run_full_validation(include_stress=include_stress)
        try:
            Center().save_history(result)
        except Exception:
            pass
        return {"status":"completed","cycle_completed_at":_utc_now(),"result":result}
