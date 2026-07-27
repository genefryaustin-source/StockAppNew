from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict

def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def _safe_import(path,name):
    m=__import__(path,fromlist=[name]); return getattr(m,name)

class ForexRegressionEngine:
    def compare(self)->Dict[str,Any]:
        History=_safe_import("modules.forex.forex_validation_history","ForexValidationHistory")
        rows=History().load(limit=2)
        if len(rows)<2:
            return {"status":"insufficient_history","history":rows}
        latest,previous=rows[-1],rows[-2]
        return {"status":"completed","latest":latest,"previous":previous,
                "score_delta":latest.get("score",0)-previous.get("score",0),
                "failed_delta":latest.get("failed",0)-previous.get("failed",0),
                "completed_at":_utc_now()}
