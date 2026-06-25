from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _safe_import(path,name):
    m=__import__(path,fromlist=[name]); return getattr(m,name)

class ForexValidationPlatform:
    def status(self)->Dict[str,Any]:
        Bootstrap=_safe_import("modules.forex.forex_validation_bootstrap","ForexValidationBootstrap")
        Registry=_safe_import("modules.forex.forex_validation_registry","ForexValidationRegistry")
        return {"status":"online","bootstrap":Bootstrap().initialize(),"registry":Registry().components(),"checked_at":_utc_now()}
