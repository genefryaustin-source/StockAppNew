from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _safe_import(path,name):
    m=__import__(path,fromlist=[name]); return getattr(m,name)

class ForexQualityScoreEngine:
    def calculate(self,payload:Dict[str,Any])->Dict[str,Any]:
        score=float(payload.get("scorecard",{}).get("score",0))
        grade="A+" if score>=98 else "A" if score>=95 else "B" if score>=90 else "C"
        return {"status":"completed","score":score,"grade":grade,"calculated_at":_utc_now()}
