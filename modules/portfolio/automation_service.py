from __future__ import annotations

import pandas as pd


class PortfolioAutomationService:
    def __init__(self, constructor):
        self.constructor = constructor

    # ---------------------------------
    # Compute drift
    # ---------------------------------
    def compute_drift(
        self,
        current_weights_df: pd.DataFrame,
        target_weights_df: pd.DataFrame,
    ) -> pd.DataFrame:

        if target_weights_df is None or target_weights_df.empty:
            return pd.DataFrame()

        target = target_weights_df.copy()
        current = current_weights_df.copy() if current_weights_df is not None else pd.DataFrame()

        if current.empty:
            current = pd.DataFrame(columns=["Symbol", "Weight", "Market Value"])

        target.columns = [c.strip() for c in target.columns]
        current.columns = [c.strip() for c in current.columns]

        if "Symbol" not in target.columns or "Target Weight" not in target.columns:
            return pd.DataFrame()

        if "Symbol" not in current.columns:
            current = pd.DataFrame(columns=["Symbol", "Weight", "Market Value"])

        if "Weight" not in current.columns:
            current["Weight"] = 0.0

        merged = target.merge(
            current[["Symbol", "Weight"]],
            on="Symbol",
            how="left"
        )

        merged["Weight"] = merged["Weight"].fillna(0.0)
        merged["Drift"] = merged["Weight"] - merged["Target Weight"]
        merged["Abs Drift"] = merged["Drift"].abs()

        return merged.sort_values("Abs Drift", ascending=False)

    # ---------------------------------
    # Check if drift exceeds threshold
    # ---------------------------------
    def drift_triggered(
        self,
        drift_df: pd.DataFrame,
        threshold: float = 0.05,
    ) -> bool:

        if drift_df is None or drift_df.empty or "Abs Drift" not in drift_df.columns:
            return False

        return bool((drift_df["Abs Drift"] >= float(threshold)).any())

    # ---------------------------------
    # Generate rebalance if needed
    # ---------------------------------
    def generate_rebalance_if_needed(
        self,
        target_df: pd.DataFrame,
        prices: dict,
        portfolio_value: float,
        drift_threshold: float = 0.05,
        min_trade_pct: float = 0.01,
    ):

        current_df = self.constructor.current_weights()

        drift_df = self.compute_drift(current_df, target_df)
        triggered = self.drift_triggered(drift_df, threshold=drift_threshold)

        if not triggered:
            return {
                "triggered": False,
                "drift_df": drift_df,
                "rebalance_df": pd.DataFrame(),
            }

        rebalance_df = self.constructor.generate_rebalance_trades(
            target_df=target_df,
            prices=prices,
            portfolio_value=portfolio_value,
            min_trade_pct=min_trade_pct,
        )

        return {
            "triggered": True,
            "drift_df": drift_df,
            "rebalance_df": rebalance_df,
        }