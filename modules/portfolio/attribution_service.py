from __future__ import annotations

import pandas as pd


class AttributionService:
    def __init__(
        self,
        positions_df: pd.DataFrame | None = None,
        returns_df: pd.DataFrame | None = None,
        benchmark_df: pd.DataFrame | None = None,
        market_data_service=None,
    ):
        self.positions_df = positions_df if positions_df is not None else pd.DataFrame()
        self.returns_df = returns_df if returns_df is not None else pd.DataFrame()
        self.benchmark_df = benchmark_df if benchmark_df is not None else pd.DataFrame()
        self.market_data_service = market_data_service

    # -----------------------------
    # Sector Mapping (fallback safe)
    # -----------------------------
    def _get_sector(self, symbol: str) -> str:
        try:
            if self.market_data_service:
                meta = self.market_data_service.get_company_profile(symbol)
                return meta.get("sector", "Unknown")
        except Exception:
            pass
        return "Unknown"

    # -----------------------------
    # Sector Exposure
    # -----------------------------
    def sector_exposure(self) -> pd.DataFrame:
        if self.positions_df.empty:
            return pd.DataFrame()

        df = self.positions_df.copy()

        df["Sector"] = df["Symbol"].apply(self._get_sector)

        total_mv = df["Market Value"].sum()
        if total_mv == 0:
            df["Weight"] = 0.0
        else:
            df["Weight"] = df["Market Value"] / total_mv

        out = (
            df.groupby("Sector", as_index=False)
            .agg(
                Market_Value=("Market Value", "sum"),
                Weight=("Weight", "sum"),
            )
            .sort_values("Weight", ascending=False)
        )

        return out

    # -----------------------------
    # Contribution by Position
    # -----------------------------
    def contribution_by_symbol(self) -> pd.DataFrame:
        if self.positions_df.empty or self.returns_df.empty:
            return pd.DataFrame()

        latest_weights = self.positions_df.copy()

        total_mv = latest_weights["Market Value"].sum()
        if total_mv == 0:
            return pd.DataFrame()

        latest_weights["Weight"] = latest_weights["Market Value"] / total_mv

        avg_return = self.returns_df["Return"].mean()

        latest_weights["Contribution"] = latest_weights["Weight"] * avg_return

        return latest_weights.sort_values("Contribution", ascending=False)

    # -----------------------------
    # Benchmark Alpha
    # -----------------------------
    def alpha_vs_benchmark(self) -> dict:
        if self.returns_df.empty or self.benchmark_df.empty:
            return {"alpha": 0.0, "beta": 0.0}

        df = self.returns_df.copy()
        bench = self.benchmark_df.copy()

        df.index = pd.to_datetime(df.index).tz_localize(None)
        bench.index = pd.to_datetime(bench.index).tz_localize(None)

        merged = df.join(bench["Benchmark Return"], how="inner")

        if merged.empty:
            return {"alpha": 0.0, "beta": 0.0}

        port_ret = merged["Return"]
        bench_ret = merged["Benchmark Return"]

        cov = port_ret.cov(bench_ret)
        var = bench_ret.var()

        beta = cov / var if var != 0 else 0.0
        alpha = port_ret.mean() - beta * bench_ret.mean()

        return {
            "alpha": float(alpha),
            "beta": float(beta),
        }

    # -----------------------------
    # Top Contributors / Detractors
    # -----------------------------
    def top_contributors(self, n=5) -> pd.DataFrame:
        df = self.contribution_by_symbol()
        if df.empty:
            return df

        return df.head(n)

    def top_detractors(self, n=5) -> pd.DataFrame:
        df = self.contribution_by_symbol()
        if df.empty:
            return df

        return df.tail(n)

    # -----------------------------
    # Factor Signals (simple)
    # -----------------------------
    def factor_snapshot(self) -> dict:
        if self.positions_df.empty:
            return {}

        df = self.positions_df.copy()

        total_mv = df["Market Value"].sum()
        if total_mv == 0:
            return {}

        weights = df["Market Value"] / total_mv

        # placeholders for now (expand later)
        return {
            "concentration": float(weights.max()),
            "diversification": float(1.0 - weights.max()),
            "num_positions": int(len(df)),
        }