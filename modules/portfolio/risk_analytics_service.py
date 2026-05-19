from __future__ import annotations

import math
import pandas as pd


class RiskAnalyticsService:
    def __init__(
        self,
        returns_df: pd.DataFrame | None = None,
        positions_df: pd.DataFrame | None = None,
    ):
        self.returns_df = returns_df.copy() if returns_df is not None else pd.DataFrame()
        self.positions_df = positions_df.copy() if positions_df is not None else pd.DataFrame()

    # -----------------------------
    # Portfolio VaR
    # -----------------------------
    def historical_var(self, confidence: float = 0.95) -> float:
        if self.returns_df.empty or "Return" not in self.returns_df.columns:
            return 0.0

        rets = self.returns_df["Return"].dropna()
        if rets.empty:
            return 0.0

        percentile = max(0.0, min(1.0, 1.0 - confidence))
        return float(-rets.quantile(percentile))

    def parametric_var(self, confidence_z: float = 1.65) -> float:
        if self.returns_df.empty or "Return" not in self.returns_df.columns:
            return 0.0

        rets = self.returns_df["Return"].dropna()
        if rets.empty:
            return 0.0

        mu = float(rets.mean())
        sigma = float(rets.std(ddof=0))
        var = -(mu - confidence_z * sigma)
        return float(max(var, 0.0))

    def expected_shortfall(self, confidence: float = 0.95) -> float:
        if self.returns_df.empty or "Return" not in self.returns_df.columns:
            return 0.0

        rets = self.returns_df["Return"].dropna()
        if rets.empty:
            return 0.0

        cutoff = rets.quantile(1.0 - confidence)
        tail = rets[rets <= cutoff]
        if tail.empty:
            return 0.0

        return float(-tail.mean())

    # -----------------------------
    # Exposure + concentration
    # -----------------------------
    def concentration_risk(self) -> dict:
        if self.positions_df.empty or "Market Value" not in self.positions_df.columns:
            return {
                "max_weight": 0.0,
                "hh_index": 0.0,
                "effective_n": 0.0,
            }

        df = self.positions_df.copy()
        total_mv = float(df["Market Value"].fillna(0.0).sum())

        if total_mv == 0:
            return {
                "max_weight": 0.0,
                "hh_index": 0.0,
                "effective_n": 0.0,
            }

        weights = (df["Market Value"].fillna(0.0) / total_mv).abs()
        hh_index = float((weights ** 2).sum())
        effective_n = float(1.0 / hh_index) if hh_index > 0 else 0.0

        return {
            "max_weight": float(weights.max()),
            "hh_index": hh_index,
            "effective_n": effective_n,
        }

    def position_risk_contribution(self) -> pd.DataFrame:
        if self.positions_df.empty or "Market Value" not in self.positions_df.columns:
            return pd.DataFrame()

        df = self.positions_df.copy()
        total_mv = float(df["Market Value"].fillna(0.0).sum())
        if total_mv == 0:
            return pd.DataFrame()

        df["Weight"] = df["Market Value"].fillna(0.0) / total_mv
        df["Abs Weight"] = df["Weight"].abs()
        total_abs = float(df["Abs Weight"].sum()) or 1.0
        df["Risk Contribution"] = df["Abs Weight"] / total_abs

        cols = [c for c in ["Symbol", "Market Value", "Weight", "Risk Contribution", "Unrealized P&L", "Realized P&L"] if c in df.columns]
        return df[cols].sort_values("Risk Contribution", ascending=False)

    # -----------------------------
    # Stress testing
    # -----------------------------
    def stress_test(self, scenarios: dict[str, float] | None = None) -> pd.DataFrame:
        if self.positions_df.empty or "Market Value" not in self.positions_df.columns:
            return pd.DataFrame()

        df = self.positions_df.copy()
        total_mv = float(df["Market Value"].fillna(0.0).sum())

        if scenarios is None:
            scenarios = {
                "Market Down 5%": -0.05,
                "Market Down 10%": -0.10,
                "Market Up 5%": 0.05,
            }

        rows = []
        for name, shock in scenarios.items():
            pnl = total_mv * float(shock)
            rows.append({
                "Scenario": name,
                "Shock": shock,
                "Estimated P&L Impact": pnl,
            })

        return pd.DataFrame(rows)

    # -----------------------------
    # Drawdown alerts
    # -----------------------------
    def drawdown_alert(self, threshold: float = -0.10) -> dict:
        if self.returns_df.empty or "Drawdown" not in self.returns_df.columns:
            return {"triggered": False, "current_drawdown": 0.0}

        current_dd = float(self.returns_df["Drawdown"].iloc[-1])
        return {
            "triggered": current_dd <= threshold,
            "current_drawdown": current_dd,
        }

    def volatility_regime(self) -> dict:
        if self.returns_df.empty or "Return" not in self.returns_df.columns:
            return {"daily_vol": 0.0, "annualized_vol": 0.0, "regime": "Unknown"}

        rets = self.returns_df["Return"].dropna()
        if rets.empty:
            return {"daily_vol": 0.0, "annualized_vol": 0.0, "regime": "Unknown"}

        daily_vol = float(rets.std(ddof=0))
        ann_vol = float(daily_vol * math.sqrt(252))

        if ann_vol < 0.10:
            regime = "Low"
        elif ann_vol < 0.25:
            regime = "Normal"
        else:
            regime = "High"

        return {
            "daily_vol": daily_vol,
            "annualized_vol": ann_vol,
            "regime": regime,
        }