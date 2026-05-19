from __future__ import annotations

import pandas as pd


class PortfolioConstructionService:
    def __init__(self, positions_df: pd.DataFrame | None = None):
        self.positions_df = positions_df.copy() if positions_df is not None else pd.DataFrame()

    # -----------------------------
    # Current Weights
    # -----------------------------
    def current_weights(self) -> pd.DataFrame:
        if self.positions_df is None or self.positions_df.empty:
            return pd.DataFrame(columns=["Symbol", "Market Value", "Weight"])

        df = self.positions_df.copy()
        df.columns = [c.strip() for c in df.columns]

        # Normalize symbol column
        if "Symbol" not in df.columns:
            if "symbol" in df.columns:
                df["Symbol"] = df["symbol"]
            else:
                return pd.DataFrame(columns=["Symbol", "Market Value", "Weight"])

        if "Market Value" not in df.columns:
            return pd.DataFrame(columns=["Symbol", "Market Value", "Weight"])

        total_mv = df["Market Value"].sum()

        if total_mv == 0:
            df["Weight"] = 0.0
        else:
            df["Weight"] = df["Market Value"] / total_mv

        return df[["Symbol", "Market Value", "Weight"]]

    # -----------------------------
    # Equal Weight Target
    # -----------------------------
    def equal_weight(self, symbols: list[str]) -> pd.DataFrame:
        if not symbols:
            return pd.DataFrame()

        w = 1.0 / len(symbols)

        return pd.DataFrame({
            "Symbol": symbols,
            "Target Weight": [w] * len(symbols),
        })

    # -----------------------------
    # Manual Target
    # -----------------------------
    def manual_weights(self, weights_dict: dict[str, float]) -> pd.DataFrame:
        if not weights_dict:
            return pd.DataFrame()

        df = pd.DataFrame([
            {"Symbol": k.upper(), "Target Weight": float(v)}
            for k, v in weights_dict.items()
        ])

        total = df["Target Weight"].sum()
        if total != 0:
            df["Target Weight"] = df["Target Weight"] / total

        return df

    # -----------------------------
    # Rebalance Engine
    # -----------------------------
    def generate_rebalance_trades(
        self,
        target_df: pd.DataFrame,
        prices: dict[str, float],
        portfolio_value: float,
        min_trade_pct: float = 0.01,
    ) -> pd.DataFrame:

        if target_df is None or target_df.empty:
            return pd.DataFrame()

        target_df = target_df.copy()
        target_df.columns = [c.strip() for c in target_df.columns]

        if "Symbol" not in target_df.columns:
            return pd.DataFrame()

        if "Target Weight" not in target_df.columns:
            return pd.DataFrame()

        current_df = self.current_weights()

        if current_df.empty:
            current_df = pd.DataFrame(columns=["Symbol", "Market Value", "Weight"])

        df = target_df.merge(current_df, on="Symbol", how="left")

        df["Weight"] = df["Weight"].fillna(0.0)
        df["Market Value"] = df["Market Value"].fillna(0.0)

        portfolio_value = float(portfolio_value or 0.0)

        df["Target Value"] = df["Target Weight"] * portfolio_value
        df["Diff Value"] = df["Target Value"] - df["Market Value"]

        rows = []

        for _, row in df.iterrows():
            symbol = row["Symbol"]
            price = prices.get(symbol)

            if price is None or price <= 0:
                continue

            diff_value = float(row["Diff Value"])

            if abs(diff_value) < portfolio_value * min_trade_pct:
                continue

            qty = diff_value / price

            rows.append({
                "Symbol": symbol,
                "Side": "buy" if qty > 0 else "sell",
                "Qty": abs(qty),
                "Est Price": price,
                "Notional": diff_value,
            })

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows).sort_values("Notional", ascending=False)