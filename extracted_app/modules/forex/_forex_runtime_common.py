from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional
import json, math, os

def utcnow(): return datetime.now(timezone.utc)
def iso(dt: Optional[datetime] = None) -> str: return (dt or utcnow()).isoformat()
def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None: return default
        value = float(value)
        if math.isnan(value) or math.isinf(value): return default
        return value
    except Exception: return default
def dumps(value: Any) -> str:
    try: return json.dumps(value, default=str)
    except Exception: return json.dumps({'unserializable': str(value)})
def loads(value: Any, default: Any = None) -> Any:
    try:
        if value is None: return default
        if isinstance(value, (dict, list)): return value
        return json.loads(value)
    except Exception: return default
DEFAULT_DB_PATH = os.getenv('FOREX_RUNTIME_DB', 'forex_runtime.sqlite3')
