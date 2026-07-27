from __future__ import annotations

import logging

from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ForexWatchlistAI:
    """
    AI enrichment layer for Forex Watchlists.

    This class converts a simple watchlist into an
    institutional-quality trading watchlist by attaching
    live AI recommendations, account awareness, open
    positions, pending orders, and sizing information.

    No UI should call portfolio/recommendation engines
    directly. Instead, dashboards consume this class.
    """

    def __init__(

        self,

        *,

        portfolio_engine,

        recommendation_engine=None,

        order_engine=None,

        default_risk_pct: float = 1.0,

    ):

        self.default_risk_pct = default_risk_pct

        self.portfolio_engine = portfolio_engine
        self.recommendation_engine = recommendation_engine
        self.order_engine = order_engine

    # ==========================================================
    # Single Pair
    # ==========================================================

    def enrich_pair(
        self,
        *,
        pair: str,
        account_id: str,
    ) -> Dict[str, Any]:

        recommendation = {}

        try:

            recommendation = (
                self.portfolio_engine.recommend_position_from_signal(

                    account_id=account_id,

                    pair=pair,

                    risk_pct=self.default_risk_pct,

                )
            )
            print("=" * 100)
            print(f"PAIR: {pair}")
            print("RECOMMENDATION OBJECT")
            print(recommendation)
            print("=" * 100)


        except Exception as exc:

            print("=" * 100)

            print(f"FAILED FOR {pair}")

            print(type(exc).__name__)

            print(exc)

            print("=" * 100)

            logger.exception(exc)

        signal = recommendation.get(
            "signal",
            {},
        )

        sizing = recommendation.get(
            "sizing",
            {},
        )

        recommended_side = recommendation.get(
            "recommended_side"
        )

        can_open = recommendation.get(
            "can_open_position",
            False,
        )

        # ------------------------------------------------------
        # Open Position?
        # ------------------------------------------------------

        position_open = False

        pending_orders = 0

        try:

            positions = self.portfolio_engine.list_positions(

                account_id=account_id,

                status="OPEN",

            )

            position_open = any(

                p.pair.upper() == pair.upper()

                for p in positions

            )

        except Exception:

            pass

        # ------------------------------------------------------
        # Pending Orders
        # ------------------------------------------------------

        if self.order_engine is not None:

            try:

                orders = self.order_engine.load_open_orders(

                    account_id=account_id,

                )

                pending_orders = sum(

                    1

                    for order in orders

                    if str(
                        order.get(
                            "pair",
                            "",
                        )
                    ).upper() == pair.upper()

                )

            except Exception:

                pass

        return {

            "pair": pair,

            "recommendation": signal.get(

                "recommendation",

                "WATCH",

            ),

            "confidence": signal.get(

                "confidence",

                0,

            ),

            "entry_price": signal.get(

                "entry_price",

                0,

            ),

            "stop_price": signal.get(

                "stop_price",

                0,

            ),

            "target_price": signal.get(

                "target_price",

                0,

            ),

            "risk_reward": signal.get(

                "risk_reward",

                0,

            ),

            "trend_score": signal.get(

                "trend_score",

                0,

            ),

            "momentum_score": signal.get(

                "momentum_score",

                0,

            ),

            "volatility_score": signal.get(

                "volatility_score",

                0,

            ),

            "carry_score": signal.get(

                "carry_score",

                0,

            ),

            "liquidity_score": signal.get(

                "liquidity_score",

                0,

            ),

            "macro_score": signal.get(

                "macro_score",

                0,

            ),

            "composite_score": signal.get(

                "composite_score",

                0,

            ),

            "recommended_side": recommended_side,

            "can_open_position": can_open,

            "suggested_units": sizing.get(

                "suggested_units",

                0,

            ),

            "margin_required": sizing.get(

                "margin_required",

                0,

            ),

            "position_open": position_open,

            "pending_orders": pending_orders,

            "raw": recommendation,

        }

    # ==========================================================
    # Entire Watchlist
    # ==========================================================

    def enrich_watchlist(
        self,
        *,
        watchlist,
        account_id: str,
    ) -> List[Dict[str, Any]]:

        rows: List[Dict[str, Any]] = []

        for item in watchlist.items:

            try:

                row = self.enrich_pair(

                    pair=item.pair,

                    account_id=account_id,

                )
                print("=" * 80)
                print(item.pair)
                print(row)
                print("=" * 80)

            except Exception as exc:

                logger.exception(exc)

                row = {

                    "pair": item.pair,

                    "recommendation": "ERROR",

                    "confidence": 0,

                    "entry_price": 0,

                    "stop_price": 0,

                    "target_price": 0,

                    "risk_reward": 0,

                    "trend_score": 0,

                    "momentum_score": 0,

                    "volatility_score": 0,

                    "carry_score": 0,

                    "liquidity_score": 0,

                    "macro_score": 0,

                    "composite_score": 0,

                    "recommended_side": None,

                    "can_open_position": False,

                    "suggested_units": 0,

                    "margin_required": 0,

                    "position_open": False,

                    "pending_orders": 0,

                    "raw": {},

                }

            row["ai_enabled"] = item.ai_enabled

            row["alerts_enabled"] = item.alerts_enabled

            row["auto_trade_enabled"] = item.auto_trade_enabled

            row["notes"] = item.notes

            rows.append(row)

        rows.sort(

            key=lambda x: (

                x.get(

                    "confidence",

                    0,

                ),

                x.get(

                    "composite_score",

                    0,

                ),

            ),

            reverse=True,

        )

        return rows

    # ==========================================================
    # Summary
    # ==========================================================

    def summarize(
        self,
        *,
        rows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        return {

            "pair_count": len(rows),

            "buy_count": sum(

                r["recommendation"] == "BUY"

                for r in rows

            ),

            "sell_count": sum(

                r["recommendation"] == "SELL"

                for r in rows

            ),

            "watch_count": sum(

                r["recommendation"] == "WATCH"

                for r in rows

            ),

            "open_positions": sum(

                r["position_open"]

                for r in rows

            ),

            "pending_orders": sum(

                r["pending_orders"]

                for r in rows

            ),

            "average_confidence":

                round(

                    sum(

                        r["confidence"]

                        for r in rows

                    )

                    / max(

                        len(rows),

                        1,

                    ),

                    2,

                ),

        }