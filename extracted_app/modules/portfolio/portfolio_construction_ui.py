"""
modules/portfolio/portfolio_construction_ui.py

AI Portfolio Construction Panel.

Renders the full portfolio output:
  - Portfolio summary metrics
  - Position table with weights, signals, conviction, rationale
  - Sector allocation breakdown chart
  - Risk/return scatter
  - Individual stock rationale expanders

Call from ai_portfolio_ui.py:
    from modules.portfolio.portfolio_construction_ui import render_portfolio_construction_panel
    render_portfolio_construction_panel(candidates, mission_decision, regime_state)
"""

from __future__ import annotations

import math
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import streamlit as st


# ─────────────────────────────────────────────────────────────
# Colour config
# ─────────────────────────────────────────────────────────────
GREEN  = "#1D9E75"
RED    = "#E24B4A"
BLUE   = "#378ADD"
AMBER  = "#BA7517"
PURPLE = "#7F77DD"

CONVICTION_COLORS = {
    "Ultra High": GREEN,
    "High":       "#4CAF50",
    "Moderate":   AMBER,
    "Low":        RED,
    "Neutral":    "#8B949E",
}

ACTION_COLORS = {
    "Strong Buy":  GREEN,
    "Buy":         "#4CAF50",
    "Hold":        AMBER,
    "Reduce":      "#FF8C00",
    "Sell":        RED,
    "Avoid":       "#6B0000",
}

SECTOR_PALETTE = [
    "#378ADD", "#1D9E75", "#BA7517", "#7F77DD",
    "#E24B4A", "#4CAF50", "#FF8C00", "#00BCD4",
    "#9C27B0", "#F06292", "#795548", "#607D8B",
]


# ═══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def render_portfolio_construction_panel(
    candidates: list,
    mission_decision=None,
    regime_state=None,
    opportunities: Optional[list] = None,
):
    """
    Full portfolio construction panel.
    `candidates` = list of AIPortfolioCandidate objects with target_weight set.
    """
    if not candidates:
        st.warning(
            "No portfolio candidates available. "
            "Run the AI ranking engine first or check that your universe has symbols."
        )
        return

    # Sort by target_weight descending
    portfolio = sorted(candidates, key=lambda c: getattr(c, "target_weight", 0), reverse=True)
    portfolio = [c for c in portfolio if getattr(c, "target_weight", 0) > 0]

    if not portfolio:
        st.warning("Candidates found but none have been assigned a target weight yet.")
        return

    st.markdown("---")
    st.markdown("## 🏗️ AI Portfolio Construction")

    # ── Summary metrics ───────────────────────────────────────
    _render_summary(portfolio, mission_decision, regime_state)

    st.markdown("---")

    # ── Main tabs ─────────────────────────────────────────────
    tab_positions, tab_sectors, tab_risk, tab_rationale = st.tabs([
        "📋 Positions",
        "🥧 Sector Allocation",
        "⚡ Risk & Return",
        "🧠 AI Rationale",
    ])

    with tab_positions:
        _render_positions_table(portfolio, opportunities)

    with tab_sectors:
        _render_sector_breakdown(portfolio)

    with tab_risk:
        _render_risk_return(portfolio)

    with tab_rationale:
        _render_rationale_panel(portfolio)


# ═══════════════════════════════════════════════════════════════
# SUMMARY METRICS
# ═══════════════════════════════════════════════════════════════

def _render_summary(portfolio, mission_decision, regime_state):
    total_weight    = sum(getattr(c, "target_weight", 0) for c in portfolio)
    cash_pct        = max(0, 100 - total_weight)
    n_positions     = len(portfolio)
    avg_conviction  = np.mean([getattr(c, "composite_conviction", 50) for c in portfolio])
    avg_risk        = np.mean([getattr(c, "risk_score", 50) for c in portfolio])
    exp_return      = np.mean([getattr(c, "expected_return", 0) for c in portfolio]) * 100
    exp_alpha       = np.mean([getattr(c, "expected_alpha", 0) for c in portfolio]) * 100

    mission_name = "—"
    if mission_decision:
        mission_name = getattr(mission_decision, "selected_mission", "—") or \
                       (mission_decision.get("selected_mission") if isinstance(mission_decision, dict) else "—")

    regime_name = "—"
    if regime_state:
        regime_name = getattr(regime_state, "regime", "—") or \
                      (regime_state.get("regime") if isinstance(regime_state, dict) else "—")

    # Row 1 — portfolio overview
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Positions",        n_positions)
    c2.metric("Invested",         f"{total_weight:.1f}%")
    c3.metric("Cash Reserve",     f"{cash_pct:.1f}%")
    c4.metric("Avg Conviction",   f"{avg_conviction:.0f}/100")
    c5.metric("Avg Risk Score",   f"{avg_risk:.0f}/100")
    c6.metric("Exp. Alpha",       f"{exp_alpha:+.1f}%")

    # Row 2 — context
    c7, c8, c9, _ = st.columns([1, 1, 1, 3])
    c7.metric("Mission",          mission_name)
    c8.metric("Regime",           regime_name.title())
    c9.metric("Exp. Return",      f"{exp_return:+.1f}%")

    # Conviction bar
    high_conv = len([c for c in portfolio if getattr(c, "composite_conviction", 0) >= 70])
    med_conv  = len([c for c in portfolio if 50 <= getattr(c, "composite_conviction", 0) < 70])
    low_conv  = len([c for c in portfolio if getattr(c, "composite_conviction", 0) < 50])

    st.markdown(
        f"**Conviction mix:** "
        f"🟢 High ({high_conv}) · "
        f"🟡 Moderate ({med_conv}) · "
        f"🔴 Low ({low_conv})"
    )


# ═══════════════════════════════════════════════════════════════
# POSITIONS TABLE
# ═══════════════════════════════════════════════════════════════

def _render_positions_table(portfolio, opportunities=None):
    st.subheader("Portfolio Positions")

    # Build opportunity map for quick lookup
    opp_map = {}
    if opportunities:
        for o in opportunities:
            sym = getattr(o, "symbol", None)
            if sym:
                opp_map[sym] = o

    # Filters
    col_filter, col_sort, _ = st.columns([1, 1, 4])
    with col_filter:
        action_filter = st.selectbox(
            "Filter by action",
            ["All", "Strong Buy", "Buy", "Hold", "Reduce", "Sell"],
            key="pc_action_filter"
        )
    with col_sort:
        sort_by = st.selectbox(
            "Sort by",
            ["Weight", "AI Score", "Conviction", "Expected Return", "Risk Score"],
            key="pc_sort_by"
        )

    sort_map = {
        "Weight":          lambda c: getattr(c, "target_weight", 0),
        "AI Score":        lambda c: getattr(c, "ai_score", 0),
        "Conviction":      lambda c: getattr(c, "composite_conviction", 0),
        "Expected Return": lambda c: getattr(c, "expected_return", 0),
        "Risk Score":      lambda c: -getattr(c, "risk_score", 0),  # lower is better
    }
    sorted_portfolio = sorted(portfolio, key=sort_map[sort_by], reverse=True)

    rows = []
    for c in sorted_portfolio:
        action = getattr(c, "recommended_action", "Hold") or "Hold"
        if action_filter != "All" and action != action_filter:
            continue

        conviction = getattr(c, "conviction_label", "Neutral") or "Neutral"
        comp_conv  = getattr(c, "composite_conviction", 50)
        ai_score   = getattr(c, "ai_score", 50)
        risk_score = getattr(c, "risk_score", 50)
        exp_ret    = getattr(c, "expected_return", 0) * 100
        exp_alpha  = getattr(c, "expected_alpha", 0) * 100
        weight     = getattr(c, "target_weight", 0)
        sector     = getattr(c, "sector", "Unknown") or "Unknown"
        volatility = getattr(c, "volatility", 25)

        # Action emoji
        action_emoji = {
            "Strong Buy": "🟢 Strong Buy",
            "Buy":        "🟩 Buy",
            "Hold":       "🟡 Hold",
            "Reduce":     "🟠 Reduce",
            "Sell":       "🔴 Sell",
            "Avoid":      "⛔ Avoid",
        }.get(action, action)

        # Conviction emoji
        conv_emoji = {
            "Ultra High": "⭐⭐⭐",
            "High":       "⭐⭐",
            "Moderate":   "⭐",
            "Low":        "·",
            "Neutral":    "·",
        }.get(conviction, "·")

        # Opportunity tag
        opp_tag = ""
        if c.symbol in opp_map:
            opp_tag = "🔥"

        rows.append({
            "":             opp_tag,
            "Symbol":       c.symbol,
            "Sector":       sector[:18],
            "Weight":       f"{weight:.1f}%",
            "Action":       action_emoji,
            "Conviction":   f"{conv_emoji} {conviction}",
            "AI Score":     f"{ai_score:.0f}",
            "Comp. Conv.":  f"{comp_conv:.0f}",
            "Risk":         f"{risk_score:.0f}",
            "Volatility":   f"{volatility:.1f}%",
            "Exp. Return":  f"{exp_ret:+.1f}%",
            "Exp. Alpha":   f"{exp_alpha:+.1f}%",
        })

    if not rows:
        st.info("No positions match the current filter.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"🔥 = Active opportunity signal  ·  {len(rows)} positions shown")

    # Export button
    csv = pd.DataFrame(rows).to_csv(index=False)
    st.download_button(
        "⬇️ Export positions CSV",
        data=csv,
        file_name="ai_portfolio_positions.csv",
        mime="text/csv",
        key="pc_export_csv"
    )


# ═══════════════════════════════════════════════════════════════
# SECTOR BREAKDOWN
# ═══════════════════════════════════════════════════════════════

def _render_sector_breakdown(portfolio):
    st.subheader("Sector Allocation")

    # Aggregate by sector
    sector_weights: dict = {}
    sector_counts:  dict = {}
    for c in portfolio:
        sector = getattr(c, "sector", "Unknown") or "Unknown"
        w = getattr(c, "target_weight", 0)
        sector_weights[sector] = sector_weights.get(sector, 0) + w
        sector_counts[sector]  = sector_counts.get(sector, 0) + 1

    total_invested = sum(sector_weights.values())
    cash_pct = max(0, 100 - total_invested)

    if cash_pct > 0:
        sector_weights["Cash"] = cash_pct
        sector_counts["Cash"]  = 0

    sectors = list(sector_weights.keys())
    weights = list(sector_weights.values())
    colors  = SECTOR_PALETTE[:len(sectors)]

    col_chart, col_table = st.columns([1, 1])

    with col_chart:
        fig, ax = plt.subplots(figsize=(5, 5), facecolor="#0F1117")
        ax.set_facecolor("#0F1117")

        wedges, texts, autotexts = ax.pie(
            weights,
            labels=None,
            autopct=lambda p: f"{p:.1f}%" if p >= 3 else "",
            colors=colors,
            startangle=90,
            wedgeprops={"linewidth": 1.5, "edgecolor": "#0F1117"},
            pctdistance=0.75,
        )
        for t in autotexts:
            t.set_color("white")
            t.set_fontsize(8)

        # Donut hole
        centre = plt.Circle((0, 0), 0.50, fc="#0F1117")
        ax.add_artist(centre)
        ax.text(0, 0, f"{total_invested:.0f}%\nInvested",
                ha="center", va="center", fontsize=10,
                color="white", fontweight="bold")

        ax.set_title("Sector Weights", color="white", fontsize=11, pad=12)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    with col_table:
        table_rows = []
        for sector, weight in sorted(sector_weights.items(), key=lambda x: x[1], reverse=True):
            count = sector_counts.get(sector, 0)
            table_rows.append({
                "Sector":    sector,
                "Weight":    f"{weight:.1f}%",
                "Positions": count if sector != "Cash" else "—",
                "Avg/Pos":   f"{weight/count:.1f}%" if count > 0 else "—",
            })

        st.dataframe(
            pd.DataFrame(table_rows),
            use_container_width=True,
            hide_index=True
        )

        # Concentration warning
        max_sector = max(sector_weights.items(), key=lambda x: x[1])
        if max_sector[1] > 30:
            st.warning(
                f"⚠️ **{max_sector[0]}** represents {max_sector[1]:.1f}% of portfolio — "
                "consider reducing concentration."
            )


# ═══════════════════════════════════════════════════════════════
# RISK / RETURN SCATTER
# ═══════════════════════════════════════════════════════════════

def _render_risk_return(portfolio):
    st.subheader("Risk vs. Expected Return")

    if len(portfolio) < 2:
        st.info("Need at least 2 positions to render the scatter.")
        return

    symbols   = [c.symbol for c in portfolio]
    exp_ret   = [getattr(c, "expected_return", 0) * 100 for c in portfolio]
    risk      = [getattr(c, "risk_score", 50) for c in portfolio]
    weights   = [getattr(c, "target_weight", 1) for c in portfolio]
    conv      = [getattr(c, "composite_conviction", 50) for c in portfolio]
    actions   = [getattr(c, "recommended_action", "Hold") or "Hold" for c in portfolio]

    action_color_map = {
        "Strong Buy": GREEN,
        "Buy":        "#4CAF50",
        "Hold":       AMBER,
        "Reduce":     "#FF8C00",
        "Sell":       RED,
        "Avoid":      "#6B0000",
    }
    dot_colors = [action_color_map.get(a, BLUE) for a in actions]
    dot_sizes  = [max(30, w * 25) for w in weights]

    fig, ax = plt.subplots(figsize=(10, 5), facecolor="#0F1117")
    ax.set_facecolor("#161B22")
    ax.spines[:].set_color("#21262D")
    ax.tick_params(colors="#8B949E", labelsize=8)
    ax.grid(True, color="#21262D", linewidth=0.4, alpha=0.7)

    scatter = ax.scatter(
        risk, exp_ret,
        s=dot_sizes, c=dot_colors, alpha=0.85,
        edgecolors="#0F1117", linewidths=0.8, zorder=5
    )

    # Label each dot
    for i, sym in enumerate(symbols):
        ax.annotate(
            sym,
            (risk[i], exp_ret[i]),
            fontsize=7, color="#C9D1D9",
            xytext=(4, 4), textcoords="offset points"
        )

    # Reference lines
    ax.axhline(0, color="#30363D", linewidth=0.8, linestyle="--")
    ax.axvline(50, color="#30363D", linewidth=0.8, linestyle="--", alpha=0.5)

    ax.set_xlabel("Risk Score (lower = safer)", color="#8B949E", fontsize=9)
    ax.set_ylabel("Expected Return (%)", color="#8B949E", fontsize=9)
    ax.set_title(
        "Risk vs. Return — bubble size = portfolio weight",
        color="#C9D1D9", fontsize=11
    )

    # Legend
    legend_elements = [
        mpatches.Patch(color=GREEN,     label="Strong Buy"),
        mpatches.Patch(color="#4CAF50", label="Buy"),
        mpatches.Patch(color=AMBER,     label="Hold"),
        mpatches.Patch(color=RED,       label="Sell/Reduce"),
    ]
    ax.legend(
        handles=legend_elements,
        fontsize=8, loc="upper right",
        facecolor="#161B22", edgecolor="#30363D",
        labelcolor="#C9D1D9", framealpha=0.8
    )

    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    # Quadrant summary
    q1 = sum(1 for i in range(len(portfolio)) if risk[i] < 50 and exp_ret[i] > 0)
    q2 = sum(1 for i in range(len(portfolio)) if risk[i] >= 50 and exp_ret[i] > 0)
    q3 = sum(1 for i in range(len(portfolio)) if risk[i] < 50 and exp_ret[i] <= 0)
    q4 = sum(1 for i in range(len(portfolio)) if risk[i] >= 50 and exp_ret[i] <= 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🟢 Low Risk / Positive Return", q1, help="Ideal quadrant")
    c2.metric("🟡 High Risk / Positive Return", q2, help="Speculative")
    c3.metric("🟠 Low Risk / Flat Return", q3, help="Defensive")
    c4.metric("🔴 High Risk / Negative Return", q4, help="Review these positions")


# ═══════════════════════════════════════════════════════════════
# AI RATIONALE PANEL
# ═══════════════════════════════════════════════════════════════

def _render_rationale_panel(portfolio):
    st.subheader("AI Investment Rationale")
    st.caption("Click any position to expand the AI thesis, bullish/bearish factors, and risk flags.")

    # Sort options
    sort_opt = st.radio(
        "Show",
        ["All positions", "Strong Buy / Buy only", "High conviction only"],
        horizontal=True,
        key="pc_rationale_sort"
    )

    filtered = portfolio
    if sort_opt == "Strong Buy / Buy only":
        filtered = [c for c in portfolio
                    if getattr(c, "recommended_action", "") in ("Strong Buy", "Buy")]
    elif sort_opt == "High conviction only":
        filtered = [c for c in portfolio
                    if getattr(c, "composite_conviction", 0) >= 70]

    if not filtered:
        st.info("No positions match this filter.")
        return

    for c in filtered:
        symbol     = c.symbol
        action     = getattr(c, "recommended_action", "Hold") or "Hold"
        conviction = getattr(c, "conviction_label", "Neutral") or "Neutral"
        comp_conv  = getattr(c, "composite_conviction", 50)
        ai_score   = getattr(c, "ai_score", 50)
        weight     = getattr(c, "target_weight", 0)
        sector     = getattr(c, "sector", "Unknown") or "Unknown"
        thesis     = getattr(c, "thesis", "") or ""
        bull_factors = getattr(c, "bullish_factors", []) or []
        bear_factors = getattr(c, "bearish_factors", []) or []
        risk_flags   = getattr(c, "risk_flags", []) or []
        exp_ret    = getattr(c, "expected_return", 0) * 100
        exp_alpha  = getattr(c, "expected_alpha", 0) * 100
        risk_score = getattr(c, "risk_score", 50)
        downside   = getattr(c, "downside_risk", 0)

        action_color = ACTION_COLORS.get(action, AMBER)
        conv_color   = CONVICTION_COLORS.get(conviction, "#8B949E")

        header = (
            f"**{symbol}** · {sector} · "
            f"Weight: {weight:.1f}% · "
            f"Action: {action} · "
            f"Conviction: {conviction} ({comp_conv:.0f}/100)"
        )

        with st.expander(header, expanded=(action == "Strong Buy")):
            # Mini metrics row
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("AI Score",      f"{ai_score:.0f}/100")
            m2.metric("Conviction",    f"{comp_conv:.0f}/100")
            m3.metric("Risk Score",    f"{risk_score:.0f}/100")
            m4.metric("Exp. Return",   f"{exp_ret:+.1f}%")
            m5.metric("Exp. Alpha",    f"{exp_alpha:+.1f}%")

            # Conviction bar
            bar_pct = int(comp_conv)
            bar_color = GREEN if comp_conv >= 70 else AMBER if comp_conv >= 50 else RED
            st.markdown(
                f"**Conviction:** "
                f"<div style='background:#21262D;border-radius:4px;height:8px;width:100%'>"
                f"<div style='background:{bar_color};height:8px;border-radius:4px;"
                f"width:{bar_pct}%'></div></div>",
                unsafe_allow_html=True
            )
            st.markdown("")

            # Thesis
            if thesis:
                st.markdown(f"**🧠 AI Thesis**")
                st.info(thesis)
            else:
                st.caption("No AI thesis generated for this position.")

            # Factors
            col_bull, col_bear = st.columns(2)
            with col_bull:
                st.markdown("**✅ Bullish Factors**")
                if bull_factors:
                    for f in bull_factors:
                        st.markdown(f"- {f}")
                else:
                    st.caption("None recorded")

            with col_bear:
                st.markdown("**⚠️ Bearish Factors**")
                if bear_factors:
                    for f in bear_factors:
                        st.markdown(f"- {f}")
                else:
                    st.caption("None recorded")

            # Risk flags
            if risk_flags:
                st.markdown("**🚩 Risk Flags**")
                for flag in risk_flags:
                    st.warning(f"⚠️ {flag}")

            # Downside risk
            if downside > 0:
                st.caption(f"**Downside risk estimate:** {downside * 100:.1f}%")
