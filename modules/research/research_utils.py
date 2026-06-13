
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any
import math
import random


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except Exception:
        return default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _ticker_seed(ticker: str) -> int:
    return sum(ord(c) for c in (ticker or '').upper()) or 1


def _stable_score(ticker: str, salt: int = 0, base: float = 50.0, spread: float = 20.0) -> float:
    seed = _ticker_seed(ticker) + salt * 997
    rnd = random.Random(seed)
    return round(_clamp(base + (rnd.random() - 0.5) * 2 * spread), 1)


def _safe_import(path: str, name: str):
    try:
        module = __import__(path, fromlist=[name])
        return getattr(module, name)
    except Exception:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
