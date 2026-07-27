from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List

import pandas as pd
from sqlalchemy import text


@dataclass
class PortfolioRiskSummary:
    portfolio_id: str
    position_count: int
    total_market_value: float
    total_unrealized_pnl: float
    total_realized_pnl: float
    largest_position_symbol: str
    largest_position_pct: float
    max_sector: str
    max_sector_pct: float
    concentration_status: str
    risk_status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PortfolioRiskMonitor:
    """
    Portfolio-level risk monitoring for paper/live trading.

    Monitors:
        - Position concentration
        - Sector concentration
        - Unrealized P&L exposure
        - Realized P&L
        - Recommendation-linked exposure
        - Position sizing compliance
    """

    def __init__(self, db):
        self.db = db

    def build_summary(self, portfolio_id: str) -> PortfolioRiskSummary:
        positions = self.load_positions(portfolio_id)

        if positions.empty:
            return PortfolioRiskSummary(
                portfolio_id=portfolio_id,
                position_count=0,
                total_market_value=0.0,
                total_unrealized_pnl=0.0,
                total_realized_pnl=0.0,
                largest_position_symbol="—",
                largest_position_pct=0.0,
                max_sector="—",
                max_sector_pct=0.0,
                concentration_status="No Positions",
                risk_status="No Positions",
            )

        total_mv = float(positions["market_value"].fillna(0).sum())
        total_unrealized = float(positions["unrealized_pnl"].fillna(0).sum())
        total_realized = float(positions["realized_pnl"].fillna(0).sum())

        positions["position_pct"] = positions.apply(
            lambda r: (float(r.get("market_value") or 0) / total_mv * 100.0)
            if total_mv > 0 else 0.0,
            axis=1,
        )

        largest = positions.sort_values("position_pct", ascending=False).iloc[0]

        sector_df = self.sector_exposure(portfolio_id)
        if sector_df.empty:
            max_sector = "Unknown"
            max_sector_pct = 0.0
        else:
            top_sector = sector_df.sort_values("sector_pct", ascending=False).iloc[0]
            max_sector = str(top_sector.get("sector") or "Unknown")
            max_sector_pct = float(top_sector.get("sector_pct") or 0.0)

        largest_pct = float(largest.get("position_pct") or 0.0)

        concentration_status = self._classify_concentration(
            largest_position_pct=largest_pct,
            max_sector_pct=max_sector_pct,
        )

        risk_status = self._classify_risk(
            total_unrealized_pnl=total_unrealized,
            total_market_value=total_mv,
            largest_position_pct=largest_pct,
            max_sector_pct=max_sector_pct,
        )

        return PortfolioRiskSummary(
            portfolio_id=portfolio_id,
            position_count=len(positions),
            total_market_value=round(total_mv, 2),
            total_unrealized_pnl=round(total_unrealized, 2),
            total_realized_pnl=round(total_realized, 2),
            largest_position_symbol=str(largest.get("symbol") or "—"),
            largest_position_pct=round(largest_pct, 2),
            max_sector=max_sector,
            max_sector_pct=round(max_sector_pct, 2),
            concentration_status=concentration_status,
            risk_status=risk_status,
        )

    def load_positions(self, portfolio_id: str) -> pd.DataFrame:
        sql = text("""
            SELECT
                p.symbol,
                p.qty,
                p.avg_cost,
                p.market_price,
                p.market_value,
                p.unrealized_pnl,
                p.realized_pnl,
                COALESCE(r.sector, 'Unknown') AS sector,
                r.recommendation,
                r.conviction_score,
                r.confidence_score,
                r.risk_reward
            FROM portfolio_positions p
            LEFT JOIN LATERAL (
                SELECT
                    sector,
                    recommendation,
                    conviction_score,
                    confidence_score,
                    risk_reward
                FROM trade_recommendations r
                WHERE r.portfolio_id = p.portfolio_id
                  AND r.symbol = p.symbol
                ORDER BY r.created_at DESC
                LIMIT 1
            ) r ON TRUE
            WHERE p.portfolio_id = :pid
              AND p.qty > 0
            ORDER BY p.market_value DESC
        """)

        return pd.read_sql(sql, self.db.bind, params={"pid": portfolio_id})

    def sector_exposure(self, portfolio_id: str) -> pd.DataFrame:
        positions = self.load_positions(portfolio_id)

        if positions.empty:
            return pd.DataFrame()

        total_mv = float(positions["market_value"].fillna(0).sum())

        out = (
            positions.groupby("sector", dropna=False)
            .agg(
                positions=("symbol", "count"),
                market_value=("market_value", "sum"),
                unrealized_pnl=("unrealized_pnl", "sum"),
                realized_pnl=("realized_pnl", "sum"),
                avg_conviction=("conviction_score", "mean"),
                avg_confidence=("confidence_score", "mean"),
            )
            .reset_index()
        )

        out["sector_pct"] = out["market_value"].apply(
            lambda v: (float(v or 0) / total_mv * 100.0) if total_mv > 0 else 0.0
        )

        return out.sort_values("sector_pct", ascending=False)

    def concentration_breaches(
        self,
        portfolio_id: str,
        max_position_pct: float = 15.0,
        max_sector_pct: float = 30.0,
    ) -> pd.DataFrame:
        positions = self.load_positions(portfolio_id)

        if positions.empty:
            return pd.DataFrame()

        total_mv = float(positions["market_value"].fillna(0).sum())

        positions["position_pct"] = positions["market_value"].apply(
            lambda v: (float(v or 0) / total_mv * 100.0) if total_mv > 0 else 0.0
        )

        position_breaches = positions[
            positions["position_pct"] > float(max_position_pct)
        ].copy()

        sector_df = self.sector_exposure(portfolio_id)
        sector_breaches = sector_df[
            sector_df["sector_pct"] > float(max_sector_pct)
        ].copy() if not sector_df.empty else pd.DataFrame()

        rows: List[Dict[str, Any]] = []

        for _, r in position_breaches.iterrows():
            rows.append({
                "breach_type": "POSITION_CONCENTRATION",
                "symbol_or_sector": r.get("symbol"),
                "current_pct": round(float(r.get("position_pct") or 0.0), 2),
                "limit_pct": float(max_position_pct),
                "severity": "HIGH" if float(r.get("position_pct") or 0.0) >= max_position_pct * 1.5 else "MEDIUM",
                "message": f"{r.get('symbol')} exceeds max position concentration.",
            })

        for _, r in sector_breaches.iterrows():
            rows.append({
                "breach_type": "SECTOR_CONCENTRATION",
                "symbol_or_sector": r.get("sector"),
                "current_pct": round(float(r.get("sector_pct") or 0.0), 2),
                "limit_pct": float(max_sector_pct),
                "severity": "HIGH" if float(r.get("sector_pct") or 0.0) >= max_sector_pct * 1.5 else "MEDIUM",
                "message": f"{r.get('sector')} exceeds max sector concentration.",
            })

        return pd.DataFrame(rows)

    def recommendation_exposure(self, portfolio_id: str) -> pd.DataFrame:
        sql = text("""
            SELECT
                r.recommendation,
                COUNT(DISTINCT p.symbol) AS positions,
                SUM(p.market_value) AS market_value,
                SUM(p.unrealized_pnl) AS unrealized_pnl,
                AVG(r.conviction_score) AS avg_conviction,
                AVG(r.confidence_score) AS avg_confidence
            FROM portfolio_positions p
            LEFT JOIN LATERAL (
                SELECT
                    recommendation,
                    conviction_score,
                    confidence_score
                FROM trade_recommendations r
                WHERE r.portfolio_id = p.portfolio_id
                  AND r.symbol = p.symbol
                ORDER BY r.created_at DESC
                LIMIT 1
            ) r ON TRUE
            WHERE p.portfolio_id = :pid
              AND p.qty > 0
            GROUP BY r.recommendation
            ORDER BY market_value DESC
        """)

        return pd.read_sql(sql, self.db.bind, params={"pid": portfolio_id})

    def _classify_concentration(
        self,
        largest_position_pct: float,
        max_sector_pct: float,
    ) -> str:
        if largest_position_pct >= 25 or max_sector_pct >= 50:
            return "High Concentration"
        if largest_position_pct >= 15 or max_sector_pct >= 35:
            return "Moderate Concentration"
        return "Diversified"

    def _classify_risk(
        self,
        total_unrealized_pnl: float,
        total_market_value: float,
        largest_position_pct: float,
        max_sector_pct: float,
    ) -> str:
        pnl_pct = (
            total_unrealized_pnl / total_market_value * 100.0
            if total_market_value > 0 else 0.0
        )

        if pnl_pct <= -10 or largest_position_pct >= 25 or max_sector_pct >= 50:
            return "High Risk"
        if pnl_pct <= -5 or largest_position_pct >= 15 or max_sector_pct >= 35:
            return "Moderate Risk"
        return "Controlled"