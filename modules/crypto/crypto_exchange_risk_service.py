"""
modules/crypto/crypto_exchange_risk_service.py

Sprint CR-3: Exchange Intelligence -- Exchange Risk Scoring and
Liquidity Monitoring, both from CoinGecko's free, no-API-key-required
/exchanges endpoints.

Confirmed exact response fields from CoinGecko's own official docs:

  GET /exchanges -- returns id, name, year_established, country,
  trust_score, trust_score_rank, trade_volume_24h_btc for every
  actively-tracked exchange.

  GET /exchanges/{id}/tickers -- returns per-pair tickers including
  bid_ask_spread_percentage and cost_to_move_up_usd/
  cost_to_move_down_usd -- a genuine liquidity signal (how much it
  actually costs to move the price, and how tight the spread is), not
  a re-labeling of raw trading volume.

Reuses this app's own established CoinGecko call pattern
(modules/crypto/data_service.py's _cg_get()) rather than
reimplementing HTTP handling from scratch.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _cg_request(path: str, params: Optional[dict] = None) -> Optional[Any]:
    """
    Thin wrapper around this app's existing CoinGecko helper --
    reused directly rather than duplicated, so retry/backoff behavior
    stays in one place.
    """
    from modules.crypto.data_service import _cg_get
    return _cg_get(path, params)


def fetch_exchange_risk_scores(*, per_page: int = 250) -> Dict[str, Any]:
    """
    Real network call to CoinGecko's /exchanges endpoint -- cannot be
    executed or verified end-to-end from this sandbox
    (api.coingecko.com is outside the allowed fetch domains here,
    same caveat as CR-1/CR-2's external integrations). Response
    parsing below matches CoinGecko's own confirmed, current schema
    exactly.
    """
    try:
        payload = _cg_request("/exchanges", {"per_page": per_page, "page": 1})
        if payload is None:
            return {"status": "error", "message": "CoinGecko request failed or returned no data."}
        if not isinstance(payload, list):
            return {"status": "error", "message": f"Unexpected response shape: {type(payload)}"}

        rows = [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "trust_score": item.get("trust_score"),
                "trust_score_rank": item.get("trust_score_rank"),
                "trade_volume_24h_btc": item.get("trade_volume_24h_btc"),
                "country": item.get("country"),
                "year_established": item.get("year_established"),
            }
            for item in payload
            if isinstance(item, dict) and item.get("id")
        ]
        return {"status": "ok", "rows": rows}

    except Exception as exc:
        logger.warning("CoinGecko exchange risk score fetch failed: %s", exc)
        return {"status": "error", "message": str(exc)}


def fetch_exchange_liquidity(exchange_id: str) -> Dict[str, Any]:
    """
    Real network call to CoinGecko's /exchanges/{id}/tickers endpoint
    -- same sandbox limitation as fetch_exchange_risk_scores() above.
    """
    try:
        payload = _cg_request(f"/exchanges/{exchange_id}/tickers")
        if payload is None:
            return {"status": "error", "message": "CoinGecko request failed or returned no data."}

        tickers = payload.get("tickers") if isinstance(payload, dict) else None
        tickers = tickers if isinstance(tickers, list) else []

        rows = [
            {
                "base": t.get("base"),
                "target": t.get("target"),
                "bid_ask_spread_percentage": t.get("bid_ask_spread_percentage"),
                "cost_to_move_up_usd": t.get("cost_to_move_up_usd"),
                "cost_to_move_down_usd": t.get("cost_to_move_down_usd"),
                "volume": t.get("volume"),
            }
            for t in tickers if isinstance(t, dict)
        ]
        return {"status": "ok", "rows": rows}

    except Exception as exc:
        logger.warning("CoinGecko liquidity fetch failed for %s: %s", exchange_id, exc)
        return {"status": "error", "message": str(exc)}