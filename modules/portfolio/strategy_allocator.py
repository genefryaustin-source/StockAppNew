from __future__ import annotations

import pandas as pd


class StrategyAllocator:
    def __init__(self):
        pass

    # ---------------------------------
    # Equal capital across strategies
    # ---------------------------------
    def equal_allocate(self, strategy_targets: dict[str, pd.DataFrame]) -> pd.DataFrame:
        if not strategy_targets:
            return pd.DataFrame()

        n = len(strategy_targets)
        strategy_weight = 1.0 / n

        rows = []

        for strategy_name, df in strategy_targets.items():
            if df is None or df.empty:
                continue

            local = df.copy()

            if "Symbol" not in local.columns or "Target Weight" not in local.columns:
                continue

            for _, row in local.iterrows():
                rows.append({
                    "Strategy": strategy_name,
                    "Symbol": row["Symbol"],
                    "Strategy Weight": strategy_weight,
                    "Local Target Weight": float(row["Target Weight"]),
                    "Allocated Weight": strategy_weight * float(row["Target Weight"]),
                })

        if not rows:
            return pd.DataFrame()

        out = pd.DataFrame(rows)

        combined = (
            out.groupby("Symbol", as_index=False)
            .agg(Total_Target_Weight=("Allocated Weight", "sum"))
            .sort_values("Total_Target_Weight", ascending=False)
        )

        combined = combined.rename(columns={"Total_Target_Weight": "Target Weight"})
        return combined

    # ---------------------------------
    # Custom strategy capital weights
    # ---------------------------------
    def weighted_allocate(
        self,
        strategy_targets: dict[str, pd.DataFrame],
        allocation_weights: dict[str, float],
    ) -> pd.DataFrame:
        if not strategy_targets or not allocation_weights:
            return pd.DataFrame()

        total_alloc = float(sum(allocation_weights.values()))
        if total_alloc <= 0:
            return pd.DataFrame()

        norm_alloc = {
            k: float(v) / total_alloc
            for k, v in allocation_weights.items()
        }

        rows = []

        for strategy_name, df in strategy_targets.items():
            if df is None or df.empty:
                continue

            alloc = norm_alloc.get(strategy_name, 0.0)
            if alloc <= 0:
                continue

            local = df.copy()

            if "Symbol" not in local.columns or "Target Weight" not in local.columns:
                continue

            for _, row in local.iterrows():
                rows.append({
                    "Strategy": strategy_name,
                    "Symbol": row["Symbol"],
                    "Strategy Weight": alloc,
                    "Local Target Weight": float(row["Target Weight"]),
                    "Allocated Weight": alloc * float(row["Target Weight"]),
                })

        if not rows:
            return pd.DataFrame()

        out = pd.DataFrame(rows)

        combined = (
            out.groupby("Symbol", as_index=False)
            .agg(Target_Weight=("Allocated Weight", "sum"))
            .sort_values("Target_Weight", ascending=False)
        )

        combined = combined.rename(columns={"Target_Weight": "Target Weight"})
        return combined

    # ---------------------------------
    # Strategy contribution table
    # ---------------------------------
    def strategy_mix_table(
        self,
        strategy_targets: dict[str, pd.DataFrame],
        allocation_weights: dict[str, float],
    ) -> pd.DataFrame:
        rows = []

        total_alloc = float(sum(allocation_weights.values())) if allocation_weights else 0.0
        if total_alloc <= 0:
            return pd.DataFrame()

        for name, df in strategy_targets.items():
            alloc = float(allocation_weights.get(name, 0.0)) / total_alloc
            rows.append({
                "Strategy": name,
                "Allocation Weight": alloc,
                "Symbols": 0 if df is None else len(df),
            })

        return pd.DataFrame(rows).sort_values("Allocation Weight", ascending=False)