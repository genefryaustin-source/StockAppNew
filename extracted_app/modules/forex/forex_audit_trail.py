from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _safe_import(path,name):
    m=__import__(path,fromlist=[name]); return getattr(m,name)

from pathlib import Path
import json
class ForexAuditTrail:
    def __init__(self,path:str="data/forex_validation/audit.jsonl"):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
    def record(self,event:Dict[str,Any])->Dict[str,Any]:
        event=dict(event); event.setdefault("timestamp",_utc_now())
        with self.path.open("a",encoding="utf-8") as f: f.write(json.dumps(event)+"\n")
        return event
