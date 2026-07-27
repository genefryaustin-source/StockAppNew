"""
modules/forex/forex_quote_aggregator.py

Phase 16A -- Multi-source Forex quote aggregator.

Queries the five real FX quote providers directly (Polygon, Finnhub, Alpha
Vantage, TwelveData, Yahoo), normalizes whichever succeed, and returns a
consolidated best quote plus a per-provider breakdown.

Previously provider_quotes() never made a network call at all: each
provider's "price" was a fixed DEFAULT_QUOTES value nudged by a fake
hash(provider + pair)-derived drift, "latency_ms" was hash(provider) % 120,
and every provider always reported status "OK" -- so the "FALLBACK" path in
quote() could never actually trigger no matter what was configured. This
now calls each provider's real get_quote(pair), measures real wall-clock
latency, and honestly reports which providers returned a usable rate vs an
error (e.g. no API key configured, or a request failure).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import importlib
import time


_PROVIDER_MODULES = [
    ("modules.forex.providers.polygon_forex_provider", "Polygon"),
    ("modules.forex.providers.finnhub_forex_provider", "Finnhub"),
    ("modules.forex.providers.alpha_vantage_forex_provider", "AlphaVantage"),
    ("modules.forex.providers.twelvedata_forex_provider", "TwelveData"),
    ("modules.forex.providers.yahoo_forex_provider", "Yahoo"),
]


def normalize_pair(pair: Any) -> str:
    value = str(pair or "EUR/USD").replace("-", "/").replace("_", "/").upper().strip()
    if "/" not in value and len(value) == 6:
        value = value[:3] + "/" + value[3:]
    return value


class ForexQuoteAggregator:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def quote(self, pair: str = "EUR/USD") -> Dict[str, Any]:
        pair = normalize_pair(pair)
        provider_quotes = self.provider_quotes(pair)
        valid = [q for q in provider_quotes if q.get("status") == "OK" and q.get("mid") is not None]

        if valid:
            mids = [float(q["mid"]) for q in valid]
            mid = sum(mids) / len(mids)
            # These providers each return a single reference rate, not a
            # real bid/ask spread, so bid/ask here are estimated around the
            # aggregated live mid using a representative spread width --
            # not a fabricated price level.
            spread = 0.02 if "JPY" in pair else 0.00012
            bid = mid - spread / 2
            ask = mid + spread / 2
            status = "OK"
        else:
            mid = bid = ask = spread = None
            status = "NO_DATA"

        return {
            "status": status,
            "pair": pair,
            "bid": round(bid, 5) if bid is not None else None,
            "ask": round(ask, 5) if ask is not None else None,
            "mid": round(mid, 5) if mid is not None else None,
            "spread": round(spread, 5) if spread is not None else None,
            "provider_count": len(valid),
            "providers": provider_quotes,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": None if valid else "No configured provider returned a live rate for this pair.",
        }

    def provider_quotes(self, pair: str) -> List[Dict[str, Any]]:
        rows = []
        for module_path, label in _PROVIDER_MODULES:
            start = time.perf_counter()
            try:
                module = importlib.import_module(module_path)
                result = module.get_quote(pair)
            except Exception as exc:
                result = {"error": str(exc)}
            latency_ms = round((time.perf_counter() - start) * 1000, 2)

            if isinstance(result, dict) and not result.get("error") and result.get("mid") is not None:
                rows.append({
                    "provider": label,
                    "status": "OK",
                    "mid": result.get("mid"),
                    "last": result.get("last"),
                    "latency_ms": latency_ms,
                    "timestamp": result.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                })
            else:
                error = result.get("error") if isinstance(result, dict) else "Unknown error"
                rows.append({
                    "provider": label,
                    "status": "ERROR",
                    "mid": None,
                    "latency_ms": latency_ms,
                    "error": error,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        return rows


_AGG: Optional[ForexQuoteAggregator] = None


def get_forex_quote_aggregator(db: Optional[Any] = None) -> ForexQuoteAggregator:
    global _AGG
    if _AGG is None or (db is not None and _AGG.db is None):
        _AGG = ForexQuoteAggregator(db=db)
    return _AGG