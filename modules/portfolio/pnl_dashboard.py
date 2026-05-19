from __future__ import annotations

from typing import Dict, List
from sqlalchemy import text
import numpy as np
import pandas as pd
import streamlit as st

from modules.market_data.service import get_price_history





# ---------------------------------------------------------
# DB / SCHEMA HELPERS
# ---------------------------------------------------------

def _table_exists(db, table_name: str) -> bool:
    try:
        row = db.execute(
            text(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table' AND name=:table_name
                """
            ),
            {"table_name": table_name},
        ).fetchone()
        return row is not None
    except Exception as e:
        print(f"PNL DASHBOARD table_exists error for {table_name}: {e}")
        return False


def _get_table_columns(db, table_name: str) -> List[str]:
    try:
        rows = db.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return [r[1] for r in rows]
    except Exception as e:
        print(f"PNL DASHBOARD get_table_columns error for {table_name}: {e}")
        return []


def _read_sql_df(db, query: str, params: dict | None = None) -> pd.DataFrame:
    try:
        if hasattr(db, "bind") and db.bind is not None:
            return pd.read_sql_query(text(query), db.bind, params=params or {})
        conn = db.connection() if hasattr(db, "connection") else None
        if conn is not None:
            return pd.read_sql_query(text(query), conn, params=params or {})
    except Exception as e:
        print("PNL DASHBOARD read_sql_df error:", e)

    return pd.DataFrame()


# ---------------------------------------------------------
# CORE DATA LOADERS
# ---------------------------------------------------------

def _get_cash_balance(db, portfolio_id: str) -> float:
    if not _table_exists(db, "portfolio_cash_ledger"):
        return 0.0

    try:
        row = db.execute(
            text(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM portfolio_cash_ledger
                WHERE portfolio_id = :pid
                """
            ),
            {"pid": portfolio_id},
        ).fetchone()

        return float(row[0] or 0.0) if row else 0.0
    except Exception as e:
        print("PNL DASHBOARD cash balance error:", e)
        return 0.0


def _get_positions_df(db, portfolio_id: str) -> pd.DataFrame:
    if not _table_exists(db, "portfolio_positions"):
        return pd.DataFrame()

    cols = _get_table_columns(db, "portfolio_positions")
    select_cols = [
        c for c in [
            "symbol",
            "qty",
            "avg_cost",
            "market_price",
            "market_value",
            "unrealized_pnl",
            "realized_pnl",
            "updated_at",
        ] if c in cols
    ]

    if not select_cols:
        return pd.DataFrame()

    q = f"""
        SELECT {", ".join(select_cols)}
        FROM portfolio_positions
        WHERE portfolio_id = :pid
    """
    df = _read_sql_df(db, q, {"pid": portfolio_id})

    if df.empty:
        return df

    for c in ["qty", "avg_cost", "market_price", "market_value", "unrealized_pnl", "realized_pnl"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    if "updated_at" in df.columns:
        df["updated_at"] = pd.to_datetime(df["updated_at"], errors="coerce")

    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()

    return df


def _get_closed_trades_df(db, portfolio_id: str) -> pd.DataFrame:
    if not _table_exists(db, "closed_trades"):
        return pd.DataFrame()

    cols = _get_table_columns(db, "closed_trades")
    select_cols = [
        c for c in [
            "symbol",
            "opened_at",
            "closed_at",
            "entry_qty",
            "exit_qty",
            "entry_price",
            "exit_price",
            "gross_pnl",
            "net_pnl",
            "commission",
            "slippage",
            "holding_period_days",
            "side_open",
            "side_close",
            "notes",
        ] if c in cols
    ]

    if not select_cols:
        return pd.DataFrame()

    q = f"""
        SELECT {", ".join(select_cols)}
        FROM closed_trades
        WHERE portfolio_id = :pid
        ORDER BY closed_at DESC
    """
    df = _read_sql_df(db, q, {"pid": portfolio_id})

    if df.empty:
        return df

    for c in ["opened_at", "closed_at"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    for c in [
        "entry_qty", "exit_qty", "entry_price", "exit_price",
        "gross_pnl", "net_pnl", "commission", "slippage", "holding_period_days"
    ]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()

    return df


def _get_equity_curve_df(db, portfolio_id: str) -> pd.DataFrame:
    """
    Priority:
    1. portfolio_snapshots
    2. cumulative cash ledger fallback
    """
    if _table_exists(db, "portfolio_snapshots"):
        cols = _get_table_columns(db, "portfolio_snapshots")

        time_col = next((c for c in ["asof", "created_at", "snapshot_at", "updated_at"] if c in cols), None)
        equity_col = next((c for c in ["total_equity", "equity", "portfolio_value", "nav", "total_value"] if c in cols), None)

        if time_col and equity_col:
            q = f"""
                SELECT {time_col} AS ts, {equity_col} AS equity
                FROM portfolio_snapshots
                WHERE portfolio_id = :pid
                ORDER BY {time_col} ASC
            """
            df = _read_sql_df(db, q, {"pid": portfolio_id})
            if not df.empty:
                df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
                df["equity"] = pd.to_numeric(df["equity"], errors="coerce").fillna(0.0)
                df = df.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)
                return df

    if _table_exists(db, "portfolio_cash_ledger"):
        cols = _get_table_columns(db, "portfolio_cash_ledger")
        time_col = next((c for c in ["created_at", "asof", "updated_at"] if c in cols), None)

        if time_col and "amount" in cols:
            q = f"""
                SELECT {time_col} AS ts, amount
                FROM portfolio_cash_ledger
                WHERE portfolio_id = :pid
                ORDER BY {time_col} ASC
            """
            df = _read_sql_df(db, q, {"pid": portfolio_id})
            if not df.empty:
                df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
                df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
                df = df.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)
                df["equity"] = df["amount"].cumsum()
                return df[["ts", "equity"]]

    return pd.DataFrame(columns=["ts", "equity"])


# ---------------------------------------------------------
# LIVE MARK-TO-MARKET
# ---------------------------------------------------------

def _refresh_live_market_values(db, positions: pd.DataFrame) -> pd.DataFrame:
    """
    Refreshes current market prices for open positions using market_data.service.
    Does not write to DB. Safe dashboard-only overlay.
    """
    if positions.empty or "symbol" not in positions.columns:
        return positions

    out = positions.copy()
    latest_prices = {}

    for symbol in out["symbol"].dropna().astype(str).unique():
        try:
            hist = get_price_history(db, symbol, period="1mo", interval="1d", force_refresh=False)
            if hist is not None and not hist.empty and "Close" in hist.columns:
                latest_prices[symbol] = float(hist["Close"].iloc[-1])
        except Exception as e:
            print(f"PNL DASHBOARD refresh price error for {symbol}: {e}")

    if latest_prices:
        out["live_market_price"] = out["symbol"].map(latest_prices).fillna(out.get("market_price", 0.0))
    else:
        out["live_market_price"] = out.get("market_price", 0.0)

    out["live_market_price"] = pd.to_numeric(out["live_market_price"], errors="coerce").fillna(0.0)

    if "qty" in out.columns:
        out["live_market_value"] = out["qty"] * out["live_market_price"]
    else:
        out["live_market_value"] = 0.0

    if "avg_cost" in out.columns and "qty" in out.columns:
        out["live_unrealized_pnl"] = (out["live_market_price"] - out["avg_cost"]) * out["qty"]
    else:
        out["live_unrealized_pnl"] = out.get("unrealized_pnl", 0.0)

    return out


# ---------------------------------------------------------
# BENCHMARK / RISK / STATS
# ---------------------------------------------------------

def _get_benchmark_curve(db, symbol: str = "SPY", period: str = "1y") -> pd.DataFrame:
    try:
        df = get_price_history(db, symbol, period=period, interval="1d", force_refresh=False)
        if df is None or df.empty or "Date" not in df.columns or "Close" not in df.columns:
            return pd.DataFrame(columns=["ts", "close", "normalized"])

        out = df[["Date", "Close"]].copy()
        out.rename(columns={"Date": "ts", "Close": "close"}, inplace=True)
        out["ts"] = pd.to_datetime(out["ts"], errors="coerce")
        out["close"] = pd.to_numeric(out["close"], errors="coerce").fillna(0.0)
        out = out.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)

        if not out.empty and float(out["close"].iloc[0]) != 0:
            out["normalized"] = 100.0 * out["close"] / float(out["close"].iloc[0])
        else:
            out["normalized"] = 100.0

        return out

    except Exception as e:
        print("PNL DASHBOARD benchmark error:", e)
        return pd.DataFrame(columns=["ts", "close", "normalized"])


def _compute_drawdown(equity_curve: pd.DataFrame) -> Dict[str, float]:
    if equity_curve.empty or "equity" not in equity_curve.columns:
        return {
            "peak_equity": 0.0,
            "current_equity": 0.0,
            "max_drawdown_pct": 0.0,
            "current_drawdown_pct": 0.0,
        }

    s = equity_curve["equity"].astype(float).copy()
    running_peak = s.cummax().replace(0, np.nan)
    dd = (s - running_peak) / running_peak
    dd = dd.fillna(0.0)

    return {
        "peak_equity": float(running_peak.max()) if len(running_peak) else 0.0,
        "current_equity": float(s.iloc[-1]) if len(s) else 0.0,
        "max_drawdown_pct": float(dd.min()) if len(dd) else 0.0,
        "current_drawdown_pct": float(dd.iloc[-1]) if len(dd) else 0.0,
    }


def _compute_return_stats(equity_curve: pd.DataFrame) -> Dict[str, float]:
    if equity_curve.empty or len(equity_curve) < 2:
        return {
            "daily_return_mean": 0.0,
            "daily_volatility": 0.0,
            "annualized_volatility": 0.0,
            "sharpe_ratio": 0.0,
        }

    s = equity_curve["equity"].astype(float).copy()
    rets = s.pct_change().replace([np.inf, -np.inf], np.nan).dropna()

    if rets.empty:
        return {
            "daily_return_mean": 0.0,
            "daily_volatility": 0.0,
            "annualized_volatility": 0.0,
            "sharpe_ratio": 0.0,
        }

    daily_mean = float(rets.mean())
    daily_vol = float(rets.std())
    ann_vol = float(daily_vol * np.sqrt(252))
    sharpe = float((daily_mean / daily_vol) * np.sqrt(252)) if daily_vol > 0 else 0.0

    return {
        "daily_return_mean": daily_mean,
        "daily_volatility": daily_vol,
        "annualized_volatility": ann_vol,
        "sharpe_ratio": sharpe,
    }


def _build_summary(positions: pd.DataFrame, closed: pd.DataFrame, cash: float) -> Dict[str, float]:
    market_value = float(positions["market_value"].sum()) if "market_value" in positions.columns else 0.0
    unrealized = float(positions["unrealized_pnl"].sum()) if "unrealized_pnl" in positions.columns else 0.0
    realized_open_positions = float(positions["realized_pnl"].sum()) if "realized_pnl" in positions.columns else 0.0
    realized_closed = float(closed["net_pnl"].sum()) if "net_pnl" in closed.columns else 0.0
    total_equity = cash + market_value
    total_realized = realized_open_positions + realized_closed

    return {
        "cash": cash,
        "market_value": market_value,
        "total_equity": total_equity,
        "unrealized_pnl": unrealized,
        "realized_pnl": total_realized,
        "open_positions": int(len(positions)) if not positions.empty else 0,
        "closed_trades": int(len(closed)) if not closed.empty else 0,
    }


def _build_trade_stats(closed: pd.DataFrame) -> Dict[str, float]:
    if closed.empty or "net_pnl" not in closed.columns:
        return {
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "avg_holding_days": 0.0,
            "expectancy": 0.0,
        }

    wins = closed[closed["net_pnl"] > 0]
    losses = closed[closed["net_pnl"] < 0]

    gross_wins = float(wins["net_pnl"].sum()) if not wins.empty else 0.0
    gross_losses = abs(float(losses["net_pnl"].sum())) if not losses.empty else 0.0

    win_rate = float(len(wins) / len(closed)) if len(closed) > 0 else 0.0
    avg_win = float(wins["net_pnl"].mean()) if not wins.empty else 0.0
    avg_loss_abs = abs(float(losses["net_pnl"].mean())) if not losses.empty else 0.0
    expectancy = (win_rate * avg_win) - ((1.0 - win_rate) * avg_loss_abs)

    return {
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": float(losses["net_pnl"].mean()) if not losses.empty else 0.0,
        "profit_factor": float(gross_wins / gross_losses) if gross_losses > 0 else 0.0,
        "best_trade": float(closed["net_pnl"].max()) if not closed.empty else 0.0,
        "worst_trade": float(closed["net_pnl"].min()) if not closed.empty else 0.0,
        "avg_holding_days": float(closed["holding_period_days"].mean()) if "holding_period_days" in closed.columns and not closed.empty else 0.0,
        "expectancy": float(expectancy),
    }


def _build_symbol_trade_breakdown(closed: pd.DataFrame) -> pd.DataFrame:
    if closed.empty or "symbol" not in closed.columns or "net_pnl" not in closed.columns:
        return pd.DataFrame()

    df = closed.copy()
    df["is_win"] = (df["net_pnl"] > 0).astype(int)

    grouped = (
        df.groupby("symbol", dropna=False)
        .agg(
            trades=("symbol", "count"),
            wins=("is_win", "sum"),
            total_net_pnl=("net_pnl", "sum"),
            avg_net_pnl=("net_pnl", "mean"),
            best_trade=("net_pnl", "max"),
            worst_trade=("net_pnl", "min"),
        )
        .reset_index()
    )

    grouped["win_rate"] = np.where(grouped["trades"] > 0, grouped["wins"] / grouped["trades"], 0.0)
    grouped = grouped.sort_values(["total_net_pnl", "trades"], ascending=[False, False]).reset_index(drop=True)
    return grouped


def _build_normalized_comparison(equity_curve: pd.DataFrame, benchmark_curve: pd.DataFrame) -> pd.DataFrame:
    if equity_curve.empty:
        return pd.DataFrame()

    eq = equity_curve.copy()
    eq["ts"] = pd.to_datetime(eq["ts"], errors="coerce")
    eq["equity"] = pd.to_numeric(eq["equity"], errors="coerce").fillna(0.0)
    eq = eq.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)

    if eq.empty:
        return pd.DataFrame()

    start_equity = float(eq["equity"].iloc[0]) if float(eq["equity"].iloc[0]) != 0 else 1.0
    eq["Portfolio"] = 100.0 * eq["equity"] / start_equity
    eq = eq[["ts", "Portfolio"]]

    if benchmark_curve.empty:
        return eq.set_index("ts")

    bm = benchmark_curve[["ts", "normalized"]].copy()
    bm.rename(columns={"normalized": "SPY"}, inplace=True)
    bm["ts"] = pd.to_datetime(bm["ts"], errors="coerce")
    bm = bm.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)

    merged = pd.merge_asof(
        eq.sort_values("ts"),
        bm.sort_values("ts"),
        on="ts",
        direction="nearest",
    )

    return merged.set_index("ts")


# ---------------------------------------------------------
# MAIN RENDER
# ---------------------------------------------------------

def render_pnl_dashboard(db_session, portfolio_id: str):
    # ---------------------------------
    # ✅ PREVENT DOUBLE RENDER PER RUN
    # ---------------------------------


    st.header("PnL & Performance Dashboard")
    print("🔥 PNL DASHBOARD CALLED")
    import uuid

    unique_key = f"refresh_mtm_{portfolio_id}_{uuid.uuid4().hex[:6]}"

    refresh_live = st.button(
        "Refresh Live Mark-to-Market",
        key=f"pnl_refresh_mtm_{portfolio_id}_v1"
    )

    cash = _get_cash_balance(db_session, portfolio_id)
    positions = _get_positions_df(db_session, portfolio_id)
    closed = _get_closed_trades_df(db_session, portfolio_id)
    equity_curve = _get_equity_curve_df(db_session, portfolio_id)

    if refresh_live and not positions.empty:
        positions_live = _refresh_live_market_values(db_session, positions)
    else:
        positions_live = positions.copy()

    # If live prices exist, use them in summary
    if not positions_live.empty and "live_market_value" in positions_live.columns:
        positions_for_summary = positions_live.copy()
        positions_for_summary["market_value"] = positions_for_summary["live_market_value"]
        positions_for_summary["unrealized_pnl"] = positions_for_summary.get("live_unrealized_pnl", positions_for_summary.get("unrealized_pnl", 0.0))
    else:
        positions_for_summary = positions_live.copy()

    summary = _build_summary(positions_for_summary, closed, cash)
    trade_stats = _build_trade_stats(closed)
    drawdown_stats = _compute_drawdown(equity_curve)
    return_stats = _compute_return_stats(equity_curve)
    symbol_breakdown = _build_symbol_trade_breakdown(closed)
    benchmark_curve = _get_benchmark_curve(db_session, symbol="SPY", period="1y")
    comparison_df = _build_normalized_comparison(equity_curve, benchmark_curve)

    # -----------------------------------------------------
    # TOP METRICS
    # -----------------------------------------------------
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Equity", f"${summary['total_equity']:,.2f}")
    m2.metric("Available Cash", f"${summary['cash']:,.2f}")
    m3.metric("Market Value", f"${summary['market_value']:,.2f}")
    m4.metric("Open Positions", f"{summary['open_positions']}")

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Unrealized PnL", f"${summary['unrealized_pnl']:,.2f}")
    m6.metric("Realized PnL", f"${summary['realized_pnl']:,.2f}")
    m7.metric("Closed Trades", f"{summary['closed_trades']}")
    m8.metric("Win Rate", f"{trade_stats['win_rate']:.1%}")

    # -----------------------------------------------------
    # BENCHMARK COMPARISON
    # -----------------------------------------------------
    st.subheader("Benchmark Comparison (Portfolio vs SPY)")
    if not comparison_df.empty:
        st.line_chart(comparison_df)
    else:
        st.info("Not enough portfolio history yet to compare against SPY.")

    # -----------------------------------------------------
    # EQUITY CURVE
    # -----------------------------------------------------
    st.subheader("Equity Curve")
    if not equity_curve.empty:
        curve_df = equity_curve.copy().set_index("ts")
        st.line_chart(curve_df["equity"])
    else:
        st.info("No equity curve data yet. Snapshots or ledger history will populate this as activity grows.")

    # -----------------------------------------------------
    # DRAWDOWN / RISK
    # -----------------------------------------------------
    st.subheader("Drawdown & Risk Metrics")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Peak Equity", f"${drawdown_stats['peak_equity']:,.2f}")
    r2.metric("Current Drawdown", f"{drawdown_stats['current_drawdown_pct']:.2%}")
    r3.metric("Max Drawdown", f"{drawdown_stats['max_drawdown_pct']:.2%}")
    r4.metric("Sharpe Ratio", f"{return_stats['sharpe_ratio']:.2f}")

    r5, r6, r7 = st.columns(3)
    r5.metric("Avg Daily Return", f"{return_stats['daily_return_mean']:.3%}")
    r6.metric("Daily Volatility", f"{return_stats['daily_volatility']:.3%}")
    r7.metric("Annualized Volatility", f"{return_stats['annualized_volatility']:.2%}")

    # -----------------------------------------------------
    # TRADE ANALYTICS
    # -----------------------------------------------------
    st.subheader("Trade Analytics")
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Avg Win", f"${trade_stats['avg_win']:,.2f}")
    t2.metric("Avg Loss", f"${trade_stats['avg_loss']:,.2f}")
    t3.metric("Profit Factor", f"{trade_stats['profit_factor']:.2f}")
    t4.metric("Expectancy / Trade", f"${trade_stats['expectancy']:,.2f}")

    t5, t6, t7 = st.columns(3)
    t5.metric("Best Trade", f"${trade_stats['best_trade']:,.2f}")
    t6.metric("Worst Trade", f"${trade_stats['worst_trade']:,.2f}")
    t7.metric("Avg Hold (Days)", f"{trade_stats['avg_holding_days']:.2f}")

    # -----------------------------------------------------
    # OPEN POSITIONS
    # -----------------------------------------------------
    st.subheader("Open Positions")
    if not positions_live.empty:
        display_cols = [
            c for c in [
                "symbol",
                "qty",
                "avg_cost",
                "market_price",
                "live_market_price",
                "market_value",
                "live_market_value",
                "unrealized_pnl",
                "live_unrealized_pnl",
                "realized_pnl",
                "updated_at",
            ] if c in positions_live.columns
        ]
        st.dataframe(positions_live[display_cols], use_container_width=True)
    else:
        st.info("No open positions.")

    # -----------------------------------------------------
    # SYMBOL BREAKDOWN
    # -----------------------------------------------------
    st.subheader("Trade Breakdown by Symbol")
    if not symbol_breakdown.empty:
        st.dataframe(symbol_breakdown, use_container_width=True)
    else:
        st.info("No closed trades yet for symbol-level analytics.")

    # -----------------------------------------------------
    # CLOSED TRADES
    # -----------------------------------------------------
    st.subheader("Closed Trades")
    if not closed.empty:
        display_cols = [
            c for c in [
                "symbol",
                "opened_at",
                "closed_at",
                "entry_qty",
                "exit_qty",
                "entry_price",
                "exit_price",
                "gross_pnl",
                "net_pnl",
                "commission",
                "slippage",
                "holding_period_days",
                "side_open",
                "side_close",
                "notes",
            ] if c in closed.columns
        ]
        st.dataframe(closed[display_cols], use_container_width=True)
    else:
        st.info("No closed trades yet.")