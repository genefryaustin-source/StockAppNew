"""
modules/trading_intelligence/trade_management_engine.py

Trade Lifecycle Management Engine

Purpose
-------
Monitors active positions against originating recommendations and
produces actionable trade management intelligence:

    OPEN
    CAUTION
    STOP_ALERT
    TARGET_HIT
    TRAILING_PROFIT
    CLOSED

Designed to sit on top of:

    trade_recommendations
    trade_orders
    trade_fills
    portfolio_positions
    closed_trades

No UI dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any

import pandas as pd
from sqlalchemy import text


# ============================================================
# MODELS
# ============================================================

@dataclass
class TradeManagementEvent:
    symbol: str
    portfolio_id: str

    status: str

    current_price: float
    entry_price: float

    stop_price: Optional[float]
    target_price: Optional[float]

    unrealized_pnl: float
    unrealized_pnl_pct: float

    risk_reward_current: Optional[float]

    days_held: float

    recommendation: str
    conviction_score: float
    confidence_score: float

    message: str

    def to_dict(self):
        return asdict(self)


# ============================================================
# ENGINE
# ============================================================

class TradeManagementEngine:

    def __init__(self, db):
        self.db = db

    # ========================================================
    # PUBLIC
    # ========================================================

    def get_trade_management_dashboard(
        self,
        portfolio_id: str,
    ) -> List[TradeManagementEvent]:

        positions = self._load_positions(portfolio_id)

        if positions.empty:
            return []

        recommendations = self._load_latest_recommendations(
            portfolio_id
        )

        current_prices = self._load_current_prices(
            positions["symbol"].tolist()
        )

        events: List[TradeManagementEvent] = []

        for _, pos in positions.iterrows():

            symbol = str(pos["symbol"]).upper()

            current_price = float(
                current_prices.get(symbol, 0.0) or 0.0
            )

            recommendation = recommendations.get(symbol)

            event = self._evaluate_position(
                portfolio_id=portfolio_id,
                symbol=symbol,
                position_row=pos,
                recommendation=recommendation,
                current_price=current_price,
            )

            events.append(event)

        return sorted(
            events,
            key=lambda x: (
                self._severity_rank(x.status),
                -x.unrealized_pnl_pct,
            ),
        )

    def get_trade_management_dataframe(
        self,
        portfolio_id: str,
    ) -> pd.DataFrame:

        events = self.get_trade_management_dashboard(
            portfolio_id
        )

        return pd.DataFrame(
            [e.to_dict() for e in events]
        )

    def get_summary_metrics(
        self,
        portfolio_id: str,
    ) -> Dict[str, Any]:

        events = self.get_trade_management_dashboard(
            portfolio_id
        )

        if not events:
            return {
                "open_positions": 0,
                "target_hits": 0,
                "stop_alerts": 0,
                "cautions": 0,
                "trailing_profit": 0,
            }

        return {
            "open_positions": len(events),
            "target_hits": len(
                [x for x in events if x.status == "TARGET_HIT"]
            ),
            "stop_alerts": len(
                [x for x in events if x.status == "STOP_ALERT"]
            ),
            "cautions": len(
                [x for x in events if x.status == "CAUTION"]
            ),
            "trailing_profit": len(
                [x for x in events if x.status == "TRAILING_PROFIT"]
            ),
        }

    # ========================================================
    # POSITION EVALUATION
    # ========================================================

    def _evaluate_position(
        self,
        portfolio_id: str,
        symbol: str,
        position_row,
        recommendation,
        current_price: float,
    ) -> TradeManagementEvent:

        qty = float(position_row.get("qty", 0))
        avg_cost = float(position_row.get("avg_cost", 0))

        updated_at = position_row.get("updated_at")

        stop_price = None
        target_price = None

        recommendation_label = "UNKNOWN"
        conviction = 0.0
        confidence = 0.0

        if recommendation:

            stop_price = recommendation.get(
                "stop_price"
            )

            target_price = recommendation.get(
                "target_price"
            )

            recommendation_label = recommendation.get(
                "recommendation",
                "UNKNOWN",
            )

            conviction = float(
                recommendation.get(
                    "conviction_score",
                    0,
                )
                or 0
            )

            confidence = float(
                recommendation.get(
                    "confidence_score",
                    0,
                )
                or 0
            )

        market_value = qty * current_price
        cost_basis = qty * avg_cost

        unrealized = market_value - cost_basis

        pnl_pct = 0.0

        if cost_basis > 0:
            pnl_pct = (
                unrealized / cost_basis
            ) * 100.0

        days_held = self._days_held(updated_at)

        rr_current = self._current_rr(
            current_price=current_price,
            stop_price=stop_price,
            target_price=target_price,
        )

        status, message = self._classify_trade(
            current_price=current_price,
            stop_price=stop_price,
            target_price=target_price,
            pnl_pct=pnl_pct,
        )

        return TradeManagementEvent(
            symbol=symbol,
            portfolio_id=portfolio_id,
            status=status,
            current_price=current_price,
            entry_price=avg_cost,
            stop_price=stop_price,
            target_price=target_price,
            unrealized_pnl=unrealized,
            unrealized_pnl_pct=pnl_pct,
            risk_reward_current=rr_current,
            days_held=days_held,
            recommendation=recommendation_label,
            conviction_score=conviction,
            confidence_score=confidence,
            message=message,
        )

    # ========================================================
    # CLASSIFICATION
    # ========================================================

    def _classify_trade(
        self,
        current_price: float,
        stop_price: Optional[float],
        target_price: Optional[float],
        pnl_pct: float,
    ):

        if stop_price and current_price <= stop_price:

            return (
                "STOP_ALERT",
                "Price breached stop level.",
            )

        if target_price and current_price >= target_price:

            return (
                "TARGET_HIT",
                "Target reached.",
            )

        if (
            stop_price
            and target_price
            and current_price > (
                stop_price +
                ((target_price - stop_price) * 0.75)
            )
        ):
            return (
                "TRAILING_PROFIT",
                "Protect gains. Consider trailing stop.",
            )

        if pnl_pct <= -5:

            return (
                "CAUTION",
                "Position under pressure.",
            )

        return (
            "OPEN",
            "Trade behaving normally.",
        )

    # ========================================================
    # HELPERS
    # ========================================================

    def _current_rr(
        self,
        current_price: float,
        stop_price: Optional[float],
        target_price: Optional[float],
    ) -> Optional[float]:

        if (
            stop_price is None
            or target_price is None
        ):
            return None

        risk = current_price - stop_price

        reward = target_price - current_price

        if risk <= 0:
            return None

        return round(reward / risk, 2)

    def _days_held(
        self,
        dt,
    ) -> float:

        if not dt:
            return 0.0

        try:

            if getattr(dt, "tzinfo", None):
                dt = dt.replace(tzinfo=None)

            return round(
                (
                    datetime.utcnow() - dt
                ).total_seconds() / 86400.0,
                2,
            )

        except Exception:
            return 0.0

    def _severity_rank(
        self,
        status: str,
    ):

        order = {
            "STOP_ALERT": 0,
            "TARGET_HIT": 1,
            "TRAILING_PROFIT": 2,
            "CAUTION": 3,
            "OPEN": 4,
        }

        return order.get(status, 99)

    # ========================================================
    # DATA ACCESS
    # ========================================================

    def _load_positions(
        self,
        portfolio_id: str,
    ) -> pd.DataFrame:

        sql = text("""
            SELECT
                symbol,
                qty,
                avg_cost,
                updated_at
            FROM portfolio_positions
            WHERE portfolio_id = :pid
              AND qty > 0
        """)

        return pd.read_sql(
            sql,
            self.db.bind,
            params={"pid": portfolio_id},
        )

    def _load_latest_recommendations(
        self,
        portfolio_id: str,
    ) -> Dict[str, Dict]:

        sql = text("""
            SELECT *
            FROM trade_recommendations
            WHERE portfolio_id = :pid
            ORDER BY created_at DESC
        """)

        df = pd.read_sql(
            sql,
            self.db.bind,
            params={"pid": portfolio_id},
        )

        results = {}

        for _, row in df.iterrows():

            symbol = str(
                row["symbol"]
            ).upper()

            if symbol not in results:
                results[symbol] = row.to_dict()

        return results

    def _load_current_prices(
        self,
        symbols: List[str],
    ) -> Dict[str, float]:

        if not symbols:
            return {}

        sql = text("""
            SELECT
                symbol,
                price
            FROM latest_prices
            WHERE symbol = ANY(:symbols)
        """)

        try:

            rows = self.db.execute(
                sql,
                {"symbols": symbols},
            ).fetchall()

            return {
                str(r.symbol).upper(): float(r.price)
                for r in rows
            }

        except Exception:

            return {}