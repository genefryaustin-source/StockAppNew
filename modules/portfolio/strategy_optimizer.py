from __future__ import annotations

import pandas as pd


class StrategyWeightOptimizer:
    def __init__(self):
        pass

    def optimize_weights(
        self,
        strategy_metrics_df: pd.DataFrame,
        overlap_matrix_df: pd.DataFrame | None = None,
        max_strategy_weight: float = 0.50,
        min_strategy_weight: float = 0.00,
        overlap_penalty: float = 0.15,
        drawdown_penalty: float = 0.25,
    ) -> pd.DataFrame:
        """
        Expected columns in strategy_metrics_df:
        - Strategy
        - Sharpe
        - Alpha
        - Max Drawdown
        - Capital Efficiency (optional)
        """

        if strategy_metrics_df is None or strategy_metrics_df.empty:
            return pd.DataFrame()

        df = strategy_metrics_df.copy()

        required = ["Strategy"]
        for col in required:
            if col not in df.columns:
                return pd.DataFrame()

        # Normalize missing metrics
        for col in ["Sharpe", "Alpha", "Max Drawdown", "Capital Efficiency"]:
            if col not in df.columns:
                df[col] = 0.0

        # Base score
        df["Base Score"] = (
            0.45 * df["Sharpe"].fillna(0.0) +
            0.30 * df["Alpha"].fillna(0.0) +
            0.25 * df["Capital Efficiency"].fillna(0.0)
        )

        # Drawdown penalty
        # More negative max drawdown => bigger penalty
        df["Drawdown Penalty"] = df["Max Drawdown"].fillna(0.0).abs() * float(drawdown_penalty)

        # Overlap penalty
        overlap_penalties = {}
        if overlap_matrix_df is not None and not overlap_matrix_df.empty:
            for strat in df["Strategy"].tolist():
                if strat in overlap_matrix_df.index:
                    row = overlap_matrix_df.loc[strat]
                    # subtract self-overlap
                    total_overlap = float(row.sum()) - float(row.get(strat, 0.0))
                    overlap_penalties[strat] = total_overlap * float(overlap_penalty)
                else:
                    overlap_penalties[strat] = 0.0
        else:
            overlap_penalties = {s: 0.0 for s in df["Strategy"].tolist()}

        df["Overlap Penalty"] = df["Strategy"].map(overlap_penalties).fillna(0.0)

        df["Raw Optimized Score"] = (
            df["Base Score"] -
            df["Drawdown Penalty"] -
            df["Overlap Penalty"]
        )

        # Clip negative scores for long-only allocator
        df["Raw Optimized Score"] = df["Raw Optimized Score"].clip(lower=0.0)

        total_score = float(df["Raw Optimized Score"].sum())

        if total_score <= 0:
            # fallback equal weight
            w = 1.0 / len(df)
            df["Optimized Weight"] = w
        else:
            df["Optimized Weight"] = df["Raw Optimized Score"] / total_score

        # Apply cap/floor
        df["Optimized Weight"] = df["Optimized Weight"].clip(
            lower=float(min_strategy_weight),
            upper=float(max_strategy_weight),
        )

        # Re-normalize after cap/floor
        total_after = float(df["Optimized Weight"].sum())
        if total_after > 0:
            df["Optimized Weight"] = df["Optimized Weight"] / total_after

        return df[[
            "Strategy",
            "Sharpe",
            "Alpha",
            "Max Drawdown",
            "Capital Efficiency",
            "Base Score",
            "Drawdown Penalty",
            "Overlap Penalty",
            "Raw Optimized Score",
            "Optimized Weight",
        ]].sort_values("Optimized Weight", ascending=False)