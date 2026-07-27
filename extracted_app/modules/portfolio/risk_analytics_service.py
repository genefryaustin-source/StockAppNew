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

    def _portfolio_returns(self) -> pd.Series:

        if self.returns_df.empty:
            return pd.Series(dtype=float)

        #
        # Legacy single-column format
        #
        if "Return" in self.returns_df.columns:
            return (
                pd.to_numeric(
                    self.returns_df["Return"],
                    errors="coerce",
                )
                .dropna()
            )

        #
        # Multi-asset format
        #
        numeric = (
            self.returns_df
            .apply(
                pd.to_numeric,
                errors="coerce",
            )
        )

        if numeric.empty:
            return pd.Series(dtype=float)

        #
        # Equal-weight portfolio return
        #
        return (
            numeric
            .mean(axis=1)
            .dropna()
        )
    # -----------------------------
    # Portfolio VaR
    # -----------------------------
    def historical_var(self, confidence: float = 0.95) -> float:
        rets = self._portfolio_returns()

        if rets.empty:
            return 0.0


        percentile = max(0.0, min(1.0, 1.0 - confidence))
        return float(-rets.quantile(percentile))

    def parametric_var(self, confidence_z: float = 1.65) -> float:
        rets = self._portfolio_returns()

        if rets.empty:
            return 0.0


        mu = float(rets.mean())
        sigma = float(rets.std(ddof=0))
        var = -(mu - confidence_z * sigma)
        return float(max(var, 0.0))

    def expected_shortfall(self, confidence: float = 0.95) -> float:
        rets = self._portfolio_returns()

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

        rets = self._portfolio_returns()

        if rets.empty:
            return {
                "triggered": False,
                "current_drawdown": 0.0,
            }

        equity = (1 + rets).cumprod()
        running_max = equity.cummax()
        drawdown = (equity / running_max) - 1.0

        current_drawdown = float(drawdown.iloc[-1])

        return {
            "triggered": current_drawdown <= threshold,
            "current_drawdown": current_drawdown,
        }

    def max_drawdown(self) -> dict:
        """
        The largest peak-to-trough decline over the whole return
        series -- distinct from drawdown_alert(), which only reports
        the CURRENT drawdown against a threshold, not the historical
        maximum. A portfolio can be flat today (current_drawdown near
        0) while having suffered a much larger drawdown at some point
        in its history; this is that larger number.
        """
        rets = self._portfolio_returns()

        if rets.empty:
            return {"max_drawdown": 0.0, "trough_index": None}

        equity = (1 + rets).cumprod()
        running_max = equity.cummax()
        drawdown = (equity / running_max) - 1.0

        max_dd = float(drawdown.min())
        trough_idx = drawdown.idxmin()

        return {
            "max_drawdown": max_dd,
            "trough_index": str(trough_idx) if trough_idx is not None else None,
        }

    def sharpe_ratio(self, *, risk_free_rate_annual: float = 0.0, periods_per_year: int = 252) -> float | None:
        """
        Annualized Sharpe ratio: (mean daily excess return / daily
        return std dev) * sqrt(periods_per_year). risk_free_rate_annual
        is an ANNUAL rate (e.g. 0.05 for 5%) -- converted to a daily
        rate internally for the excess-return calculation.

        Returns None (not 0.0 -- a real Sharpe ratio is never exactly
        zero by coincidence) if there's not enough return history or
        the return series has zero variance (e.g. a single position
        that hasn't moved), since a Sharpe ratio is undefined in that
        case, not zero.
        """
        rets = self._portfolio_returns()

        if len(rets) < 2:
            return None

        daily_rf = risk_free_rate_annual / periods_per_year
        excess = rets - daily_rf

        std = excess.std()
        if std == 0 or pd.isna(std):
            return None

        sharpe = (excess.mean() / std) * math.sqrt(periods_per_year)

        return round(float(sharpe), 3)

    def sortino_ratio(self, *, risk_free_rate_annual: float = 0.0, periods_per_year: int = 252) -> float | None:
        """
        Annualized Sortino ratio -- like Sharpe, but only penalizes
        downside volatility (returns below the risk-free/target rate),
        not total volatility. A portfolio with big upside swings and
        no downside ones scores well here even if its Sharpe ratio
        (which penalizes ALL volatility) doesn't.

        Returns None if there's not enough history, or if there are no
        downside periods at all (downside deviation of 0 -- Sortino is
        undefined, not infinite or zero, in that case).
        """
        rets = self._portfolio_returns()

        if len(rets) < 2:
            return None

        daily_rf = risk_free_rate_annual / periods_per_year
        excess = rets - daily_rf

        downside = excess[excess < 0]
        if downside.empty:
            return None

        downside_deviation = math.sqrt((downside ** 2).mean())
        if downside_deviation == 0:
            return None

        sortino = (excess.mean() / downside_deviation) * math.sqrt(periods_per_year)

        return round(float(sortino), 3)

    def volatility_regime(self) -> dict:
        """
        Determine the current portfolio volatility regime.

        Supports both:

            Legacy format:
                returns_df["Return"]

            Multi-asset format:
                returns_df =

                    ABX    BSM    AAPL
                    ...    ...    ...

        """

        rets = self._portfolio_returns()

        if rets.empty:
            return {
                "daily_vol": 0.0,
                "annualized_vol": 0.0,
                "regime": "Unknown",
            }

        daily_vol = float(rets.std(ddof=0))
        annualized_vol = float(daily_vol * math.sqrt(252))

        if annualized_vol < 0.10:
            regime = "Low"

        elif annualized_vol < 0.25:
            regime = "Normal"

        else:
            regime = "High"

        return {
            "daily_vol": daily_vol,
            "annualized_vol": annualized_vol,
            "regime": regime,
        }

    # -----------------------------
    # Advanced cross-check (optional: arch GARCH + Riskfolio-Lib EVaR/CVaR)
    # -----------------------------
    def advanced_risk_cross_check(
            self,
            confidence: float = 0.95,
    ) -> dict:
        """
        Runs optional advanced risk models.

        Supports both:

            Legacy format:
                returns_df["Return"]

            Multi-asset format:
                returns_df =

                    ABX    BSM    AAPL
                    ...    ...    ...

        Uses the portfolio return series generated by _portfolio_returns().
        """

        from modules.portfolio.advanced_risk_engine import (
            garch_volatility_forecast,
            riskfolio_tail_risk,
        )

        rets = self._portfolio_returns()

        if rets.empty:
            unavailable = {
                "available": False,
                "reason": "No return series available.",
            }

            return {
                "garch": unavailable,
                "riskfolio": unavailable,
            }

        try:

            garch = garch_volatility_forecast(rets)

        except Exception as exc:

            garch = {
                "available": False,
                "reason": str(exc),
            }

        try:

            riskfolio = riskfolio_tail_risk(
                rets,
                confidence=confidence,
            )

        except Exception as exc:

            riskfolio = {
                "available": False,
                "reason": str(exc),
            }

        return {
            "garch": garch,
            "riskfolio": riskfolio,
        }