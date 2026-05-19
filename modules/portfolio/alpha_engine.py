from __future__ import annotations

import pandas as pd


class AlphaEngine:
    def __init__(self, market_data_service=None):
        self.market_data_service = market_data_service

    # ---------------------------------
    # Basic signal calculation
    # ---------------------------------
    def build_signal_frame(self, symbols: list[str]) -> pd.DataFrame:
        rows = []

        for symbol in symbols:
            symbol = str(symbol).upper().strip()
            if not symbol:
                continue

            score = self._score_symbol(symbol)

            rows.append({
                "Symbol": symbol,
                "Alpha Score": score["alpha_score"],
                "Momentum Score": score["momentum_score"],
                "Quality Score": score["quality_score"],
                "Value Score": score["value_score"],
                "Volatility Penalty": score["vol_penalty"],
                "Composite Score": score["composite_score"],
            })

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows).sort_values("Composite Score", ascending=False).reset_index(drop=True)
        return df

    # ---------------------------------
    # Score to target weights
    # ---------------------------------
    def scores_to_target_weights(
        self,
        signal_df: pd.DataFrame,
        top_n: int = 10,
        min_weight: float = 0.0,
        max_weight: float = 0.20,
    ) -> pd.DataFrame:
        if signal_df is None or signal_df.empty:
            return pd.DataFrame()

        df = signal_df.copy().sort_values("Composite Score", ascending=False).head(int(top_n)).copy()

        # Clip negatives so only positive alpha names get capital in v1
        df["Raw Score"] = df["Composite Score"].clip(lower=0.0)

        total = float(df["Raw Score"].sum())
        if total <= 0:
            # fallback equal-weight
            w = 1.0 / len(df)
            df["Target Weight"] = w
        else:
            df["Target Weight"] = df["Raw Score"] / total

        # cap weights
        df["Target Weight"] = df["Target Weight"].clip(lower=min_weight, upper=max_weight)

        # renormalize after caps
        total_after = float(df["Target Weight"].sum())
        if total_after > 0:
            df["Target Weight"] = df["Target Weight"] / total_after

        return df[["Symbol", "Composite Score", "Target Weight"]].sort_values(
            "Target Weight", ascending=False
        )

    # ---------------------------------
    # Lightweight scoring model
    # ---------------------------------
    def _score_symbol(self, symbol: str) -> dict:
        momentum_score = 0.0
        quality_score = 0.0
        value_score = 0.0
        vol_penalty = 0.0

        # Safely try to use market_data_service if it supports richer metadata
        try:
            if self.market_data_service and hasattr(self.market_data_service, "get_quote"):
                q = self.market_data_service.get_quote(symbol)
                if isinstance(q, dict):
                    # lightweight quote-driven placeholders
                    price = self._safe_num(q.get("price", q.get("c", q.get("last", q.get("close", 0.0)))))
                    prev_close = self._safe_num(q.get("prev_close", q.get("pc", price)))
                    chg = ((price / prev_close) - 1.0) if prev_close not in (0, None) else 0.0
                    momentum_score = max(min(chg * 10.0, 1.0), -1.0)
        except Exception:
            pass

        # Optional profile/fundamental hooks if your service exposes them
        try:
            if self.market_data_service and hasattr(self.market_data_service, "get_company_profile"):
                profile = self.market_data_service.get_company_profile(symbol) or {}
                quality_score += 0.1 if profile.get("ipo") else 0.0
        except Exception:
            pass

        try:
            if self.market_data_service and hasattr(self.market_data_service, "get_fundamentals"):
                f = self.market_data_service.get_fundamentals(symbol) or {}
                roe = self._safe_num(f.get("roe", 0.0))
                pe = self._safe_num(f.get("pe", 0.0))
                debt = self._safe_num(f.get("debt_to_equity", 0.0))

                quality_score += max(min(roe / 20.0, 1.0), -1.0)
                value_score += max(min((25.0 - pe) / 25.0, 1.0), -1.0) if pe > 0 else 0.0
                vol_penalty += max(min(debt / 3.0, 1.0), 0.0)
        except Exception:
            pass

        alpha_score = (
            0.45 * momentum_score +
            0.30 * quality_score +
            0.25 * value_score -
            0.20 * vol_penalty
        )

        return {
            "alpha_score": float(alpha_score),
            "momentum_score": float(momentum_score),
            "quality_score": float(quality_score),
            "value_score": float(value_score),
            "vol_penalty": float(vol_penalty),
            "composite_score": float(alpha_score),
        }

    @staticmethod
    def _safe_num(x, default: float = 0.0) -> float:
        try:
            if x is None:
                return default
            return float(x)
        except Exception:
            return default