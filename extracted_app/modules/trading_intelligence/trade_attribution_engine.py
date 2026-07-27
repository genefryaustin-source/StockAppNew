from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any

import pandas as pd
from sqlalchemy import text


@dataclass
class TradeAttributionSummary:
    linked_trades: int
    closed_linked_trades: int
    total_net_pnl: float
    avg_net_pnl: float
    win_rate: float
    best_signal: str
    best_sector: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TradeAttributionEngine:
    """
    Connects recommendations to executed orders, fills, and closed trades.

    Primary question answered:

        Which recommendations, signals, sectors, and conviction bands
        are actually producing profitable trades?
    """

    def __init__(self, db):
        self.db = db

    # -----------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------

    def build_summary(self, portfolio_id: str) -> TradeAttributionSummary:
        df = self.load_attribution_table(portfolio_id)

        if df.empty:
            return TradeAttributionSummary(
                linked_trades=0,
                closed_linked_trades=0,
                total_net_pnl=0.0,
                avg_net_pnl=0.0,
                win_rate=0.0,
                best_signal="—",
                best_sector="—",
            )

        linked = len(df)
        closed = len(df[df["net_pnl"].notna()])

        closed_df = df[df["net_pnl"].notna()].copy()

        total_net = float(closed_df["net_pnl"].sum()) if not closed_df.empty else 0.0
        avg_net = float(closed_df["net_pnl"].mean()) if not closed_df.empty else 0.0

        wins = len(closed_df[closed_df["net_pnl"] > 0])
        win_rate = (wins / len(closed_df) * 100.0) if len(closed_df) else 0.0

        signal_df = self.signal_attribution(portfolio_id)
        sector_df = self.sector_attribution(portfolio_id)

        best_signal = "—"
        if not signal_df.empty and "total_net_pnl" in signal_df.columns:
            best_signal = str(signal_df.sort_values("total_net_pnl", ascending=False).iloc[0]["signal"])

        best_sector = "—"
        if not sector_df.empty and "total_net_pnl" in sector_df.columns:
            best_sector = str(sector_df.sort_values("total_net_pnl", ascending=False).iloc[0]["sector"])

        return TradeAttributionSummary(
            linked_trades=linked,
            closed_linked_trades=closed,
            total_net_pnl=round(total_net, 2),
            avg_net_pnl=round(avg_net, 2),
            win_rate=round(win_rate, 2),
            best_signal=best_signal,
            best_sector=best_sector,
        )

    # -----------------------------------------------------
    # MAIN ATTRIBUTION TABLE
    # -----------------------------------------------------

    def load_attribution_table(self, portfolio_id: str) -> pd.DataFrame:
        sql = text("""
            SELECT
                r.id AS recommendation_id,
                r.created_at AS recommended_at,
                r.symbol,
                r.recommendation,
                r.conviction_score,
                r.confidence_score,
                r.risk_reward,
                r.sector,
                r.signal,
                r.entry_price AS recommended_entry,
                r.stop_price AS recommended_stop,
                r.target_price AS recommended_target,
                r.suggested_qty,
                r.executed,
                r.executed_order_id,

                o.id AS order_id,
                o.created_at AS ordered_at,
                o.side,
                o.qty AS order_qty,
                o.status AS order_status,
                o.avg_fill_price,
                o.filled_qty,

                c.closed_at,
                c.entry_price AS actual_entry,
                c.exit_price AS actual_exit,
                c.gross_pnl,
                c.net_pnl,
                c.holding_period_days,

                CASE
                    WHEN c.entry_price > 0
                    THEN ((c.exit_price - c.entry_price) / c.entry_price) * 100
                    ELSE NULL
                END AS return_pct,

                CASE
                    WHEN c.net_pnl > 0 THEN 'WIN'
                    WHEN c.net_pnl <= 0 THEN 'LOSS'
                    ELSE 'OPEN'
                END AS outcome

            FROM trade_recommendations r
            LEFT JOIN trade_orders o
                ON o.id = r.executed_order_id
            LEFT JOIN closed_trades c
                ON c.portfolio_id = r.portfolio_id
               AND c.symbol = r.symbol
               AND c.opened_at >= r.created_at - INTERVAL '2 days'
            WHERE r.portfolio_id = :pid
            ORDER BY r.created_at DESC
        """)

        return pd.read_sql(sql, self.db.bind, params={"pid": portfolio_id})

    # -----------------------------------------------------
    # SIGNAL ATTRIBUTION
    # -----------------------------------------------------

    def signal_attribution(self, portfolio_id: str) -> pd.DataFrame:
        df = self.load_attribution_table(portfolio_id)

        if df.empty:
            return pd.DataFrame()

        closed = df[df["net_pnl"].notna()].copy()

        if closed.empty:
            return pd.DataFrame()

        out = (
            closed.groupby("signal", dropna=False)
            .agg(
                trades=("symbol", "count"),
                wins=("net_pnl", lambda x: int((x > 0).sum())),
                losses=("net_pnl", lambda x: int((x <= 0).sum())),
                total_net_pnl=("net_pnl", "sum"),
                avg_net_pnl=("net_pnl", "mean"),
                avg_return_pct=("return_pct", "mean"),
                avg_conviction=("conviction_score", "mean"),
                avg_confidence=("confidence_score", "mean"),
            )
            .reset_index()
        )

        out["win_rate"] = out.apply(
            lambda r: round((r["wins"] / r["trades"]) * 100.0, 2)
            if r["trades"] else 0.0,
            axis=1,
        )

        return out.sort_values("total_net_pnl", ascending=False)

    # -----------------------------------------------------
    # SECTOR ATTRIBUTION
    # -----------------------------------------------------

    def sector_attribution(self, portfolio_id: str) -> pd.DataFrame:
        df = self.load_attribution_table(portfolio_id)

        if df.empty:
            return pd.DataFrame()

        closed = df[df["net_pnl"].notna()].copy()

        if closed.empty:
            return pd.DataFrame()

        out = (
            closed.groupby("sector", dropna=False)
            .agg(
                trades=("symbol", "count"),
                wins=("net_pnl", lambda x: int((x > 0).sum())),
                losses=("net_pnl", lambda x: int((x <= 0).sum())),
                total_net_pnl=("net_pnl", "sum"),
                avg_net_pnl=("net_pnl", "mean"),
                avg_return_pct=("return_pct", "mean"),
                avg_conviction=("conviction_score", "mean"),
                avg_confidence=("confidence_score", "mean"),
            )
            .reset_index()
        )

        out["win_rate"] = out.apply(
            lambda r: round((r["wins"] / r["trades"]) * 100.0, 2)
            if r["trades"] else 0.0,
            axis=1,
        )

        return out.sort_values("total_net_pnl", ascending=False)

    # -----------------------------------------------------
    # CONVICTION ATTRIBUTION
    # -----------------------------------------------------

    def conviction_band_attribution(self, portfolio_id: str) -> pd.DataFrame:
        df = self.load_attribution_table(portfolio_id)

        if df.empty:
            return pd.DataFrame()

        closed = df[df["net_pnl"].notna()].copy()

        if closed.empty:
            return pd.DataFrame()

        def band(v):
            try:
                v = float(v or 0)
            except Exception:
                v = 0.0

            if v >= 90:
                return "90+ Elite"
            if v >= 80:
                return "80-89 Strong"
            if v >= 75:
                return "75-79 Buy Zone"
            if v >= 70:
                return "70-74 Watch Zone"
            return "<70 Low Conviction"

        closed["conviction_band"] = closed["conviction_score"].apply(band)

        out = (
            closed.groupby("conviction_band")
            .agg(
                trades=("symbol", "count"),
                wins=("net_pnl", lambda x: int((x > 0).sum())),
                losses=("net_pnl", lambda x: int((x <= 0).sum())),
                total_net_pnl=("net_pnl", "sum"),
                avg_net_pnl=("net_pnl", "mean"),
                avg_return_pct=("return_pct", "mean"),
                avg_risk_reward=("risk_reward", "mean"),
            )
            .reset_index()
        )

        out["win_rate"] = out.apply(
            lambda r: round((r["wins"] / r["trades"]) * 100.0, 2)
            if r["trades"] else 0.0,
            axis=1,
        )

        return out.sort_values("conviction_band")

    # -----------------------------------------------------
    # OPEN RECOMMENDATION ATTRIBUTION
    # -----------------------------------------------------

    def open_recommendation_exposure(self, portfolio_id: str) -> pd.DataFrame:
        sql = text("""
            SELECT
                r.symbol,
                r.recommendation,
                r.conviction_score,
                r.confidence_score,
                r.risk_reward,
                r.sector,
                r.signal,
                r.executed,
                r.executed_order_id,
                p.qty,
                p.avg_cost,
                p.market_price,
                p.market_value,
                p.unrealized_pnl,
                p.realized_pnl
            FROM trade_recommendations r
            LEFT JOIN portfolio_positions p
                ON p.portfolio_id = r.portfolio_id
               AND p.symbol = r.symbol
            WHERE r.portfolio_id = :pid
              AND r.executed = TRUE
            ORDER BY r.created_at DESC
        """)

        return pd.read_sql(sql, self.db.bind, params={"pid": portfolio_id})