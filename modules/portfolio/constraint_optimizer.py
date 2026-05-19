from __future__ import annotations

import pandas as pd
import numpy as np


class ConstraintAwareOptimizer:
    def __init__(self):
        pass

    def optimize(
        self,
        strategy_metrics_df: pd.DataFrame,
        overlap_matrix_df: pd.DataFrame | None = None,
        current_weights: dict[str, float] | None = None,
        max_strategy_weight: float = 0.50,
        max_symbol_weight: float = 0.10,
        turnover_penalty: float = 0.20,
        overlap_penalty: float = 0.15,
        drawdown_penalty: float = 0.25,
        vol_target: float | None = None,
    ) -> pd.DataFrame:

        if strategy_metrics_df is None or strategy_metrics_df.empty:
            return pd.DataFrame()

        df = strategy_metrics_df.copy()

        # ---------------------------
        # Base scoring
        # ---------------------------
        df["Score"] = (
            0.4 * df["Sharpe"].fillna(0.0)
            + 0.3 * df["Alpha"].fillna(0.0)
            + 0.3 * df["Capital Efficiency"].fillna(0.0)
        )

        # ---------------------------
        # Drawdown penalty
        # ---------------------------
        df["DD Penalty"] = df["Max Drawdown"].abs() * drawdown_penalty

        # ---------------------------
        # Overlap penalty
        # ---------------------------
        overlap_scores = {}

        if overlap_matrix_df is not None and not overlap_matrix_df.empty:
            for strat in df["Strategy"]:
                if strat in overlap_matrix_df.index:
                    overlap = overlap_matrix_df.loc[strat].sum()
                    overlap_scores[strat] = overlap * overlap_penalty
                else:
                    overlap_scores[strat] = 0.0
        else:
            overlap_scores = {s: 0.0 for s in df["Strategy"]}

        df["Overlap Penalty"] = df["Strategy"].map(overlap_scores)

        # ---------------------------
        # Turnover penalty
        # ---------------------------
        turnover_scores = {}

        for strat in df["Strategy"]:
            prev = 0.0 if current_weights is None else current_weights.get(strat, 0.0)
            turnover_scores[strat] = abs(prev - 0.0) * turnover_penalty

        df["Turnover Penalty"] = df["Strategy"].map(turnover_scores)

        # ---------------------------
        # Final score
        # ---------------------------
        df["Final Score"] = (
            df["Score"]
            - df["DD Penalty"]
            - df["Overlap Penalty"]
            - df["Turnover Penalty"]
        )

        df["Final Score"] = df["Final Score"].clip(lower=0.0)

        total_score = df["Final Score"].sum()

        if total_score <= 0:
            df["Weight"] = 1.0 / len(df)
        else:
            df["Weight"] = df["Final Score"] / total_score

        # ---------------------------
        # Cap weights
        # ---------------------------
        df["Weight"] = df["Weight"].clip(upper=max_strategy_weight)

        # Renormalize
        df["Weight"] = df["Weight"] / df["Weight"].sum()

        # ---------------------------
        # Volatility targeting (optional)
        # ---------------------------
        if vol_target is not None and "Volatility" in df.columns:
            current_vol = (df["Weight"] * df["Volatility"]).sum()
            if current_vol > 0:
                scale = vol_target / current_vol
                df["Weight"] = df["Weight"] * scale
                df["Weight"] = df["Weight"] / df["Weight"].sum()

        return df.sort_values("Weight", ascending=False)