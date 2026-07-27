from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _safe_import(path,name):
    m=__import__(path,fromlist=[name]); return getattr(m,name)

class ForexValidationServiceRegistry:
    def services(self)->Dict[str,Any]:
        return {"status":"online","services":["validation","scheduler","runtime","reporting","release"],"generated_at":_utc_now()}
