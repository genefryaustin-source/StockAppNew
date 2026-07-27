"""
modules/forex/forex_volume_profile_engine.py

Real volume profile: buckets live historical OHLCV bars (via
forex_history_service -> provider router) by price level and sums each
bucket's real reported volume. Replaces the previous version, which
hardcoded a base price (1.0718) and fabricated every bucket's volume with
hash(pair + i) % 28 -- a deterministic fingerprint with no relationship to
any market data.

Note: spot FX has no consolidated tape, so "volume" as reported by these
providers is typically a tick/quote count rather than true traded notional.
That's a real, disclosed characteristic of the provider data -- not
something invented here. When a provider's bars carry no volume field at
all, bars are weighted equally instead, and this is reported honestly via
`note`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

NUM_BUCKETS = 20


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


class ForexVolumeProfileEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def profile(self, pair: str = "EUR/USD", interval: str = "1h") -> Dict[str, Any]:
        try:
            from modules.forex.forex_history_service import get_forex_history_service
            payload = get_forex_history_service().fetch_from_router(pair, interval=interval)
        except Exception as exc:
            return {
                "status": "ERROR",
                "pair": pair,
                "poc": None,
                "rows": [],
                "error": str(exc),
                "generated_at": _utc_iso(),
            }

        rows = payload.get("rows") if isinstance(payload, dict) else None
        if not rows:
            error = payload.get("error") if isinstance(payload, dict) else None
            return {
                "status": "NO_DATA",
                "pair": pair,
                "poc": None,
                "rows": [],
                "error": error or f"No live history returned for {pair} yet.",
                "generated_at": _utc_iso(),
            }

        bars: List[Dict[str, float]] = []
        for r in rows:
            close = _safe_float(r.get("close"))
            if close is None:
                continue
            high = _safe_float(r.get("high"), close)
            low = _safe_float(r.get("low"), close)
            volume = _safe_float(r.get("volume"), 0.0)
            bars.append({"high": high, "low": low, "close": close, "volume": volume or 0.0})

        if not bars:
            return {
                "status": "NO_DATA",
                "pair": pair,
                "poc": None,
                "rows": [],
                "error": "No usable bars in the live history payload.",
                "generated_at": _utc_iso(),
            }

        price_min = min(b["low"] for b in bars)
        price_max = max(b["high"] for b in bars)
        if price_max <= price_min:
            price_max = price_min + (price_min * 0.001 if price_min else 1.0)

        bucket_size = (price_max - price_min) / NUM_BUCKETS
        buckets = [0.0] * NUM_BUCKETS
        has_any_volume = any(b["volume"] for b in bars)

        for b in bars:
            idx = int((b["close"] - price_min) / bucket_size) if bucket_size else 0
            idx = max(0, min(NUM_BUCKETS - 1, idx))
            buckets[idx] += b["volume"] if has_any_volume else 1.0

        rows_out = []
        for i, vol in enumerate(buckets):
            price = round(price_min + (i + 0.5) * bucket_size, 5)
            rows_out.append({"price": price, "volume_m": round(vol, 2)})

        poc = max(rows_out, key=lambda r: r["volume_m"]) if rows_out else None

        return {
            "status": "READY" if has_any_volume else "READY_NO_VOLUME_FIELD",
            "pair": pair,
            "poc": poc,
            "rows": rows_out,
            "note": None if has_any_volume else (
                "The live provider did not return a volume field for this pair; "
                "bars are weighted equally instead of by real traded volume."
            ),
            "generated_at": _utc_iso(),
        }


_ENGINE: Optional[ForexVolumeProfileEngine] = None


def get_forex_volume_profile_engine(db: Optional[Any] = None) -> ForexVolumeProfileEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexVolumeProfileEngine(db=db)
    return _ENGINE