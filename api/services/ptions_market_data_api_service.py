"""
api/services/options_market_data_api_service.py

Options Market Data API Service

Backs GET /api/v1/options/chains/{symbol} and
GET /api/v1/options/greeks/{option_symbol}.

Not tenant-scoped -- like quotes/history, options chain and greeks data
is public market data, not a per-tenant resource.

get_chain wraps modules.options.options_data_service.get_options_chain,
which itself wraps a real provider-failover router (MarketData.app ->
Tradier -> Finnhub -> Yahoo) -- all provider logic stays there.

get_greeks combines two real, independent pieces: the option's spot
price and (if the provider supplies it) implied vol/greeks from the
same chain lookup, and an independently-computed Black-Scholes-Merton
Greeks calculation via modules.options.quantlib_greeks_engine (real
QuantLib, not an approximation) -- returning both rather than picking
one, so a caller can see whether they agree. If the provider doesn't
supply implied vol directly, it's backed out from the contract's own
market price first (quantlib_greeks_engine.implied_volatility), the
same two-step process the engine's own docstring describes.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _df_to_records(df: pd.DataFrame | None) -> list[dict]:
    if df is None or df.empty:
        return []
    clean = df.replace([np.inf, -np.inf], np.nan).where(pd.notnull(df), None)
    return clean.to_dict(orient="records")


class OptionsMarketDataAPIService:
    """API service for options chains and per-contract Greeks."""

    def __init__(self, db):
        # Not used -- chains/Greeks aren't tenant/db-scoped -- but the
        # module registry's loader always calls cls(db) uniformly
        # across every service.
        self.db = db

    # ---------------------------------------------------------
    # Chain
    # ---------------------------------------------------------

    def get_chain(
        self,
        *,
        symbol: str,
        expiration: str | None = None,
    ) -> dict[str, Any]:
        """
        Full options chain for an underlying, grouped by expiration
        (each with "calls" and "puts"). available=False (not an error)
        if no provider could return chain data for this symbol.
        """

        symbol = symbol.upper().strip()

        try:
            from modules.options.options_data_service import get_options_chain

            chain = get_options_chain(symbol)
        except Exception:
            logger.exception("Options chain lookup failed | %s", symbol)
            chain = None

        if not chain or chain.get("error"):
            return {
                "ticker": symbol,
                "available": False,
                "reason": (chain or {}).get("error") or "No options chain data available.",
            }

        raw_chain = chain.get("chain") or {}

        expirations = chain.get("expirations") or []
        if expiration:
            expirations = [e for e in expirations if e == expiration]
            raw_chain = {e: v for e, v in raw_chain.items() if e == expiration}

        chain_json = {
            expiry: {
                "calls": _df_to_records(data.get("calls")),
                "puts": _df_to_records(data.get("puts")),
            }
            for expiry, data in raw_chain.items()
        }

        return {
            "ticker": symbol,
            "available": True,
            "source": chain.get("source"),
            "contracts": sum(
                len(v["calls"]) + len(v["puts"]) for v in chain_json.values()
            ),
            "expirations": expirations,
            "chain": chain_json,
        }

    # ---------------------------------------------------------
    # Greeks
    # ---------------------------------------------------------

    def get_greeks(
        self,
        *,
        option_symbol: str,
    ) -> dict[str, Any]:
        """
        Spot, implied vol, and Greeks for a single option contract --
        both whatever the data provider supplied directly (if any) and
        an independently-computed Black-Scholes-Merton calculation via
        QuantLib, so a caller can see whether they agree.

        available=False (not an error) at any point this can't be
        completed: an unparseable symbol, no chain data for the
        underlying, the contract not found in the current chain, or no
        way to determine implied volatility.
        """

        option_symbol = option_symbol.upper().strip()

        from modules.options.options_portfolio_engine import parse_occ_symbol

        parsed = parse_occ_symbol(option_symbol)

        if not parsed.get("underlying"):
            return {
                "option_symbol": option_symbol,
                "available": False,
                "reason": (
                    "Could not parse option symbol. Expected OCC format, "
                    "e.g. AAPL250117C00150000."
                ),
            }

        try:
            from modules.options.options_data_service import get_options_chain

            chain = get_options_chain(parsed["underlying"])
        except Exception:
            logger.exception(
                "Chain lookup failed while computing Greeks | %s", option_symbol
            )
            chain = None

        if not chain or chain.get("error"):
            return {
                "option_symbol": option_symbol,
                "underlying": parsed["underlying"],
                "available": False,
                "reason": (chain or {}).get("error") or "No chain data available for this underlying.",
            }

        all_rows = chain.get("all_rows")
        if all_rows is None or all_rows.empty or "option_symbol" not in all_rows.columns:
            return {
                "option_symbol": option_symbol,
                "underlying": parsed["underlying"],
                "available": False,
                "reason": "No chain data available for this underlying.",
            }

        matches = all_rows[all_rows["option_symbol"].astype(str).str.upper() == option_symbol]
        if matches.empty:
            return {
                "option_symbol": option_symbol,
                "underlying": parsed["underlying"],
                "available": False,
                "reason": "This contract was not found in the current chain.",
            }

        row = matches.iloc[0]

        spot = row.get("underlying_price")
        provider_iv = row.get("iv")
        market_price = row.get("mid") if row.get("mid") else row.get("last")

        if spot is None or (isinstance(spot, float) and np.isnan(spot)):
            return {
                "option_symbol": option_symbol,
                "underlying": parsed["underlying"],
                "available": False,
                "reason": "No underlying spot price available for this contract.",
            }

        spot = float(spot)

        try:
            expiry_date = datetime.strptime(parsed["expiry"], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return {
                "option_symbol": option_symbol,
                "underlying": parsed["underlying"],
                "available": False,
                "reason": "Could not parse this contract's expiration date.",
            }

        iv = float(provider_iv) if provider_iv and not pd.isna(provider_iv) and float(provider_iv) > 0 else None

        from modules.options.quantlib_greeks_engine import compute_greeks, implied_volatility

        if iv is None and market_price and not pd.isna(market_price) and float(market_price) > 0:
            iv = implied_volatility(
                market_price=float(market_price),
                spot=spot,
                strike=parsed["strike"],
                expiry=expiry_date,
                option_type=parsed["option_type"],
            )

        if iv is None or iv <= 0:
            return {
                "option_symbol": option_symbol,
                "underlying": parsed["underlying"],
                "available": False,
                "reason": "Could not determine implied volatility for this contract.",
            }

        computed = compute_greeks(
            spot=spot,
            strike=parsed["strike"],
            expiry=expiry_date,
            option_type=parsed["option_type"],
            implied_vol=iv,
        )

        provider_greeks = None
        provider_fields = {
            "delta": row.get("delta"),
            "gamma": row.get("gamma"),
            "theta": row.get("theta"),
            "vega": row.get("vega"),
        }
        if any(v is not None and not pd.isna(v) for v in provider_fields.values()):
            provider_greeks = {
                k: (float(v) if v is not None and not pd.isna(v) else None)
                for k, v in provider_fields.items()
            }

        return {
            "option_symbol": option_symbol,
            "underlying": parsed["underlying"],
            "expiry": parsed["expiry"],
            "option_type": parsed["option_type"],
            "strike": parsed["strike"],
            "spot": spot,
            "implied_vol": iv,
            "available": True,
            "computed_greeks": computed.to_dict(),
            "provider_greeks": provider_greeks,
        }