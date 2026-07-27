from __future__ import annotations

import pandas as pd

from modules.portfolio.reporting_service import ReportingService


class PortfolioAPI:
    def __init__(self, db_session):
        self.db = db_session
        self.reporting = ReportingService()

    # ---------------------------------
    # CORE SNAPSHOT
    # ---------------------------------
    def get_portfolio_snapshot(
        self,
        portfolio_id: int,
        totals: dict,
        health: dict,
        df_pos: pd.DataFrame,
        sleeve_df: pd.DataFrame,
        trades_df: pd.DataFrame,
        risk_df: pd.DataFrame,
    ) -> dict:

        summary = self.reporting.build_portfolio_summary(totals, health)
        positions = self.reporting.build_positions_report(df_pos)
        strategies = self.reporting.build_strategy_report(sleeve_df)
        trades = self.reporting.build_trade_blotter(trades_df)
        risk = self.reporting.build_risk_report(risk_df)

        return {
            "portfolio_id": portfolio_id,
            "summary": summary,
            "positions": positions.to_dict(orient="records") if not positions.empty else [],
            "strategies": strategies.to_dict(orient="records") if not strategies.empty else [],
            "trades": trades.to_dict(orient="records") if not trades.empty else [],
            "risk": risk.to_dict(orient="records") if not risk.empty else [],
        }

    # ---------------------------------
    # LIGHTWEIGHT ENDPOINTS
    # ---------------------------------
    def get_positions(self, df_pos: pd.DataFrame) -> list:
        if df_pos is None or df_pos.empty:
            return []
        return df_pos.to_dict(orient="records")

    def get_strategies(self, sleeve_df: pd.DataFrame) -> list:
        if sleeve_df is None or sleeve_df.empty:
            return []
        return sleeve_df.to_dict(orient="records")

    def get_trades(self, trades_df: pd.DataFrame) -> list:
        if trades_df is None or trades_df.empty:
            return []
        return trades_df.to_dict(orient="records")

    def get_risk(self, risk_df: pd.DataFrame) -> list:
        if risk_df is None or risk_df.empty:
            return []
        return risk_df.to_dict(orient="records")