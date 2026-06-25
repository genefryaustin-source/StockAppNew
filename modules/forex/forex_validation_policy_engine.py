from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _safe_import(path,name):
    m=__import__(path,fromlist=[name]); return getattr(m,name)

class ForexValidationPolicyEngine:
    def evaluate(self,payload:Dict[str,Any])->Dict[str,Any]:
        score=float(payload.get("scorecard",{}).get("score",100))
        return {"status":"pass" if score>=95 else "fail","score":score,"evaluated_at":_utc_now()}
