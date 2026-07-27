from __future__ import annotations

import pandas as pd
from datetime import datetime, date

from models.trading import TradeOrder, PortfolioSnapshot


class GuardrailService:
    def __init__(self, db_session):
        self.db = db_session

    def current_drawdown(self, portfolio_id: int) -> float:
        snaps = (
            self.db.query(PortfolioSnapshot)
            .filter(PortfolioSnapshot.portfolio_id == portfolio_id)
            .order_by(PortfolioSnapshot.as_of.asc())
            .all()
        )

        if not snaps:
            return 0.0

        equities = [float(s.equity or 0.0) for s in snaps]
        if not equities:
            return 0.0

        peak = max(equities)
        current = equities[-1]

        if peak <= 0:
            return 0.0

        return float((current / peak) - 1.0)

    def orders_today(self, portfolio_id: int) -> int:
        today = date.today()
        orders = (
            self.db.query(TradeOrder)
            .filter(TradeOrder.portfolio_id == portfolio_id)
            .all()
        )

        count = 0
        for o in orders:
            created = getattr(o, "created_at", None)
            if created and created.date() == today:
                count += 1
        return count

    def gross_exposure(self, positions_df: pd.DataFrame) -> float:
        if positions_df is None or positions_df.empty or "Market Value" not in positions_df.columns:
            return 0.0

        mv = positions_df["Market Value"].fillna(0.0)
        long_exposure = float(mv[mv > 0].sum())
        short_exposure = float(abs(mv[mv < 0].sum()))
        return float(long_exposure + short_exposure)

    def max_position_weight(self, positions_df: pd.DataFrame) -> float:
        if positions_df is None or positions_df.empty or "Market Value" not in positions_df.columns:
            return 0.0

        total = float(positions_df["Market Value"].fillna(0.0).sum())
        if total == 0:
            return 0.0

        weights = (positions_df["Market Value"].fillna(0.0) / total).abs()
        return float(weights.max())

    def validate_rebalance_plan(
        self,
        portfolio_id: int,
        rebalance_df: pd.DataFrame,
        positions_df: pd.DataFrame,
        equity: float,
        config: dict,
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []

        max_drawdown = float(config.get("MAX_DRAWDOWN_HALT", -0.20))
        max_daily_orders = int(config.get("MAX_DAILY_ORDERS", 25))
        max_order_notional = float(config.get("MAX_ORDER_NOTIONAL", 50000))
        max_gross_exposure_mult = float(config.get("MAX_GROSS_EXPOSURE_MULT", 1.50))
        max_position_weight = float(config.get("MAX_POSITION_WEIGHT", 0.25))
        enable_live = bool(config.get("ENABLE_LIVE_TRADING", False))
        kill_switch = bool(config.get("KILL_SWITCH", False))

        if kill_switch:
            errors.append("Global kill switch is enabled")

        if not enable_live:
            errors.append("Live trading is disabled")

        dd = self.current_drawdown(portfolio_id)
        if dd <= max_drawdown:
            errors.append(f"Drawdown halt triggered ({dd:.2%})")

        todays_orders = self.orders_today(portfolio_id)
        projected_orders = todays_orders + (0 if rebalance_df is None else len(rebalance_df))
        if projected_orders > max_daily_orders:
            errors.append(f"Daily order limit exceeded ({projected_orders} > {max_daily_orders})")

        if rebalance_df is not None and not rebalance_df.empty:
            for _, row in rebalance_df.iterrows():
                notional = abs(float(row.get("Notional", 0.0)))
                if notional > max_order_notional:
                    errors.append(f"Order exceeds max notional: {row.get('Symbol')} (${notional:,.2f})")

        gross = self.gross_exposure(positions_df)
        if equity > 0 and (gross / equity) > max_gross_exposure_mult:
            errors.append(f"Gross exposure limit exceeded ({gross / equity:.2f}x)")

        mpw = self.max_position_weight(positions_df)
        if mpw > max_position_weight:
            errors.append(f"Max position weight exceeded ({mpw:.2%})")

        return (len(errors) == 0, errors)