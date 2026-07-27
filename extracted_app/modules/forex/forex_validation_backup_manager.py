from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _safe_import(path,name):
    m=__import__(path,fromlist=[name]); return getattr(m,name)

class ForexValidationBackupManager:
    def backup(self)->Dict[str,Any]:
        P=_safe_import("modules.forex.forex_validation_persistence","ForexValidationPersistence")
        return {"status":"completed","snapshot":P().snapshot(),"backed_up_at":_utc_now()}
