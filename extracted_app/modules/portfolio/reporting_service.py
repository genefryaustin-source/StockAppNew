from __future__ import annotations

import pandas as pd
from datetime import datetime, UTC


class ReportingService:
    def __init__(self):
        pass

    def build_portfolio_summary(self, totals: dict, health: dict) -> dict:
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "equity": float(totals.get("equity", 0.0)),
            "net_pnl": float(totals.get("net_pnl", 0.0)),
            "health_score": float(health.get("score", 0.0)),
            "regime": health.get("regime", "Unknown"),
        }

    def build_positions_report(self, df_pos: pd.DataFrame) -> pd.DataFrame:
        if df_pos is None or df_pos.empty:
            return pd.DataFrame()

        cols = [c for c in df_pos.columns if c.lower() in [
            "symbol", "qty", "market_price", "market_value", "unrealized_pnl"
        ]]
        return df_pos[cols].copy()

    def build_strategy_report(self, sleeve_df: pd.DataFrame) -> pd.DataFrame:
        if sleeve_df is None or sleeve_df.empty:
            return pd.DataFrame()

        return sleeve_df.copy()

    def build_trade_blotter(self, trades_df: pd.DataFrame) -> pd.DataFrame:
        if trades_df is None or trades_df.empty:
            return pd.DataFrame()

        return trades_df.copy()

    def build_risk_report(self, risk_df: pd.DataFrame | None) -> pd.DataFrame:
        if risk_df is None or risk_df.empty:
            return pd.DataFrame()
        return risk_df.copy()

    def export_bundle(
        self,
        summary: dict,
        positions: pd.DataFrame,
        strategies: pd.DataFrame,
        trades: pd.DataFrame,
        risk: pd.DataFrame,
    ) -> dict:
        return {
            "summary": summary,
            "positions": positions.to_dict(orient="records") if not positions.empty else [],
            "strategies": strategies.to_dict(orient="records") if not strategies.empty else [],
            "trades": trades.to_dict(orient="records") if not trades.empty else [],
            "risk": risk.to_dict(orient="records") if not risk.empty else [],
        }