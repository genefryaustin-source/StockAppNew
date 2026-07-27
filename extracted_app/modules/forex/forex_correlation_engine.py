"""
modules/forex/forex_correlation_engine.py

Phase 14B - Currency pair correlation engine.

Replaces the previous implementation, which derived every pairwise
"correlation" from hash(pair_a + pair_b) % 160 -- a deterministic number with
no relationship to actual FX prices. This version pulls real historical
closes for each pair (forex_history_service -> provider router -> live
market-data provider) and computes an actual pandas correlation matrix on
daily returns.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

PAIRS = ["EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD", "USD/JPY", "USD/CHF", "USD/CAD"]

DEFAULT_LOOKBACK_DAYS = 180
MIN_OBSERVATIONS = 5


def _load_return_frame(pairs: List[str], lookback_days: int):
    """
    Fetch real daily closes for `pairs` and return a wide DataFrame of
    closing prices indexed by date (columns = symbols with '/' stripped).
    Reuses forex_quant_research_engine's live-data-shape normalizer instead
    of re-implementing price-frame parsing.
    """
    import pandas as pd  # local import: keep this module importable even if pandas is briefly unavailable
    from modules.forex.forex_history_service import get_forex_history_service
    from modules.forex.forex_quant_research_engine import _extract_price_frame

    history_service = get_forex_history_service()
    start = history_service.default_start(days=lookback_days)
    end = history_service.default_end()

    market_data: Dict[str, Any] = {}
    errors: List[str] = []

    for pair in pairs:
        try:
            payload = history_service.fetch_from_router(
                pair,
                start_date=start,
                end_date=end,
                interval="1day",
            )
        except Exception as exc:
            errors.append(f"{pair}: {exc}")
            continue

        rows = payload.get("rows") if isinstance(payload, dict) else None
        if rows:
            market_data[pair.replace("/", "")] = rows
        else:
            err = payload.get("error") if isinstance(payload, dict) else None
            errors.append(f"{pair}: {err or 'no history rows returned'}")

    price_frame = _extract_price_frame(market_data, pairs=[p.replace("/", "") for p in pairs])
    return price_frame, errors


class ForexCorrelationEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def matrix(self, pairs: Optional[List[str]] = None, lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> Dict[str, Any]:
        pairs = pairs or PAIRS

        try:
            price_frame, errors = _load_return_frame(pairs, lookback_days)
        except Exception as exc:
            return {
                "status": "ERROR",
                "pairs": pairs,
                "matrix": [],
                "error": str(exc),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        if price_frame is None or price_frame.empty or price_frame.shape[0] < MIN_OBSERVATIONS:
            return {
                "status": "NO_DATA",
                "pairs": pairs,
                "matrix": [],
                "errors": errors,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        returns = price_frame.pct_change(fill_method=None).dropna(how="all")
        corr = returns.corr()

        rows = []
        for a in pairs:
            key_a = a.replace("/", "")
            row: Dict[str, Any] = {"pair": a}
            for b in pairs:
                key_b = b.replace("/", "")
                value = None
                if key_a in corr.columns and key_b in corr.index:
                    raw = corr.loc[key_b, key_a]
                    if raw == raw:  # filters NaN
                        value = round(float(raw), 2)
                row[b] = value
            rows.append(row)

        return {
            "status": "READY",
            "pairs": pairs,
            "matrix": rows,
            "lookback_days": lookback_days,
            "observations": int(returns.shape[0]),
            "errors": errors,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_CORR = None


def get_forex_correlation_engine(db: Optional[Any] = None, tenant_id=None, user_id=None, portfolio_id=None) -> ForexCorrelationEngine:
    global _CORR
    if _CORR is None or (db is not None and _CORR.db is None):
        _CORR = ForexCorrelationEngine(db=db)
    return _CORR