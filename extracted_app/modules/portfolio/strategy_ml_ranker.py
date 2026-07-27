from __future__ import annotations

import pandas as pd


class StrategyMLRanker:
    def __init__(self):
        pass

    def build_feature_frame(
        self,
        strategy_metrics_df: pd.DataFrame,
        closed_attr_df: pd.DataFrame | None = None,
        sleeve_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        if strategy_metrics_df is None or strategy_metrics_df.empty:
            return pd.DataFrame()

        df = strategy_metrics_df.copy()

        # Ensure required columns exist
        for col in ["Strategy", "Sharpe", "Alpha", "Max Drawdown", "Capital Efficiency"]:
            if col not in df.columns:
                if col == "Strategy":
                    return pd.DataFrame()
                df[col] = 0.0

        out = df.copy()

        # Attach closed trade metrics if available
        if closed_attr_df is not None and not closed_attr_df.empty and "Strategy" in closed_attr_df.columns:
            out = out.merge(
                closed_attr_df,
                on="Strategy",
                how="left",
            )

        # Attach sleeve contribution if available
        if sleeve_df is not None and not sleeve_df.empty and "Strategy" in sleeve_df.columns:
            sleeve_cols = [c for c in ["Strategy", "Sleeve Estimated P&L", "Tracked Symbols", "Capital Efficiency"] if c in sleeve_df.columns]
            sleeve_local = sleeve_df[sleeve_cols].copy()
            out = out.merge(
                sleeve_local,
                on="Strategy",
                how="left",
                suffixes=("", "_sleeve"),
            )

        # Fill missing numeric values
        for col in out.columns:
            if col != "Strategy":
                out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

        return out

    def score_strategies(
        self,
        features_df: pd.DataFrame,
        alpha_decay_map: dict[str, float] | None = None,
        overlap_penalty_map: dict[str, float] | None = None,
    ) -> pd.DataFrame:
        if features_df is None or features_df.empty:
            return pd.DataFrame()

        df = features_df.copy()

        alpha_decay_map = alpha_decay_map or {}
        overlap_penalty_map = overlap_penalty_map or {}

        # Normalize optional columns
        if "Closed Trades" not in df.columns:
            df["Closed Trades"] = 0.0
        if "Attributed Net P&L" not in df.columns:
            df["Attributed Net P&L"] = 0.0
        if "Win Rate" not in df.columns:
            df["Win Rate"] = 0.0
        if "Sleeve Estimated P&L" not in df.columns:
            df["Sleeve Estimated P&L"] = 0.0
        if "Tracked Symbols" not in df.columns:
            df["Tracked Symbols"] = 0.0

        # Derived features
        df["Stability Score"] = (
            0.50 * df["Sharpe"].clip(lower=0.0) +
            0.25 * df["Win Rate"].clip(lower=0.0) +
            0.25 * df["Capital Efficiency"].clip(lower=0.0)
        )

        df["Profitability Score"] = (
            0.50 * df["Alpha"].clip(lower=0.0) +
            0.25 * df["Attributed Net P&L"].clip(lower=0.0) +
            0.25 * df["Sleeve Estimated P&L"].clip(lower=0.0)
        )

        df["Risk Penalty"] = df["Max Drawdown"].abs()

        df["Breadth Bonus"] = df["Tracked Symbols"].clip(lower=0.0) * 0.01

        df["Alpha Decay Penalty"] = df["Strategy"].map(alpha_decay_map).fillna(0.0)
        df["Overlap Penalty"] = df["Strategy"].map(overlap_penalty_map).fillna(0.0)

        # Composite ML-style score
        df["ML Score"] = (
            0.35 * df["Stability Score"] +
            0.35 * df["Profitability Score"] +
            0.15 * df["Capital Efficiency"].clip(lower=0.0) +
            0.15 * df["Breadth Bonus"] -
            0.30 * df["Risk Penalty"] -
            0.20 * df["Alpha Decay Penalty"] -
            0.15 * df["Overlap Penalty"]
        )

        df["ML Score"] = df["ML Score"].fillna(0.0)

        return df.sort_values("ML Score", ascending=False)

    def rank_to_allocations(
        self,
        ranked_df: pd.DataFrame,
        max_strategy_weight: float = 0.50,
        min_strategy_weight: float = 0.00,
    ) -> pd.DataFrame:
        if ranked_df is None or ranked_df.empty or "Strategy" not in ranked_df.columns or "ML Score" not in ranked_df.columns:
            return pd.DataFrame()

        df = ranked_df.copy()

        df["Raw Score"] = df["ML Score"].clip(lower=0.0)
        total = float(df["Raw Score"].sum())

        if total <= 0:
            df["Rank Weight"] = 1.0 / len(df)
        else:
            df["Rank Weight"] = df["Raw Score"] / total

        df["Rank Weight"] = df["Rank Weight"].clip(
            lower=float(min_strategy_weight),
            upper=float(max_strategy_weight),
        )

        total_after = float(df["Rank Weight"].sum())
        if total_after > 0:
            df["Rank Weight"] = df["Rank Weight"] / total_after

        return df[["Strategy", "ML Score", "Rank Weight"]].sort_values("Rank Weight", ascending=False)