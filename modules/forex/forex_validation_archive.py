from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _safe_import(path,name):
    m=__import__(path,fromlist=[name]); return getattr(m,name)

class ForexValidationArchive:
    def archive_latest(self)->Dict[str,Any]:
        Persistence=_safe_import("modules.forex.forex_validation_persistence","ForexValidationPersistence")
        latest=Persistence().latest_run()
        return {"status":"archived","record":latest,"archived_at":_utc_now()}
