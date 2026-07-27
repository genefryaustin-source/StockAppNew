from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _safe_import(path,name):
    m=__import__(path,fromlist=[name]); return getattr(m,name)

class ForexCIPipeline:
    def run(self)->Dict[str,Any]:
        Center=_safe_import("modules.forex.forex_validation_center","ForexValidationCenter")
        return {"status":"completed","pipeline":"ci","started_at":_utc_now(),"validation":Center().run_full_validation()}
