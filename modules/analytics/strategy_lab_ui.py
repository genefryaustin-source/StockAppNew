"""
modules/analytics/strategy_lab_ui.py

Strategy Lab — complete page combining:
  1. Factor Strategy Discovery  (existing strategy_discovery logic, fixed)
  2. Strategy Backtester        (NEW — historical simulation with stats)
  3. Strategy Library           (saved strategies from DB)

Fixes all issues with the original Strategy Lab:
  - Has its own data loading (no longer depends on AI Rankings session_state)
  - Handles missing price_cache gracefully by fetching fresh
  - All three sub-pages are accessible via tabs
  - Proper route wiring instructions for app.py included

Add to app.py:
    elif page == "Strategy Lab":
        from modules.analytics.strategy_lab_ui import render_strategy_lab
        render_strategy_lab(db, user)

    elif page == "Strategy Discovery":
        from modules.analytics.strategy_lab_ui import render_strategy_lab
        render_strategy_lab(db, user)

    elif page == "Strategy Library":
        from modules.analytics.strategy_lab_ui import render_strategy_lab
        render_strategy_lab(db, user)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from modules.analytics.backtest_engine import (
    BacktestConfig,
    BacktestResult,
    run_factor_backtest,
    run_indicator_backtest,
)
from modules.analytics.strategy_discovery import discover_strategies
from modules.analytics.strategy_service import (
    list_discovered_strategies,
    save_discovered_strategies,
)


# ─────────────────────────────────────────────────────────────
# Data loaders — independent from session_state
# ─────────────────────────────────────────────────────────────

def _load_analytics_data(db, tenant_id: str, limit: int = 200) -> pd.DataFrame:
    """
    Load analytics snapshots directly from DB.
    Returns a DataFrame with Symbol + factor columns.
    Previously this depended on session_state['ai_rank_df'] from AI Rankings.
    """
    try:
        from modules.analytics.models import AnalyticsSnapshot
        rows = (
            db.query(AnalyticsSnapshot)
            .filter(AnalyticsSnapshot.tenant_id == tenant_id)
            .order_by(AnalyticsSnapshot.composite_score.desc())
            .limit(limit)
            .all()
        )
        if not rows:
            return pd.DataFrame()

        return pd.DataFrame([{
            "Symbol":       r.symbol,
            "Sector":       r.sector or "Unknown",
            "Rating":       r.rating or "N/A",
            "Composite":    round(float(r.composite_score or 0), 1),
            "Quality":      round(float(r.quality_score or 0), 1),
            "Growth":       round(float(r.growth_score or 0), 1),
            "Value":        round(float(r.value_score or 0), 1),
            "Momentum":     round(float(r.momentum_score or 0), 1),
            "Risk":         round(float(r.risk_score or 0), 1),
            "Alpha Score":  round(float(r.composite_score or 0), 1),
            "RSI":          round(float(r.rsi_14 or 0), 1),
        } for r in rows])
    except Exception as e:
        st.error(f"Failed to load analytics data: {e}")
        return pd.DataFrame()


def _compute_factor_scores_from_price(db, symbols: list[str]) -> pd.DataFrame:
    """
    Compute genuinely distinct factor scores from price data for symbols
    without analytics snapshots. Each factor uses different price signals:

      Momentum  — 3-month price return (short-term trend strength)
      Quality   — price consistency: % of days above 50d SMA (stability proxy)
      Growth    — 6-month return annualised (medium-term growth rate)
      Value     — mean-reversion score: how far below 52w high (cheaper = higher value)
      Composite — weighted blend: 35% momentum, 30% quality, 20% growth, 15% value
      Alpha     — risk-adjusted return: 3m return / 20d volatility (Sharpe-like)
    """
    from modules.market_data.price_history_service import load_price_history
    import math

    rows = []
    for sym in symbols:
        try:
            db.rollback()
        except Exception:
            pass
        try:
            df = load_price_history(db, sym)
            if df is None or df.empty:
                from modules.market_data.service import get_price_history_internal
                df = get_price_history_internal(db, sym, period="1y", interval="1d",
                                                force_refresh=True)
                if df is None or df.empty:
                    continue
                if isinstance(df.index, pd.DatetimeIndex):
                    df = df.reset_index()

            close_col = next((c for c in df.columns if c.lower() == "close"), None)
            if close_col is None:
                continue
            closes = pd.to_numeric(df[close_col], errors="coerce").dropna().tolist()
            if len(closes) < 20:
                continue

            n = len(closes)
            last = closes[-1]

            # ── MOMENTUM: 3-month (63-day) return → 0-100
            # Positive return → above 50, negative → below 50
            base_63  = closes[-min(63, n)]
            mom_ret  = (last - base_63) / base_63 * 100 if base_63 else 0
            momentum = min(100, max(0, 50 + mom_ret * 1.5))

            # ── QUALITY: price consistency above 50d SMA → 0-100
            # Higher = price reliably above its 50d moving average (trend quality)
            window  = min(50, n)
            sma50   = sum(closes[-window:]) / window
            # % of last 20 days that closed above the 50d SMA
            recent  = closes[-min(20, n):]
            above   = sum(1 for p in recent if p > sma50)
            quality = round(above / len(recent) * 100, 1)

            # ── GROWTH: 6-month (126-day) annualised return → 0-100
            # Measures medium-term growth trajectory
            base_126 = closes[-min(126, n)]
            ret_6m   = (last - base_126) / base_126 * 100 if base_126 else 0
            # Annualise the 6m return
            ret_ann  = ret_6m * 2
            growth   = min(100, max(0, 50 + ret_ann * 0.8))

            # ── VALUE: distance below 52w high → 0-100
            # High score = further below 52w high = potentially undervalued
            high_52w = max(closes[-min(252, n):])
            pct_below = (high_52w - last) / high_52w * 100 if high_52w else 0
            # 0% below = score 10 (expensive), 30% below = score 70 (cheap)
            value = min(100, max(0, 10 + pct_below * 2))

            # ── ALPHA SCORE: risk-adjusted momentum (Sharpe-like)
            # 3m return / 20d volatility — higher = better risk-adjusted performance
            daily_rets = [(closes[i] - closes[i-1]) / closes[i-1]
                          for i in range(max(1, n-20), n) if closes[i-1] > 0]
            if len(daily_rets) > 1:
                mean_ret = sum(daily_rets) / len(daily_rets)
                variance = sum((r - mean_ret)**2 for r in daily_rets) / len(daily_rets)
                vol_20d  = math.sqrt(variance) * math.sqrt(252) * 100  # annualised %
            else:
                vol_20d = 20.0
            sharpe_proxy = mom_ret / vol_20d if vol_20d > 0 else 0
            alpha_score  = min(100, max(0, 50 + sharpe_proxy * 15))

            # ── COMPOSITE: weighted blend
            composite = round(
                momentum * 0.35 +
                quality  * 0.30 +
                growth   * 0.20 +
                value    * 0.15,
                1
            )

            # ── RSI (14-day)
            deltas = [closes[i] - closes[i-1] for i in range(max(1, n-14), n)]
            gains  = [d for d in deltas if d > 0]
            losses = [-d for d in deltas if d < 0]
            avg_g  = sum(gains)  / len(gains)  if gains  else 0.001
            avg_l  = sum(losses) / len(losses) if losses else 0.001
            rsi    = round(100 - (100 / (1 + avg_g / avg_l)), 1)

            rows.append({
                "Symbol":     sym.upper(),
                "Sector":     "Unknown",
                "Rating":     "N/A",
                "Composite":  composite,
                "Quality":    quality,
                "Growth":     round(growth, 1),
                "Value":      round(value, 1),
                "Momentum":   round(momentum, 1),
                "Risk":       round(100 - quality, 1),
                "Alpha Score": round(alpha_score, 1),
                "RSI":        rsi,
            })
        except Exception as e:
            print(f"[compute_scores] {sym}: {e}")

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _load_analytics_data_all(db) -> pd.DataFrame:
    """Load analytics snapshots across ALL tenants — used as fallback when tenant filter finds nothing."""
    try:
        from modules.analytics.models import AnalyticsSnapshot
        rows = (
            db.query(AnalyticsSnapshot)
            .order_by(AnalyticsSnapshot.composite_score.desc())
            .limit(500)
            .all()
        )
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([{
            "Symbol":    r.symbol,
            "Sector":    r.sector or "Unknown",
            "Rating":    r.rating or "N/A",
            "Composite": round(float(r.composite_score or 0), 1),
            "Quality":   round(float(r.quality_score or 0), 1),
            "Growth":    round(float(r.growth_score or 0), 1),
            "Value":     round(float(r.value_score or 0), 1),
            "Momentum":  round(float(r.momentum_score or 0), 1),
            "Risk":      round(float(r.risk_score or 0), 1),
            "Alpha Score": round(float(r.composite_score or 0), 1),
        } for r in rows])
    except Exception:
        return pd.DataFrame()


def _load_portfolios(db, tenant_id: str) -> list:
    """Load available portfolios for the tenant."""
    try:
        from sqlalchemy import text
        rows = db.execute(text(
            "SELECT id, name FROM portfolios WHERE tenant_id = :tid ORDER BY created_at DESC"
        ), {"tid": tenant_id}).fetchall()
        return rows
    except Exception:
        return []


def _get_portfolio_symbols(db, portfolio_id: str) -> list[str]:
    """Get symbols of open positions in a portfolio."""
    try:
        from sqlalchemy import text
        rows = db.execute(text("""
            SELECT DISTINCT symbol FROM portfolio_positions
            WHERE portfolio_id = :pid AND qty > 0
        """), {"pid": portfolio_id}).fetchall()
        return [str(r[0]).upper().strip() for r in rows if r[0]]
    except Exception:
        return []


def _load_price_cache(db, symbols: list[str], period: str = "2y") -> dict:
    """
    Load price history by querying the price_history DB table directly
    for the exact symbols requested. Falls back to Polygon for any
    symbols not found in the DB.
    """
    from modules.market_data.price_history_service import load_price_history
    from modules.market_data.service import get_price_history_internal

    cache = {}
    missing = []
    prog = st.progress(0.0, text="Loading price history from DB…")
    n = len(symbols)

    # Step 1: load from DB directly — this guarantees the right symbols
    for i, sym in enumerate(symbols):
        prog.progress((i + 1) / n, text=f"DB lookup: {sym}…")
        try:
            db.rollback()
        except Exception:
            pass
        try:
            df = load_price_history(db, sym)
            if df is not None and not df.empty and len(df) >= 20:
                # load_price_history sets index to date objects (not DatetimeIndex)
                # Always convert to DatetimeIndex for proper series alignment
                df.index = pd.to_datetime(df.index)
                if "Close" not in df.columns and "close" in df.columns:
                    df = df.rename(columns={"close": "Close"})
                cache[sym] = df
            else:
                missing.append(sym)
        except Exception:
            missing.append(sym)

    prog.empty()

    # Step 2: for symbols not in DB, fetch from Polygon
    if missing:
        st.caption(f"Fetching {len(missing)} symbols from Polygon…")
        prog2 = st.progress(0.0, text="Fetching from Polygon…")
        fetch_period = "1y"

        for i, sym in enumerate(missing):
            prog2.progress((i + 1) / len(missing), text=f"Polygon: {sym}…")
            try:
                db.rollback()
            except Exception:
                pass
            try:
                df = get_price_history_internal(
                    db, sym,
                    period=fetch_period,
                    interval="1d",
                    force_refresh=True,
                )
                if df is not None and not df.empty and len(df) >= 20:
                    # Set DatetimeIndex if not already set
                    if not isinstance(df.index, pd.DatetimeIndex):
                        for col in ("Date", "date", "Datetime"):
                            if col in df.columns:
                                df = df.set_index(pd.to_datetime(df[col]))
                                df = df.drop(columns=[col], errors="ignore")
                                break
                    if "Close" not in df.columns and "close" in df.columns:
                        df = df.rename(columns={"close": "Close"})
                    cache[sym] = df
            except Exception as e:
                print(f"[backtest] Polygon failed {sym}: {e}")

        prog2.empty()

    st.caption(
        f"✅ Price data: {len(cache)}/{n} symbols loaded "
        f"({n - len(missing)} from DB, {len(cache) - (n - len(missing))} from Polygon)."
    )
    return cache


# ─────────────────────────────────────────────────────────────
# Main page
# ─────────────────────────────────────────────────────────────

def render_strategy_lab(db, user: dict):
    tenant_id = user.get("tenant_id", "")

    st.header("⚗️ Strategy Lab")
    st.caption(
        "Discover factor-based strategies, backtest them against historical data, "
        "and save the best ones to your Strategy Library."
    )

    tab_backtest, tab_discovery, tab_library = st.tabs([
        "📈 Backtester",
        "🔬 Strategy Discovery",
        "📚 Strategy Library",
    ])

    with tab_backtest:
        _render_backtester_tab(db, tenant_id)

    with tab_discovery:
        _render_discovery_tab(db, user, tenant_id)

    with tab_library:
        _render_library_tab(db, tenant_id)


# ─────────────────────────────────────────────────────────────
# Tab 1 — Backtester
# ─────────────────────────────────────────────────────────────

def _render_backtester_tab(db, tenant_id: str):
    st.subheader("Strategy Backtester")
    st.caption(
        "Simulate how a strategy would have performed historically. "
        "Choose factor-based (rank top stocks by score) or indicator-based (entry signal)."
    )

    mode = st.radio(
        "Backtest mode",
        ["📊 Factor Strategy", "⚗️ Indicator Strategy"],
        horizontal=True,
        key="bt_mode",
    )

    # ── Config ────────────────────────────────────────────────
    with st.expander("⚙️ Backtest Configuration", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            strategy_name = st.text_input("Strategy name", value="My Strategy", key="bt_name")
            start_date    = st.date_input("Start date",
                value=pd.Timestamp("2022-01-01"), key="bt_start")
            end_date      = st.date_input("End date",
                value=pd.Timestamp.today(), key="bt_end")
        with c2:
            initial_capital  = st.number_input("Initial capital ($)",
                min_value=1000.0, value=100000.0, step=10000.0, key="bt_capital")
            position_size    = st.slider("Position size (%)",
                1.0, 25.0, 10.0, key="bt_pos_size")
            max_positions    = st.slider("Max positions",
                2, 30, 10, key="bt_max_pos")
        with c3:
            stop_loss     = st.slider("Stop loss (%)",
                0.0, 25.0, 0.0, key="bt_sl",
                help="0 = no stop loss")
            take_profit   = st.slider("Take profit (%)",
                0.0, 50.0, 0.0, key="bt_tp",
                help="0 = no take profit")
            hold_days     = st.slider("Hold period (days)",
                0, 252, 0, key="bt_hold",
                help="0 = hold until exit signal")
            rebalance_freq= st.selectbox("Rebalance frequency",
                ["daily", "weekly", "monthly"], index=2, key="bt_rebal")

    config = BacktestConfig(
        strategy_name=strategy_name,
        start_date=str(start_date),
        end_date=str(end_date),
        initial_capital=initial_capital,
        position_size_pct=position_size,
        max_positions=max_positions,
        stop_loss_pct=stop_loss,
        take_profit_pct=take_profit,
        hold_days=hold_days,
        rebalance_freq=rebalance_freq,
    )

    # ── Factor mode setup ─────────────────────────────────────
    if "📊 Factor Strategy" in mode:
        st.markdown("#### Factor Settings")

        # Scope — portfolio holdings or full universe
        scope = st.radio(
            "Test on",
            ["🌐 Full Universe", "💼 My Portfolio Holdings"],
            horizontal=True,
            key="bt_scope",
        )

        # Portfolio selector (shown only when portfolio scope chosen)
        selected_portfolio_id = None
        if "💼 My Portfolio" in scope:
            portfolios = _load_portfolios(db, tenant_id)
            if not portfolios:
                st.warning("No portfolios found. Create one in the Portfolio page first.")
            else:
                port_opts = {str(p[0]): p[1] for p in portfolios}
                selected_portfolio_id = st.selectbox(
                    "Portfolio",
                    options=list(port_opts.keys()),
                    format_func=lambda x: port_opts[x],
                    key="bt_portfolio_id",
                )

        factor_opts = ["Composite", "Momentum", "Quality", "Growth", "Value", "Alpha Score"]
        primary_factor = st.selectbox(
            "Rank by", factor_opts, key="bt_factor"
        )
        sector_filter = st.text_input(
            "Sector filter (optional)", placeholder="e.g. Technology", key="bt_sector"
        )

        run_btn = st.button("▶ Run Factor Backtest", type="primary", key="bt_run_factor")

        if run_btn:
            with st.spinner("Loading data and running backtest…"):
                rank_df = _load_analytics_data(db, tenant_id)
                if rank_df.empty:
                    st.error("No analytics data found. Run Analytics first.")
                    return

                # Filter to portfolio holdings if selected
                if "💼 My Portfolio" in scope and selected_portfolio_id:
                    portfolio_syms = _get_portfolio_symbols(db, selected_portfolio_id)
                    if not portfolio_syms:
                        st.warning("No open positions found in this portfolio.")
                        return

                    port_syms_norm = [s.upper().strip() for s in portfolio_syms]

                    # Check how many portfolio symbols are in analytics
                    analytics_syms = set(rank_df["Symbol"].str.upper().str.strip())
                    have_analytics  = [s for s in port_syms_norm if s in analytics_syms]
                    need_computed   = [s for s in port_syms_norm if s not in analytics_syms]

                    if need_computed:
                        st.info(
                            f"{len(need_computed)} symbol(s) not in analytics — "
                            f"computing scores from price data: {', '.join(need_computed)}"
                        )
                        computed_rows = _compute_factor_scores_from_price(
                            db, need_computed
                        )
                        if not computed_rows.empty:
                            rank_df = pd.concat(
                                [rank_df, computed_rows], ignore_index=True
                            )

                    # Now filter to portfolio symbols
                    rank_df["_sym_upper"] = rank_df["Symbol"].str.upper().str.strip()
                    rank_df = rank_df[
                        rank_df["_sym_upper"].isin(set(port_syms_norm))
                    ].drop(columns=["_sym_upper"], errors="ignore")

                    if rank_df.empty:
                        st.error(
                            "Could not load price data for any portfolio symbols. "
                            f"Symbols: {port_syms_norm}"
                        )
                        return

                    st.success(
                        f"✅ Backtesting {len(rank_df)} portfolio holdings: "
                        f"{', '.join(rank_df['Symbol'].tolist())}"
                    )

                if sector_filter:
                    rank_df = rank_df[
                        rank_df["Sector"].str.contains(sector_filter, case=False, na=False)
                    ]

                if rank_df.empty:
                    st.warning("No symbols match the sector filter.")
                    return

                # Sort by chosen factor
                factor_col = primary_factor
                if factor_col not in rank_df.columns:
                    factor_col = "Composite"

                rank_df = rank_df.sort_values(factor_col, ascending=False)

                # Show factor scores so user can verify rankings
                show_cols = ["Symbol", "Composite", "Momentum", "Quality",
                             "Growth", "Value", "Alpha Score"]
                show_cols = [c for c in show_cols if c in rank_df.columns]
                with st.expander("📊 Factor scores used for ranking", expanded=False):
                    st.caption(f"Sorted by: {factor_col} (highest = selected first)")
                    st.dataframe(
                        rank_df[show_cols].reset_index(drop=True),
                        use_container_width=True,
                        hide_index=True,
                    )

                # Normalise symbol keys consistently FIRST
                def _norm(s):
                    return str(s).upper().replace(".US","").replace("-",".").strip()

                rank_df["_sym_norm"] = rank_df["Symbol"].apply(_norm)

                # Build factor_scores from ALL analytics symbols
                factor_scores = {
                    row["_sym_norm"]: {
                        "composite": float(row.get("Composite") or 0),
                        "momentum":  float(row.get("Momentum") or 0),
                        "quality":   float(row.get("Quality") or 0),
                    }
                    for _, row in rank_df.iterrows()
                }

                # Load price data for the SAME symbols that have factor scores
                # Use top candidates by composite score to keep it manageable
                top_symbols = rank_df["_sym_norm"].tolist()[:max_positions * 3]

                st.info(f"Loading price data for {len(top_symbols)} symbols…")
                price_cache_raw = _load_price_cache(db, top_symbols, period="2y")

                # Normalise price cache keys to match factor_scores keys
                price_cache = {_norm(k): v for k, v in price_cache_raw.items()}

                st.caption(
                    f"Price data loaded for {len(price_cache)} symbols. "
                    f"Factor scores for {len(factor_scores)} symbols. "
                    f"Overlap: {len(set(price_cache.keys()) & set(factor_scores.keys()))} symbols."
                )

                # Load benchmark
                bench_df = None
                try:
                    db.rollback()
                except Exception:
                    pass
                try:
                    from modules.market_data.service import get_price_history
                    bench_df = get_price_history(db, "SPY", period="2y", interval="1d")
                except Exception:
                    pass

                result = run_factor_backtest(
                    price_data=price_cache,
                    factor_scores=factor_scores,
                    config=config,
                    benchmark_data=bench_df,
                )
                st.session_state["bt_result"] = result

    # ── Indicator mode setup ──────────────────────────────────
    else:
        st.markdown("#### Indicator Condition")

        # Common preset conditions
        PRESET_CONDITIONS = {
            "— Select a preset or type your own —": "",
            "📈 RSI Oversold Recovery (RSI cross above 30, price above 200d MA)":
                "RSI crossed above 30 in the last 3 days while price is above the 200-day MA",
            "📉 RSI Overbought Reversal (RSI cross below 70)":
                "RSI crossed below 70 in the last 2 days",
            "⭐ Golden Cross (50d SMA crossed above 200d SMA)":
                "50-day SMA crossed above 200-day SMA in the past 5 days",
            "💀 Death Cross (50d SMA crossed below 200d SMA)":
                "50-day SMA crossed below 200-day SMA in the past 5 days",
            "🔥 MACD Bullish Crossover":
                "MACD crossed above signal line in the last 3 days",
            "❄️ MACD Bearish Crossover":
                "MACD crossed below signal line in the last 3 days",
            "🚀 52-Week High Breakout (with volume)":
                "52-week high breakout in the last 3 days on volume 1.5x average",
            "📊 Price Above 200-Day MA (trend filter)":
                "price is above the 200-day moving average",
            "🔔 Bollinger Band Squeeze":
                "Bollinger Band squeeze with price near the upper band",
            "💥 Volume Spike + Momentum":
                "volume 2x average with RSI above 50",
            "🎯 Oversold + Quality (RSI under 30, price above 50d MA)":
                "RSI below 30 and price is above the 50-day moving average",
        }

        preset_label = st.selectbox(
            "Common conditions",
            options=list(PRESET_CONDITIONS.keys()),
            key="bt_ind_preset",
        )
        preset_value = PRESET_CONDITIONS.get(preset_label, "")

        # Auto-fill text area when preset selected
        default_query = preset_value if preset_value else st.session_state.get("bt_ind_query", "")

        ind_query = st.text_area(
            "Custom condition (edit or type your own)",
            value=default_query,
            placeholder="e.g. RSI crossed above 30 in the last 3 days while price is above the 200-day MA",
            key="bt_ind_query",
            height=68,
            help="Select a preset above or write your own condition in plain English.",
        )

        # Scope for indicator backtest
        ind_scope = st.radio(
            "Test on",
            ["🌐 Full Universe", "💼 My Portfolio Holdings"],
            horizontal=True,
            key="bt_ind_scope",
        )

        ind_portfolio_id = None
        if "💼 My Portfolio" in ind_scope:
            portfolios = _load_portfolios(db, tenant_id)
            if portfolios:
                port_opts = {str(p[0]): p[1] for p in portfolios}
                ind_portfolio_id = st.selectbox(
                    "Portfolio",
                    options=list(port_opts.keys()),
                    format_func=lambda x: port_opts[x],
                    key="bt_ind_portfolio_id",
                )

        ind_run_btn = st.button(
            "▶ Run Indicator Backtest",
            type="primary",
            key="bt_run_ind",
            use_container_width=False,
        )

        # Store query in session state so it survives re-render
        if ind_query.strip():
            st.session_state["bt_ind_query_saved"] = ind_query.strip()

        if ind_run_btn:
            saved_query = st.session_state.get("bt_ind_query_saved", "").strip()
            if not saved_query:
                st.warning("Enter an indicator condition above before running.")
            else:
                with st.spinner(f"Parsing: '{saved_query[:60]}…'"):
                    try:
                        from modules.indicators.indicator_builder import translate_indicator
                        formula = translate_indicator(saved_query)
                    except Exception as e:
                        st.error(f"Indicator parsing failed: {e}")
                        formula = None

                if formula is not None:
                    if formula.warnings:
                        for w in formula.warnings:
                            st.warning(f"⚠️ {w}")

                    if not formula.has_conditions():
                        st.error("No conditions parsed. Try rephrasing your query.")
                    else:
                        st.info(f"✅ Parsed: {formula.plain_summary}")

                        # Get symbols to test
                        if "💼 My Portfolio" in ind_scope and ind_portfolio_id:
                            symbols = _get_portfolio_symbols(db, ind_portfolio_id)
                            if not symbols:
                                st.warning("No open positions in this portfolio.")
                                symbols = []
                        else:
                            rank_df_ind = _load_analytics_data(db, tenant_id)
                            symbols = rank_df_ind["Symbol"].tolist()[:50]                                 if not rank_df_ind.empty else []

                        if not symbols:
                            st.error("No symbols to test. Add positions or run Analytics first.")
                        else:
                            with st.spinner(
                                f"Loading price data for {len(symbols)} symbols…"
                            ):
                                price_cache = _load_price_cache(db, symbols, period="1y")

                            bench_df = None
                            try:
                                from modules.market_data.price_history_service import (
                                    load_price_history,
                                )
                                bench_df = load_price_history(db, "SPY")
                                if bench_df is not None and isinstance(
                                    bench_df.index, pd.DatetimeIndex
                                ):
                                    bench_df = bench_df.reset_index()
                            except Exception:
                                pass

                            with st.spinner("Running indicator backtest…"):
                                result = run_indicator_backtest(
                                    price_data=price_cache,
                                    formula=formula,
                                    config=config,
                                    benchmark_data=bench_df,
                                )
                            st.session_state["bt_result"] = result
                            st.rerun()

    # ── Render results ────────────────────────────────────────
    result: Optional[BacktestResult] = st.session_state.get("bt_result")
    if result:
        _render_backtest_results(result)


def _render_backtest_results(result: BacktestResult):
    if result.error:
        st.error(f"Backtest failed: {result.error}")
        return

    st.markdown("---")
    st.markdown(f"### Results: {result.strategy_name}")

    # ── Summary metrics ───────────────────────────────────────
    def _fmt(val, fmt="+.2f", suffix="%", fallback="N/A"):
        import math
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return fallback
        return f"{val:{fmt}}{suffix}"

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Return",   _fmt(result.total_return_pct),
              delta=f"vs SPY {_fmt(result.benchmark_return_pct)}",
              delta_color="normal" if (result.total_return_pct or 0) >= (result.benchmark_return_pct or 0) else "inverse")
    c2.metric("Annualised",     _fmt(result.annualised_return))
    c3.metric("Sharpe Ratio",   _fmt(result.sharpe_ratio, ".2f", ""),
              delta="Good" if (result.sharpe_ratio or 0) >= 1.0 else "Low",
              delta_color="normal" if (result.sharpe_ratio or 0) >= 1.0 else "inverse")
    c4.metric("Max Drawdown",   _fmt(result.max_drawdown_pct),
              delta_color="inverse")
    c5.metric("Win Rate",       _fmt(result.win_rate_pct, ".1f"))
    c6.metric("Total Trades",   result.total_trades)

    c7, c8, c9, c10 = st.columns(4)
    c7.metric("Alpha (ann.)",   _fmt(result.alpha_annualised))
    c8.metric("Sortino Ratio",  _fmt(result.sortino_ratio, ".2f", ""))
    c9.metric("Calmar Ratio",   _fmt(result.calmar_ratio, ".2f", ""))
    c10.metric("Avg Hold",      _fmt(result.avg_hold_days, ".0f", "d"))

    # ── Equity curve chart ────────────────────────────────────
    if not result.equity_curve.empty:
        st.markdown("#### Equity Curve")
        fig, ax = plt.subplots(figsize=(12, 4), facecolor="#0F1117")
        ax.set_facecolor("#161B22")
        ax.spines[:].set_color("#21262D")
        ax.tick_params(colors="#8B949E", labelsize=8)
        ax.grid(True, color="#21262D", linewidth=0.4, alpha=0.6)

        ax.plot(result.equity_curve.index, result.equity_curve,
                color="#1D9E75", linewidth=2, label=result.strategy_name)

        if not result.benchmark_curve.empty:
            bench_aligned = result.benchmark_curve.reindex(
                result.equity_curve.index, method="ffill"
            )
            ax.plot(bench_aligned.index, bench_aligned,
                    color="#8B949E", linewidth=1.5, linestyle="--",
                    label="SPY Benchmark", alpha=0.7)

        # Drawdown fill
        roll_max = result.equity_curve.cummax()
        ax.fill_between(
            result.equity_curve.index,
            result.equity_curve, roll_max,
            alpha=0.15, color="#E24B4A", label="Drawdown"
        )

        ax.legend(fontsize=9, facecolor="#161B22",
                  edgecolor="#21262D", labelcolor="#C9D1D9")
        ax.set_ylabel("Portfolio Value ($)", color="#8B949E", fontsize=9)
        ax.yaxis.tick_right()
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    # ── Trade log ─────────────────────────────────────────────
    if result.trades:
        st.markdown("#### Trade Log")
        trade_rows = [{
            "Symbol":      t.symbol,
            "Entry":       t.entry_date[:10],
            "Exit":        t.exit_date[:10],
            "Entry $":     f"${t.entry_price:,.2f}",
            "Exit $":      f"${t.exit_price:,.2f}",
            "P&L $":       f"${t.pnl:+,.2f}",
            "P&L %":       f"{t.pnl_pct:+.2f}%",
            "Exit Reason": t.exit_reason,
        } for t in result.trades[:100]]

        st.dataframe(
            pd.DataFrame(trade_rows),
            use_container_width=True,
            hide_index=True,
        )

        csv = pd.DataFrame(trade_rows).to_csv(index=False)
        st.download_button(
            "⬇️ Export Trade Log CSV",
            data=csv,
            file_name=f"backtest_{result.strategy_name}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key="bt_export",
        )


# ─────────────────────────────────────────────────────────────
# Tab 2 — Strategy Discovery (fixed)
# ─────────────────────────────────────────────────────────────

def _render_discovery_tab(db, user, tenant_id: str):
    st.subheader("Factor Strategy Discovery")
    st.caption(
        "Automatically tests all combinations of factor scores to find "
        "which combinations historically produced the best risk-adjusted returns."
    )

    # Load data independently — no session_state dependency
    rank_df = _load_analytics_data(db, tenant_id)

    if rank_df.empty:
        st.warning(
            "No analytics data found. "
            "Run **Analytics** first to generate factor scores."
        )
        return

    st.success(f"✅ {len(rank_df)} symbols loaded from analytics database.")

    # ── Universe controls ─────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    with c1:
        sym_limit = st.selectbox(
            "Universe size",
            options=[50, 100, 200, 500, 1000, 2000, 5000, 10000],
            index=2,
            format_func=lambda x: f"Top {x}",
            key="disc_sym_limit",
            help="Number of symbols to test. Larger = slower but more thorough."
        )
    with c2:
        sectors = ["All Sectors"] + sorted(
            rank_df["Sector"].dropna().unique().tolist()
        )
        sector_filter = st.selectbox(
            "Sector filter",
            options=sectors,
            key="disc_sector",
        )
    with c3:
        min_composite = st.slider(
            "Min Composite Score",
            0, 80, 0, step=10,
            key="disc_min_comp",
            help="Only include symbols above this composite score threshold."
        )

    # Reload with selected sym_limit if larger than current rank_df
    if sym_limit > len(rank_df):
        rank_df = _load_analytics_data(db, tenant_id, limit=sym_limit)
        if rank_df.empty:
            st.warning("No analytics data found.")
            return

    # Apply filters
    filtered_df = rank_df.copy()
    if sector_filter != "All Sectors":
        filtered_df = filtered_df[filtered_df["Sector"] == sector_filter]
    if min_composite > 0:
        filtered_df = filtered_df[filtered_df["Composite"] >= min_composite]

    filtered_df = filtered_df.head(sym_limit)
    st.caption(
        f"Testing on **{len(filtered_df)}** symbols"
        + (f" in **{sector_filter}**" if sector_filter != "All Sectors" else "")
        + (f" with composite ≥ {min_composite}" if min_composite > 0 else "")
    )
    rank_df = filtered_df

    n_available = len(filtered_df)
    max_holdings = max(4, min(n_available, 50))  # always at least 4 to avoid slider crash

    c4, c5 = st.columns(2)
    with c4:
        if n_available < 4:
            st.info(f"Only {n_available} symbols — holdings fixed at {n_available}.")
            top_n = n_available
        else:
            top_n = st.slider(
                "Top Holdings Per Strategy",
                min_value=3,
                max_value=max_holdings,
                value=min(10, max_holdings),
                key="disc_topn",
                help=f"How many top-ranked stocks to hold per strategy ({n_available} available)"
            )
    with c5:
        max_combo = st.slider("Max Factor Combo Size", 1, 4, 2, key="disc_combo")

    if st.button("🔬 Discover Strategies", type="primary", key="disc_run"):
        # Clear stale cache so we always use fresh DatetimeIndex DataFrames
        for k in ["price_cache", "ai_rank_df", "discovered_strategies",
                  "discovered_strategy_curves"]:
            st.session_state.pop(k, None)

        with st.spinner("Loading price data and testing factor combinations…"):
            symbols = rank_df["Symbol"].tolist()[:sym_limit]
            price_cache = _load_price_cache(db, symbols, period="1y")

            if not price_cache:
                st.error("No price data loaded. Check market data connection.")
                return

            # Ensure all DataFrames have DatetimeIndex (catches any edge cases)
            fixed = {}
            for sym, df in price_cache.items():
                try:
                    # Convert index to DatetimeIndex regardless of current type
                    df.index = pd.to_datetime(df.index)
                    if "Close" not in df.columns and "close" in df.columns:
                        df = df.rename(columns={"close": "Close"})
                    if isinstance(df.index, pd.DatetimeIndex) and "Close" in df.columns:
                        fixed[sym] = df
                except Exception as e:
                    print(f"[discovery] {sym} index fix failed: {e}")

            # Show data length distribution for debugging
            lengths = [len(df) for df in fixed.values() if "Close" in df.columns]
            if lengths:
                avg_len = sum(lengths) / len(lengths)
                min_len = min(lengths)
                st.caption(
                    f"✅ {len(fixed)} symbols with valid DatetimeIndex price data. "
                    f"Avg history: {avg_len:.0f} bars, Min: {min_len} bars "
                    f"(need ≥120 for strategy discovery)"
                )
                if min_len < 120:
                    n_short = sum(1 for l in lengths if l < 120)
                    st.warning(
                        f"⚠️ {n_short} symbols have fewer than 120 bars of history "
                        f"and will be excluded from discovery."
                    )
            else:
                st.caption(f"✅ {len(fixed)} symbols with valid DatetimeIndex price data.")

            if not fixed:
                st.error("No symbols had valid DatetimeIndex price data.")
                return

            # Load SPY benchmark — required by discover_strategies
            if "SPY" not in fixed:
                try:
                    from modules.market_data.price_history_service import load_price_history as _lph
                    spy_df = _lph(db, "SPY")
                    if spy_df is not None and not spy_df.empty:
                        spy_df.index = pd.to_datetime(spy_df.index)
                        fixed["SPY"] = spy_df
                        st.caption("✅ SPY benchmark loaded.")
                    else:
                        # Try fetching fresh
                        from modules.market_data.service import get_price_history_internal
                        spy_df = get_price_history_internal(
                            db, "SPY", period="1y", interval="1d", force_refresh=True
                        )
                        if spy_df is not None and not spy_df.empty:
                            if not isinstance(spy_df.index, pd.DatetimeIndex):
                                spy_df.index = pd.to_datetime(spy_df.index)
                            fixed["SPY"] = spy_df
                except Exception as e:
                    st.warning(f"SPY benchmark unavailable ({e}) — using first symbol as benchmark.")
                    # Patch discover_strategies to not require SPY by adding a dummy
                    first_sym = list(fixed.keys())[0]
                    fixed["SPY"] = fixed[first_sym].copy()

            st.session_state["price_cache"] = fixed
            st.session_state["ai_rank_df"]   = rank_df

            summary_df, curves = discover_strategies(rank_df, fixed, top_n, max_combo)

        if summary_df is None or summary_df.empty:
            st.warning("No valid strategies found. Try reducing the combo size or min data requirements.")
            return

        st.session_state["discovered_strategies"]       = summary_df
        st.session_state["discovered_strategy_curves"]  = curves

    summary_df = st.session_state.get("discovered_strategies")
    curves     = st.session_state.get("discovered_strategy_curves", {})

    if summary_df is None or summary_df.empty:
        return

    st.markdown("### Strategy Leaderboard")
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    if st.button("💾 Save to Strategy Library", key="disc_save"):
        inserted = save_discovered_strategies(db, tenant_id, summary_df)
        st.success(f"✅ {inserted} strategies saved.")

    # Chart
    names = summary_df["Strategy"].tolist()
    sel   = st.selectbox("Inspect strategy", names, key="disc_sel")
    if sel and sel in curves:
        df = curves[sel]
        row = summary_df[summary_df["Strategy"] == sel].iloc[0]

        fig, ax = plt.subplots(figsize=(10, 3.5), facecolor="#0F1117")
        ax.set_facecolor("#161B22")
        ax.plot(df.index, df["Strategy"], color="#1D9E75", label=sel)
        ax.plot(df.index, df["SPY"], color="#8B949E", linestyle="--", label="SPY")
        ax.legend(fontsize=8, facecolor="#161B22", edgecolor="#21262D", labelcolor="#C9D1D9")
        ax.spines[:].set_color("#21262D")
        ax.tick_params(colors="#8B949E", labelsize=8)
        ax.grid(True, color="#21262D", linewidth=0.3, alpha=0.5)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Return",      f"{row['Return'] * 100:.2f}%")
        c2.metric("Alpha",       f"{row['Alpha']:.4f}"       if pd.notna(row.get("Alpha")) else "N/A")
        c3.metric("Sharpe",      f"{row['Sharpe']:.2f}"      if pd.notna(row.get("Sharpe")) else "N/A")
        c4.metric("Max DD",      f"{row['Max Drawdown']*100:.2f}%" if pd.notna(row.get("Max Drawdown")) else "N/A")
        st.caption(f"Holdings: {row.get('Holdings', '—')}")


# ─────────────────────────────────────────────────────────────
# Tab 3 — Strategy Library
# ─────────────────────────────────────────────────────────────

def _render_library_tab(db, tenant_id: str):
    st.subheader("Strategy Library")
    st.caption("Strategies saved from discovery runs. Click any to load into the backtester.")

    rows = list_discovered_strategies(db, tenant_id)

    if not rows:
        st.info(
            "No saved strategies yet. "
            "Run **Strategy Discovery** and click Save to populate the library."
        )
        return

    df = pd.DataFrame([{
        "Name":         r.name,
        "Factors":      r.factors,
        "Return":       f"{r.return_pct * 100:.2f}%" if r.return_pct else "—",
        "Alpha":        f"{r.alpha:.4f}" if r.alpha else "—",
        "Sharpe":       f"{r.sharpe:.2f}" if r.sharpe else "—",
        "Max Drawdown": f"{r.max_drawdown * 100:.2f}%" if r.max_drawdown else "—",
        "Holdings":     (r.holdings or "")[:60] + "…" if r.holdings and len(r.holdings) > 60 else r.holdings,
        "Saved":        r.created_at.strftime("%b %d %Y") if r.created_at else "—",
    } for r in rows])

    st.dataframe(df, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False)
    st.download_button(
        "⬇️ Export Library CSV",
        data=csv,
        file_name="strategy_library.csv",
        mime="text/csv",
        key="lib_export",
    )