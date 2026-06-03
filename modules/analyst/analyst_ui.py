"""
modules/analyst/analyst_ui.py

Analyst Consensus Estimates & Revision Tracking — Streamlit UI.

Four sections:
  📈 Revision Score    — composite revision direction signal
  🎯 Price Targets     — consensus target, upside, individual analyst targets
  📊 Estimate Trend    — EPS estimate history with revision visualization
  📋 Ratings History   — buy/hold/sell trend + upgrade/downgrade log

Add to app.py:
    pages list: "Analyst Consensus"
    elif page == "Analyst Consensus":
        from modules.analyst.analyst_ui import render_analyst_page
        render_analyst_page(db, user)

Also embeds into Stock Dashboard — add:
    from modules.analyst.analyst_ui import render_analyst_card
    render_analyst_card(ticker)
"""

from __future__ import annotations

from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from modules.analyst.analyst_service import (
    get_eps_estimates,
    get_eps_surprise,
    get_price_targets,
    get_recommendation_trend,
    get_revision_score,
    get_upgrades_downgrades,
)


# ─────────────────────────────────────────────────────────────
# Main page
# ─────────────────────────────────────────────────────────────

def render_analyst_page(db, user: dict):
    st.header("📈 Analyst Consensus & Estimate Revisions")
    st.caption(
        "EPS estimate revision direction · Price target consensus · "
        "Upgrade/downgrade history · Buy/Hold/Sell trend · "
        "Powered by FMP + Finnhub"
    )

    col_sym, col_ref = st.columns([3, 1])
    with col_sym:
        ticker = st.text_input(
            "Symbol", value="NVDA", key="analyst_ticker",
            placeholder="AAPL, NVDA, MSFT…"
        ).upper().strip()
    with col_ref:
        st.write("")
        if st.button("↺ Refresh", key="analyst_refresh", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("analyst_cache_"):
                    del st.session_state[k]
            st.rerun()

    if not ticker:
        st.info("Enter a ticker to begin.")
        return

    _render_full_analyst_view(ticker)


def _render_full_analyst_view(ticker: str):
    """Full analyst view — loads all data and renders all sections."""

    # Load all data
    cache_key = f"analyst_cache_{ticker}"
    if cache_key not in st.session_state:
        with st.spinner(f"Loading analyst data for {ticker}…"):
            st.session_state[cache_key] = {
                "revision":  get_revision_score(ticker),
                "targets":   get_price_targets(ticker),
                "estimates": get_eps_estimates(ticker),
                "surprises": get_eps_surprise(ticker),
                "recos":     get_recommendation_trend(ticker),
                "upgrades":  get_upgrades_downgrades(ticker, days=90),
            }

    d         = st.session_state[cache_key]
    revision  = d["revision"]
    targets   = d["targets"]
    estimates = d["estimates"]
    surprises = d["surprises"]
    recos     = d["recos"]
    upgrades  = d["upgrades"]

    # ── Section 1: Revision Score ─────────────────────────────
    _render_revision_score(ticker, revision, targets)

    st.divider()

    # ── Section 2: Price Targets ──────────────────────────────
    _render_price_targets(ticker, targets)

    st.divider()

    # ── Section 3: EPS Estimates ──────────────────────────────
    _render_estimates(ticker, estimates, surprises)

    st.divider()

    # ── Section 4: Ratings & Upgrades ────────────────────────
    _render_ratings(ticker, recos, upgrades)


# ─────────────────────────────────────────────────────────────
# Section 1 — Revision Score
# ─────────────────────────────────────────────────────────────

def _render_revision_score(ticker: str, rev: dict, targets: dict):
    st.subheader(f"📈 Estimate Revision Signal — {ticker}")
    st.caption(
        "Rising EPS estimates → analysts expect stronger earnings → historically bullish. "
        "Falling estimates → downside risk. One of the most predictive quant factors."
    )

    label     = rev.get("composite_label", "Neutral")
    composite = rev.get("composite_revision", 0)
    color_map = {
        "Strong Positive": "#1D9E75",
        "Positive":        "#4CAF50",
        "Neutral":         "#BA7517",
        "Negative":        "#FF8C00",
        "Strong Negative": "#E24B4A",
    }
    color = color_map.get(label, "#8B949E")
    arrow = "↑" if composite > 10 else "↓" if composite < -10 else "→"

    # Score gauge
    st.markdown(
        f"<h3 style='margin:0'>"
        f"<span style='color:{color}'>{arrow} {label}</span>"
        f"<span style='font-size:16px;color:#8B949E;margin-left:12px'>"
        f"Score: {composite:+.0f}</span></h3>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("EPS Revision",    rev.get("revision_direction", "—"))
    c2.metric("Avg EPS Chg",     f"{rev.get('avg_eps_revision_pct', 0):+.1f}%")
    c3.metric("Rating Trend",    rev.get("rating_trend", "—"))
    c4.metric("Upgrades 90d",    rev.get("upgrades_90d", 0),
              delta_color="normal")
    c5.metric("Downgrades 90d",  rev.get("downgrades_90d", 0),
              delta_color="inverse")

    c6, c7, c8 = st.columns(3)
    c6.metric("Consensus",       rev.get("current_reco", "—"))
    c7.metric("Bull Analysts",   f"{rev.get('bull_pct', 0):.0f}%")
    c8.metric("Analysts",        rev.get("total_analysts", 0))

    # Upside from price target
    if targets.get("consensus_target") and targets.get("current_price"):
        tgt   = targets["consensus_target"]
        price = targets["current_price"]
        upside= round((tgt - price) / price * 100, 1)
        st.info(
            f"📌 Consensus price target: **${tgt:,.2f}** "
            f"({'↑' if upside > 0 else '↓'} {abs(upside):.1f}% from current) · "
            f"Range ${targets.get('low_target', 0):,.0f} – ${targets.get('high_target', 0):,.0f}"
        )


# ─────────────────────────────────────────────────────────────
# Section 2 — Price Targets
# ─────────────────────────────────────────────────────────────

def _render_price_targets(ticker: str, targets: dict):
    st.subheader("🎯 Price Target Consensus")

    cons = targets.get("consensus_target")
    high = targets.get("high_target")
    low  = targets.get("low_target")
    med  = targets.get("median_target")
    n    = targets.get("num_analysts", 0)

    if not cons and not high:
        st.info("No price target data available.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Consensus Target", f"${cons:,.2f}" if cons else "—")
    c2.metric("Median Target",    f"${med:,.2f}"  if med  else "—")
    c3.metric("High Target",      f"${high:,.2f}" if high else "—")
    c4.metric("Low Target",       f"${low:,.2f}"  if low  else "—")

    # Recent individual targets
    recent = targets.get("recent_targets", [])
    if recent:
        st.markdown("**Recent Analyst Price Targets**")
        rows = []
        for t in recent[:15]:
            prior  = t.get("prior")
            target = t.get("target")
            rows.append({
                "Date":     t["date"],
                "Firm":     t["firm"][:30] if t.get("firm") else "—",
                "Analyst":  t.get("analyst", "—")[:25],
                "Target":   f"${target:,.2f}" if target else "—",
                "Prior":    f"${prior:,.2f}"  if prior  else "—",
                "Change":   t.get("action", "—"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────
# Section 3 — EPS Estimates & Surprises
# ─────────────────────────────────────────────────────────────

def _render_estimates(ticker: str, estimates: list, surprises: list):
    st.subheader("📊 EPS Estimates & Surprise History")

    tab_est, tab_surp = st.tabs(["Forward Estimates", "Beat/Miss History"])

    with tab_est:
        if not estimates:
            st.info("No estimate data available.")
        else:
            rows = []
            for e in estimates[:8]:
                rows.append({
                    "Period":       e.get("period") or e.get("date", "")[:7],
                    "EPS (Avg)":    f"${e['eps_avg']:,.2f}" if e.get("eps_avg") is not None else "—",
                    "EPS High":     f"${e['eps_high']:,.2f}" if e.get("eps_high") is not None else "—",
                    "EPS Low":      f"${e['eps_low']:,.2f}"  if e.get("eps_low")  is not None else "—",
                    "Rev (Avg)":    f"${e['revenue_avg']/1e9:.2f}B" if e.get("revenue_avg") else "—",
                    "# Analysts":   e.get("num_analysts_eps", "—"),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            _render_eps_trend_chart(estimates, ticker)

    with tab_surp:
        if not surprises:
            st.info("No earnings surprise history available.")
        else:
            rows = []
            beats = [s for s in surprises if s.get("beat") is True]
            misses= [s for s in surprises if s.get("beat") is False]

            st.metric("Beat Rate",
                      f"{len(beats)/len(surprises)*100:.0f}%",
                      delta=f"{len(beats)} beats / {len(misses)} misses",
                      delta_color="normal" if len(beats) >= len(misses) else "inverse")

            for s in surprises[:8]:
                beat    = s.get("beat")
                icon    = "✅" if beat else "❌" if beat is False else "—"
                surp_pct= s.get("surprise_pct")
                rows.append({
                    "Date":      s["date"],
                    "Actual":    f"${s['actual']:,.2f}" if s.get("actual") is not None else "—",
                    "Estimate":  f"${s['estimate']:,.2f}" if s.get("estimate") is not None else "—",
                    "Surprise":  f"{surp_pct:+.1f}%" if surp_pct is not None else "—",
                    "Beat":      icon,
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            _render_surprise_chart(surprises, ticker)


def _render_eps_trend_chart(estimates: list, ticker: str):
    valid = [e for e in estimates if e.get("eps_avg") is not None]
    if len(valid) < 2:
        return

    periods = [e.get("period") or e.get("date", "")[:7] for e in reversed(valid[:8])]
    avgs    = [e["eps_avg"] for e in reversed(valid[:8])]
    highs   = [e.get("eps_high") or e["eps_avg"] for e in reversed(valid[:8])]
    lows    = [e.get("eps_low")  or e["eps_avg"] for e in reversed(valid[:8])]

    fig, ax = plt.subplots(figsize=(10, 3.5), facecolor="#0F1117")
    ax.set_facecolor("#161B22")
    x = range(len(periods))

    ax.fill_between(x, lows, highs, alpha=0.2, color="#378ADD", label="High–Low range")
    ax.plot(x, avgs, color="#378ADD", linewidth=2, marker="o", markersize=5, label="Consensus EPS")
    ax.axhline(0, color="#30363D", linewidth=0.8)

    ax.set_xticks(list(x))
    ax.set_xticklabels(periods, rotation=45, ha="right", fontsize=8, color="#8B949E")
    ax.set_ylabel("EPS ($)", color="#8B949E", fontsize=8)
    ax.set_title(f"{ticker} Forward EPS Estimates", color="#C9D1D9", fontsize=10)
    ax.tick_params(colors="#8B949E")
    ax.spines[:].set_color("#21262D")
    ax.grid(True, color="#21262D", linewidth=0.3, alpha=0.6)
    ax.legend(fontsize=8, facecolor="#0F1117", labelcolor="#8B949E", framealpha=0.3)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def _render_surprise_chart(surprises: list, ticker: str):
    valid = [s for s in surprises if s.get("surprise_pct") is not None]
    if len(valid) < 2:
        return

    valid = list(reversed(valid[:8]))
    dates = [s["date"][:7] for s in valid]
    pcts  = [s["surprise_pct"] for s in valid]
    colors= ["#1D9E75" if p > 0 else "#E24B4A" for p in pcts]

    fig, ax = plt.subplots(figsize=(10, 2.5), facecolor="#0F1117")
    ax.set_facecolor("#161B22")
    ax.bar(range(len(dates)), pcts, color=colors, alpha=0.85)
    ax.axhline(0, color="#30363D", linewidth=0.8)
    ax.set_xticks(range(len(dates)))
    ax.set_xticklabels(dates, rotation=45, ha="right", fontsize=8, color="#8B949E")
    ax.set_ylabel("Surprise %", color="#8B949E", fontsize=8)
    ax.set_title(f"{ticker} EPS Beat/Miss History", color="#C9D1D9", fontsize=10)
    ax.tick_params(colors="#8B949E")
    ax.spines[:].set_color("#21262D")
    ax.grid(axis="y", color="#21262D", linewidth=0.3, alpha=0.4)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


# ─────────────────────────────────────────────────────────────
# Section 4 — Ratings Trend & Upgrades
# ─────────────────────────────────────────────────────────────

def _render_ratings(ticker: str, recos: list, upgrades: list):
    st.subheader("📋 Analyst Ratings & Rating Changes")

    tab_trend, tab_changes = st.tabs(["Rating Trend", "Upgrades & Downgrades"])

    with tab_trend:
        if not recos:
            st.info("No recommendation data available.")
        else:
            _render_reco_chart(recos, ticker)

            rows = []
            for r in recos[:6]:
                rows.append({
                    "Period":      r["period"],
                    "Strong Buy":  r["strong_buy"],
                    "Buy":         r["buy"],
                    "Hold":        r["hold"],
                    "Sell":        r["sell"],
                    "Strong Sell": r["strong_sell"],
                    "Total":       r["total"],
                    "Bull %":      f"{r['bull_pct']:.0f}%",
                    "Consensus":   r["sentiment"],
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab_changes:
        if not upgrades:
            st.info("No upgrade/downgrade data in the last 90 days.")
        else:
            ups   = [u for u in upgrades if u.get("is_upgrade")]
            downs = [u for u in upgrades if u.get("is_downgrade")]

            col1, col2 = st.columns(2)
            col1.metric("Upgrades (90d)",   len(ups),
                        delta="Bullish signal" if ups else None,
                        delta_color="normal")
            col2.metric("Downgrades (90d)", len(downs),
                        delta="Bearish signal" if downs else None,
                        delta_color="inverse")

            rows = []
            for u in upgrades[:20]:
                if u.get("source") == "finnhub":
                    continue
                icon = "↑" if u.get("is_upgrade") else "↓" if u.get("is_downgrade") else "→"
                rows.append({
                    "Date":    u["date"],
                    "Firm":    u.get("firm", "—")[:30],
                    "Action":  f"{icon} {u.get('action', '').title()[:30]}",
                    "From":    u.get("from_grade", "—"),
                    "To":      u.get("to_grade", "—"),
                })

            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_reco_chart(recos: list, ticker: str):
    if not recos:
        return

    valid = recos[:8]
    periods = [r["period"] for r in reversed(valid)]
    sbuy  = [r["strong_buy"]  for r in reversed(valid)]
    buy   = [r["buy"]         for r in reversed(valid)]
    hold  = [r["hold"]        for r in reversed(valid)]
    sell  = [r["sell"]        for r in reversed(valid)]
    ssell = [r["strong_sell"] for r in reversed(valid)]
    x     = range(len(periods))

    fig, ax = plt.subplots(figsize=(10, 3.5), facecolor="#0F1117")
    ax.set_facecolor("#161B22")
    width = 0.6

    ax.bar(x, sbuy,  width, label="Strong Buy",  color="#1D9E75")
    ax.bar(x, buy,   width, bottom=sbuy,
           label="Buy",         color="#4CAF50")
    ax.bar(x, hold,  width,
           bottom=[a+b for a,b in zip(sbuy, buy)],
           label="Hold",        color="#BA7517")
    ax.bar(x, sell,  width,
           bottom=[a+b+c for a,b,c in zip(sbuy, buy, hold)],
           label="Sell",        color="#FF8C00")
    ax.bar(x, ssell, width,
           bottom=[a+b+c+d for a,b,c,d in zip(sbuy, buy, hold, sell)],
           label="Strong Sell", color="#E24B4A")

    ax.set_xticks(list(x))
    ax.set_xticklabels(periods, rotation=45, ha="right", fontsize=8, color="#8B949E")
    ax.set_ylabel("# Analysts", color="#8B949E", fontsize=8)
    ax.set_title(f"{ticker} Analyst Rating Distribution", color="#C9D1D9", fontsize=10)
    ax.tick_params(colors="#8B949E")
    ax.spines[:].set_color("#21262D")
    ax.grid(axis="y", color="#21262D", linewidth=0.3, alpha=0.4)
    ax.legend(fontsize=7, facecolor="#0F1117", labelcolor="#8B949E",
              framealpha=0.3, loc="upper left", ncol=5)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


# ─────────────────────────────────────────────────────────────
# Embeddable card for Stock Dashboard
# ─────────────────────────────────────────────────────────────

def render_analyst_card(ticker: str):
    """
    Compact analyst card for embedding in Stock Dashboard.
    Shows revision score, consensus target, and bull/bear split.
    """
    try:
        rev     = get_revision_score(ticker)
        targets = get_price_targets(ticker)
    except Exception:
        st.caption("Analyst data unavailable.")
        return

    label    = rev.get("composite_label", "Neutral")
    color_map= {
        "Strong Positive": "#1D9E75", "Positive": "#4CAF50",
        "Neutral": "#BA7517", "Negative": "#FF8C00", "Strong Negative": "#E24B4A",
    }
    color = color_map.get(label, "#8B949E")

    st.markdown(
        f"**Revision Signal:** <span style='color:{color}'>{label}</span> "
        f"(score {rev.get('composite_revision', 0):+.0f})",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Consensus",   rev.get("current_reco", "—"))
    c2.metric("Bull %",      f"{rev.get('bull_pct', 0):.0f}%")
    if targets.get("consensus_target"):
        c3.metric("Target",  f"${targets['consensus_target']:,.2f}")
    else:
        c3.metric("Target",  "—")