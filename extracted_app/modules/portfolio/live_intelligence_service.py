from __future__ import annotations

import pandas as pd


class LivePortfolioIntelligenceService:
    def __init__(
        self,
        positions_df: pd.DataFrame | None = None,
        orders_df: pd.DataFrame | None = None,
        closed_trades_df: pd.DataFrame | None = None,
        returns_df: pd.DataFrame | None = None,
    ):
        self.positions_df = positions_df.copy() if positions_df is not None else pd.DataFrame()
        self.orders_df = orders_df.copy() if orders_df is not None else pd.DataFrame()
        self.closed_trades_df = closed_trades_df.copy() if closed_trades_df is not None else pd.DataFrame()
        self.returns_df = returns_df.copy() if returns_df is not None else pd.DataFrame()

    # ---------------------------------
    # Sleeve drift
    # ---------------------------------
    def sleeve_drift(
        self,
        target_allocations: dict[str, float],
        actual_allocations: dict[str, float],
    ) -> pd.DataFrame:
        if not target_allocations:
            return pd.DataFrame()

        rows = []
        all_keys = sorted(set(target_allocations.keys()) | set(actual_allocations.keys()))

        for key in all_keys:
            target = float(target_allocations.get(key, 0.0))
            actual = float(actual_allocations.get(key, 0.0))
            drift = actual - target

            rows.append({
                "Strategy": key,
                "Target Allocation": target,
                "Actual Allocation": actual,
                "Drift": drift,
                "Abs Drift": abs(drift),
            })

        return pd.DataFrame(rows).sort_values("Abs Drift", ascending=False)

    # ---------------------------------
    # Execution slippage summary
    # ---------------------------------
    def slippage_summary(self) -> dict:
        if self.orders_df.empty or "Slippage" not in self.orders_df.columns:
            return {
                "avg_slippage": 0.0,
                "max_slippage": 0.0,
                "total_slippage": 0.0,
            }

        s = self.orders_df["Slippage"].fillna(0.0)
        return {
            "avg_slippage": float(s.mean()),
            "max_slippage": float(s.max()),
            "total_slippage": float(s.sum()),
        }

    # ---------------------------------
    # Alpha decay
    # ---------------------------------
    def alpha_decay(self, window: int = 10) -> dict:
        if self.returns_df.empty or "Return" not in self.returns_df.columns:
            return {
                "recent_avg_return": 0.0,
                "older_avg_return": 0.0,
                "decay": 0.0,
                "decaying": False,
            }

        rets = self.returns_df["Return"].dropna()
        if len(rets) < window * 2:
            return {
                "recent_avg_return": 0.0,
                "older_avg_return": 0.0,
                "decay": 0.0,
                "decaying": False,
            }

        recent = float(rets.tail(window).mean())
        older = float(rets.tail(window * 2).head(window).mean())
        decay = recent - older

        return {
            "recent_avg_return": recent,
            "older_avg_return": older,
            "decay": decay,
            "decaying": recent < older,
        }

    # ---------------------------------
    # Reweight trigger
    # ---------------------------------
    def reweight_trigger(
        self,
        drift_df: pd.DataFrame,
        drift_threshold: float = 0.05,
        alpha_decay_flag: bool = False,
        slippage_threshold: float = 0.02,
    ) -> dict:
        drift_breach = False
        if drift_df is not None and not drift_df.empty and "Abs Drift" in drift_df.columns:
            drift_breach = bool((drift_df["Abs Drift"] >= drift_threshold).any())

        slip = self.slippage_summary()
        slippage_breach = slip["avg_slippage"] >= slippage_threshold

        trigger = drift_breach or alpha_decay_flag or slippage_breach

        reasons = []
        if drift_breach:
            reasons.append("Sleeve drift threshold breached")
        if alpha_decay_flag:
            reasons.append("Alpha decay detected")
        if slippage_breach:
            reasons.append("Execution slippage elevated")

        return {
            "trigger": trigger,
            "reasons": reasons,
            "drift_breach": drift_breach,
            "alpha_decay": alpha_decay_flag,
            "slippage_breach": slippage_breach,
        }

    # ---------------------------------
    # Portfolio health score
    # ---------------------------------
    def portfolio_health_score(
        self,
        drift_df: pd.DataFrame | None = None,
    ) -> dict:
        score = 100.0

        slip = self.slippage_summary()
        decay = self.alpha_decay()

        if drift_df is not None and not drift_df.empty and "Abs Drift" in drift_df.columns:
            max_drift = float(drift_df["Abs Drift"].max())
            score -= min(max_drift * 100.0, 25.0)

        score -= min(abs(slip["avg_slippage"]) * 1000.0, 20.0)

        if decay["decaying"]:
            score -= 15.0

        score = max(score, 0.0)

        if score >= 85:
            regime = "Healthy"
        elif score >= 65:
            regime = "Watch"
        else:
            regime = "Action Needed"

        return {
            "score": float(score),
            "regime": regime,
        }