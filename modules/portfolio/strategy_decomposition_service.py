from __future__ import annotations

import pandas as pd


class StrategyDecompositionService:
    def __init__(
        self,
        positions_df: pd.DataFrame | None = None,
        closed_trades_df: pd.DataFrame | None = None,
    ):
        self.positions_df = positions_df.copy() if positions_df is not None else pd.DataFrame()
        self.closed_trades_df = closed_trades_df.copy() if closed_trades_df is not None else pd.DataFrame()

    def sleeve_contribution(
        self,
        strategy_targets: dict[str, pd.DataFrame],
        allocation_weights: dict[str, float],
    ) -> pd.DataFrame:
        if not strategy_targets or not allocation_weights:
            return pd.DataFrame()

        total_alloc = float(sum(allocation_weights.values()))
        if total_alloc <= 0:
            return pd.DataFrame()

        rows = []

        for strategy_name, target_df in strategy_targets.items():
            if target_df is None or target_df.empty:
                continue

            alloc = float(allocation_weights.get(strategy_name, 0.0)) / total_alloc
            local = target_df.copy()

            if "Symbol" not in local.columns or "Target Weight" not in local.columns:
                continue

            pnl = 0.0
            market_value = 0.0
            overlap_symbols = []

            for _, row in local.iterrows():
                symbol = str(row["Symbol"]).upper()
                local_weight = float(row["Target Weight"])

                pos_match = pd.DataFrame()
                if not self.positions_df.empty and "Symbol" in self.positions_df.columns:
                    pos_match = self.positions_df[self.positions_df["Symbol"].astype(str).str.upper() == symbol]

                if not pos_match.empty:
                    mv = float(pos_match["Market Value"].fillna(0.0).sum())
                    upnl = float(pos_match["Unrealized P&L"].fillna(0.0).sum())
                    rpnl = float(pos_match["Realized P&L"].fillna(0.0).sum())
                    symbol_pnl = upnl + rpnl

                    pnl += alloc * local_weight * symbol_pnl
                    market_value += alloc * local_weight * mv

                    overlap_symbols.append(symbol)

            rows.append({
                "Strategy": strategy_name,
                "Allocation Weight": alloc,
                "Sleeve Market Value": market_value,
                "Sleeve Estimated P&L": pnl,
                "Tracked Symbols": len(set(overlap_symbols)),
            })

        if not rows:
            return pd.DataFrame()

        out = pd.DataFrame(rows)
        out["Capital Efficiency"] = out.apply(
            lambda r: (r["Sleeve Estimated P&L"] / r["Sleeve Market Value"]) if r["Sleeve Market Value"] not in (0, None) else 0.0,
            axis=1,
        )
        return out.sort_values("Sleeve Estimated P&L", ascending=False)

    def overlap_matrix(self, strategy_targets: dict[str, pd.DataFrame]) -> pd.DataFrame:
        if not strategy_targets:
            return pd.DataFrame()

        strategies = list(strategy_targets.keys())
        matrix = pd.DataFrame(index=strategies, columns=strategies, data=0)

        symbol_sets = {}
        for name, df in strategy_targets.items():
            if df is None or df.empty or "Symbol" not in df.columns:
                symbol_sets[name] = set()
            else:
                symbol_sets[name] = set(df["Symbol"].astype(str).str.upper().tolist())

        for s1 in strategies:
            for s2 in strategies:
                matrix.loc[s1, s2] = len(symbol_sets[s1].intersection(symbol_sets[s2]))

        return matrix

    def symbol_strategy_map(self, strategy_targets: dict[str, pd.DataFrame]) -> pd.DataFrame:
        rows = []
        for strategy_name, df in strategy_targets.items():
            if df is None or df.empty or "Symbol" not in df.columns:
                continue

            for _, row in df.iterrows():
                rows.append({
                    "Strategy": strategy_name,
                    "Symbol": str(row["Symbol"]).upper(),
                    "Target Weight": float(row.get("Target Weight", 0.0)),
                })

        if not rows:
            return pd.DataFrame()

        out = pd.DataFrame(rows)
        grouped = (
            out.groupby("Symbol", as_index=False)
            .agg(
                Strategy_Count=("Strategy", "count"),
                Combined_Target_Weight=("Target Weight", "sum"),
            )
            .sort_values(["Strategy_Count", "Combined_Target_Weight"], ascending=[False, False])
        )
        return grouped

    def closed_trade_attribution_by_strategy(
        self,
        strategy_targets: dict[str, pd.DataFrame],
        allocation_weights: dict[str, float],
    ) -> pd.DataFrame:
        if self.closed_trades_df.empty or not strategy_targets or not allocation_weights:
            return pd.DataFrame()

        total_alloc = float(sum(allocation_weights.values()))
        if total_alloc <= 0:
            return pd.DataFrame()

        rows = []

        for strategy_name, target_df in strategy_targets.items():
            if target_df is None or target_df.empty or "Symbol" not in target_df.columns:
                continue

            alloc = float(allocation_weights.get(strategy_name, 0.0)) / total_alloc
            symbols = set(target_df["Symbol"].astype(str).str.upper().tolist())

            trades = self.closed_trades_df[
                self.closed_trades_df["Symbol"].astype(str).str.upper().isin(symbols)
            ].copy()

            if trades.empty:
                rows.append({
                    "Strategy": strategy_name,
                    "Closed Trades": 0,
                    "Attributed Net P&L": 0.0,
                    "Win Rate": 0.0,
                })
                continue

            trades["Weighted Net P&L"] = trades["Net P&L"].fillna(0.0) * alloc
            wins = (trades["Net P&L"].fillna(0.0) > 0).sum()
            total = len(trades)

            rows.append({
                "Strategy": strategy_name,
                "Closed Trades": int(total),
                "Attributed Net P&L": float(trades["Weighted Net P&L"].sum()),
                "Win Rate": float(wins / total) if total > 0 else 0.0,
            })

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows).sort_values("Attributed Net P&L", ascending=False)