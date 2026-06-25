from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _safe_import(path,name):
    m=__import__(path,fromlist=[name]); return getattr(m,name)

class ForexValidationAlertEngine:
    def create_alert(self,message:str,severity:str="info")->Dict[str,Any]:
        return {"status":"created","severity":severity,"message":message,"created_at":_utc_now()}
