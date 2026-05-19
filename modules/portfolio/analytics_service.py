from __future__ import annotations

import math
import pandas as pd


class PortfolioAnalyticsService:
    def __init__(
        self,
        snapshots_df: pd.DataFrame | None = None,
        closed_trades_df: pd.DataFrame | None = None,
    ):
        self.snapshots_df = snapshots_df.copy() if snapshots_df is not None else pd.DataFrame()
        self.closed_trades_df = closed_trades_df.copy() if closed_trades_df is not None else pd.DataFrame()

    def prepare_snapshot_returns(self) -> pd.DataFrame:
        if self.snapshots_df is None or self.snapshots_df.empty:
            return pd.DataFrame()

        df = self.snapshots_df.copy()
        df["As Of"] = pd.to_datetime(df["As Of"])
        df = df.sort_values("As Of").drop_duplicates(subset=["As Of"])
        df = df.set_index("As Of")

        if "Equity" not in df.columns:
            return pd.DataFrame()

        df["Return"] = df["Equity"].pct_change().fillna(0.0)
        df["Cumulative Return"] = (1.0 + df["Return"]).cumprod() - 1.0
        df["Rolling Peak"] = df["Equity"].cummax()
        df["Drawdown"] = (df["Equity"] / df["Rolling Peak"]) - 1.0
        return df

    @staticmethod
    def summary_stats(returns_df: pd.DataFrame) -> dict:
        if returns_df is None or returns_df.empty or "Return" not in returns_df.columns:
            return {
                "total_return": 0.0,
                "annualized_return": 0.0,
                "annualized_volatility": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
            }

        rets = returns_df["Return"].fillna(0.0)
        n = len(rets)

        total_return = float((1.0 + rets).prod() - 1.0)

        if n > 1:
            annualized_return = float((1.0 + total_return) ** (252 / max(n, 1)) - 1.0)
            annualized_volatility = float(rets.std(ddof=0) * math.sqrt(252))
        else:
            annualized_return = 0.0
            annualized_volatility = 0.0

        sharpe = annualized_return / annualized_volatility if annualized_volatility > 0 else 0.0
        max_drawdown = float(returns_df["Drawdown"].min()) if "Drawdown" in returns_df.columns else 0.0

        return {
            "total_return": total_return,
            "annualized_return": annualized_return,
            "annualized_volatility": annualized_volatility,
            "sharpe": sharpe,
            "max_drawdown": max_drawdown,
        }

    @staticmethod
    def position_concentration(positions_df: pd.DataFrame) -> pd.DataFrame:
        if positions_df is None or positions_df.empty:
            return pd.DataFrame()

        df = positions_df.copy()
        if "Market Value" not in df.columns or "Symbol" not in df.columns:
            return pd.DataFrame()

        total_mv = float(df["Market Value"].fillna(0.0).sum())
        df["Weight"] = 0.0 if total_mv == 0 else df["Market Value"].fillna(0.0) / total_mv
        return df.sort_values("Weight", ascending=False)

    @staticmethod
    def exposure_stats(positions_df: pd.DataFrame) -> dict:
        if positions_df is None or positions_df.empty or "Market Value" not in positions_df.columns:
            return {
                "gross_exposure": 0.0,
                "net_exposure": 0.0,
                "long_exposure": 0.0,
                "short_exposure": 0.0,
            }

        mv = positions_df["Market Value"].fillna(0.0)
        long_exposure = float(mv[mv > 0].sum())
        short_exposure = float(mv[mv < 0].sum())
        gross_exposure = float(abs(long_exposure) + abs(short_exposure))
        net_exposure = float(long_exposure + short_exposure)

        return {
            "gross_exposure": gross_exposure,
            "net_exposure": net_exposure,
            "long_exposure": long_exposure,
            "short_exposure": short_exposure,
        }

    @staticmethod
    def trade_stats(orders_df: pd.DataFrame) -> dict:
        if orders_df is None or orders_df.empty:
            return {
                "total_orders": 0,
                "filled_orders": 0,
                "buy_orders": 0,
                "sell_orders": 0,
                "avg_commission": 0.0,
                "avg_slippage": 0.0,
            }

        df = orders_df.copy()
        total_orders = int(len(df))
        filled_orders = int((df["Status"].astype(str).str.lower() == "filled").sum()) if "Status" in df.columns else 0
        buy_orders = int((df["Side"].astype(str).str.lower() == "buy").sum()) if "Side" in df.columns else 0
        sell_orders = int((df["Side"].astype(str).str.lower() == "sell").sum()) if "Side" in df.columns else 0
        avg_commission = float(df["Commission"].fillna(0.0).mean()) if "Commission" in df.columns else 0.0
        avg_slippage = float(df["Slippage"].fillna(0.0).mean()) if "Slippage" in df.columns else 0.0

        return {
            "total_orders": total_orders,
            "filled_orders": filled_orders,
            "buy_orders": buy_orders,
            "sell_orders": sell_orders,
            "avg_commission": avg_commission,
            "avg_slippage": avg_slippage,
        }

    def closed_trade_stats(self) -> dict:
        df = self.closed_trades_df.copy()
        if df.empty:
            return {
                "closed_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "gross_pnl": 0.0,
                "net_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "avg_holding_period_days": 0.0,
            }

        net = df["Net P&L"].fillna(0.0)
        gross = df["Gross P&L"].fillna(0.0)
        wins = df[net > 0]
        losses = df[net < 0]

        win_count = int(len(wins))
        loss_count = int(len(losses))
        total = int(len(df))
        win_rate = float(win_count / total) if total > 0 else 0.0

        avg_win = float(wins["Net P&L"].mean()) if win_count > 0 else 0.0
        avg_loss = float(losses["Net P&L"].mean()) if loss_count > 0 else 0.0

        gross_profit = float(wins["Net P&L"].sum()) if win_count > 0 else 0.0
        gross_loss_abs = float(abs(losses["Net P&L"].sum())) if loss_count > 0 else 0.0
        profit_factor = gross_profit / gross_loss_abs if gross_loss_abs > 0 else 0.0

        expectancy = (win_rate * avg_win) + ((1.0 - win_rate) * avg_loss)
        avg_holding_period = float(df["Holding Period (Days)"].fillna(0.0).mean()) if "Holding Period (Days)" in df.columns else 0.0

        return {
            "closed_trades": total,
            "wins": win_count,
            "losses": loss_count,
            "win_rate": win_rate,
            "gross_pnl": float(gross.sum()),
            "net_pnl": float(net.sum()),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "avg_holding_period_days": avg_holding_period,
        }

    def attribution_by_symbol(self) -> pd.DataFrame:
        df = self.closed_trades_df.copy()
        if df.empty or "Symbol" not in df.columns:
            return pd.DataFrame()

        out = (
            df.groupby("Symbol", as_index=False)
            .agg(
                Closed_Trades=("Symbol", "count"),
                Gross_PnL=("Gross P&L", "sum"),
                Net_PnL=("Net P&L", "sum"),
                Avg_Holding_Days=("Holding Period (Days)", "mean"),
            )
            .sort_values("Net_PnL", ascending=False)
        )
        return out