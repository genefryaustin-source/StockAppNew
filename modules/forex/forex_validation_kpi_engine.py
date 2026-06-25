from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _safe_import(path,name):
    m=__import__(path,fromlist=[name]); return getattr(m,name)

class ForexValidationKPIEngine:
    def compute(self,payload:Dict[str,Any])->Dict[str,Any]:
        card=payload.get("scorecard",{})
        return {"status":"completed","score":card.get("score",0),"grade":card.get("grade","N/A"),"generated_at":_utc_now()}
