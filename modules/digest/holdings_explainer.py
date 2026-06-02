"""
modules/digest/holdings_explainer.py

Personalized Holdings Explainer.

Every time a user opens their portfolio, Claude scans their specific
holdings against today's news and market moves and explains:
  - Which positions are being affected by news RIGHT NOW
  - Whether each affected position is being helped or hurt
  - The specific reason tied to their actual holdings
  - What to watch for each position

This is fundamentally different from generic market news —
every insight is tied to a specific position in the user's portfolio
with their actual cost basis, P&L, and weight.

Integration — add to portfolio_ui.py overview tab:
    from modules.digest.holdings_explainer import render_holdings_explainer
    render_holdings_explainer(db=db_session, portfolio_id=portfolio_id)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st


# ─────────────────────────────────────────────────────────────
# Claude client
# ─────────────────────────────────────────────────────────────

def _get_client():
    import anthropic
    key = (
        os.getenv("ANTHROPIC_API_KEY")
        or st.secrets.get("ANTHROPIC_API_KEY", "")
    )
    if not key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set.")
    return anthropic.Anthropic(api_key=key)


def _anthropic_available() -> bool:
    try:
        return bool(
            os.getenv("ANTHROPIC_API_KEY")
            or st.secrets.get("ANTHROPIC_API_KEY", "")
        )
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# Tool schema — structured per-position impact analysis
# ─────────────────────────────────────────────────────────────

EXPLAINER_TOOL = {
    "name": "submit_holdings_explanation",
    "description": (
        "Submit a personalized explanation of how today's news and market "
        "moves are affecting each portfolio holding."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "portfolio_headline": {
                "type": "string",
                "description": (
                    "One sentence summarising the most important thing "
                    "happening in this specific portfolio today. "
                    "e.g. 'Your NVDA position is up 4.2% on strong AI demand data, "
                    "offsetting weakness in your AAPL holding.' Max 150 chars."
                ),
            },
            "affected_positions": {
                "type": "array",
                "description": (
                    "List of positions being meaningfully affected by news or "
                    "price action today. Only include positions where something "
                    "specific and notable is happening."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "impact": {
                            "type": "string",
                            "enum": ["positive", "negative", "mixed", "neutral"],
                        },
                        "impact_magnitude": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "headline_driver": {
                            "type": "string",
                            "description": (
                                "The specific news headline or market event "
                                "driving this position today. 1 sentence, "
                                "cite the actual headline if available."
                            ),
                        },
                        "position_context": {
                            "type": "string",
                            "description": (
                                "How this news relates to THIS USER'S position — "
                                "their cost basis, P&L, weight. "
                                "e.g. 'Your 50-share position is up $240 today, "
                                "bringing unrealized gain to $1,840.' 1-2 sentences."
                            ),
                        },
                        "what_to_watch": {
                            "type": "string",
                            "description": "1 sentence on what to monitor for this position.",
                        },
                    },
                    "required": [
                        "symbol", "impact", "impact_magnitude",
                        "headline_driver", "position_context",
                    ],
                },
            },
            "unaffected_summary": {
                "type": "string",
                "description": (
                    "1 sentence on positions not significantly affected today "
                    "if any exist. Can be omitted if all positions are affected."
                ),
            },
            "macro_context": {
                "type": "string",
                "description": (
                    "1-2 sentences on relevant macro backdrop affecting "
                    "the overall portfolio today — sector rotation, "
                    "rates, earnings season, etc."
                ),
            },
            "overall_portfolio_impact": {
                "type": "string",
                "enum": ["net_positive", "net_negative", "mixed", "quiet"],
                "description": "Overall net impact on the portfolio today.",
            },
        },
        "required": [
            "portfolio_headline",
            "affected_positions",
            "overall_portfolio_impact",
        ],
    },
}


# ─────────────────────────────────────────────────────────────
# Data loaders
# ─────────────────────────────────────────────────────────────

def _load_positions(db, portfolio_id: str) -> list[dict]:
    """Load all open positions with full context."""
    try:
        from sqlalchemy import text
        rows = db.execute(text("""
            SELECT symbol, qty, avg_cost, market_value, unrealized_pnl
            FROM portfolio_positions
            WHERE portfolio_id = :pid AND qty > 0
        """), {"pid": portfolio_id}).mappings().fetchall()
        return [dict(r) for r in rows] if rows else []
    except Exception:
        return []


def _load_price_changes(db, symbols: list[str]) -> dict:
    """Today's price change % for each symbol."""
    from modules.market_data.service import get_price_history

    result = {}
    for sym in symbols:
        try:
            db.rollback()
        except Exception:
            pass
        try:
            df = get_price_history(db, sym, period="5d", interval="1d")
            if df is None or df.empty or "Close" not in df.columns:
                continue
            df = df.dropna(subset=["Close"])
            if len(df) < 2:
                continue
            curr = float(df["Close"].iloc[-1])
            prev = float(df["Close"].iloc[-2])
            chg  = ((curr - prev) / prev * 100) if prev else 0.0
            result[sym] = {
                "price":       round(curr, 2),
                "prev_close":  round(prev, 2),
                "day_chg_pct": round(chg, 2),
                "day_pnl_est": round(chg / 100 * prev, 2),
            }
        except Exception:
            pass
    return result


def _load_news_batch(symbols: list[str]) -> dict:
    """
    Fetch news for all symbols.
    Returns {symbol: [{"headline": str, "summary": str, "source": str, "datetime": str}]}
    Rate-limited: fetches max 8 symbols to respect Finnhub limits.
    """
    try:
        from modules.market_data.news_service import get_finnhub_news
    except ImportError:
        return {}

    news_map = {}
    for sym in symbols[:8]:
        try:
            items = get_finnhub_news(sym) or []
            if items:
                news_map[sym] = [
                    {
                        "headline": n.get("headline", ""),
                        "summary":  (n.get("summary") or "")[:200],
                        "source":   n.get("source", ""),
                        "datetime": n.get("datetime", ""),
                    }
                    for n in items[:4]
                ]
        except Exception:
            pass
    return news_map


def _load_analytics(db, tenant_id: str, symbols: list[str]) -> dict:
    """Load analytics snapshots for context."""
    try:
        from modules.analytics.models import AnalyticsSnapshot
        rows = (
            db.query(AnalyticsSnapshot)
            .filter(
                AnalyticsSnapshot.tenant_id == tenant_id,
                AnalyticsSnapshot.symbol.in_(symbols),
            )
            .order_by(AnalyticsSnapshot.asof.desc())
            .all()
        )
        seen, result = set(), {}
        for r in rows:
            if r.symbol not in seen:
                seen.add(r.symbol)
                result[r.symbol] = {
                    "sector":    getattr(r, "sector", None),
                    "rating":    getattr(r, "rating", None),
                    "rsi_14":    getattr(r, "rsi_14", None),
                    "trend":     getattr(r, "trend", None),
                    "composite": getattr(r, "composite_score", None),
                    "signal":    getattr(r, "signal", None),
                }
        return result
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────
# Context builder
# ─────────────────────────────────────────────────────────────

def _build_context(
    positions: list[dict],
    price_changes: dict,
    news_map: dict,
    analytics: dict,
    portfolio_id: str,
) -> dict:
    total_value = sum(
        float(p.get("market_value") or 0) for p in positions
    )

    enriched = []
    for pos in positions:
        sym  = str(pos.get("symbol", "")).upper()
        qty  = float(pos.get("qty") or 0)
        cost = float(pos.get("avg_cost") or 0)
        mv   = float(pos.get("market_value") or 0)
        upnl = float(pos.get("unrealized_pnl") or 0)

        px   = price_changes.get(sym, {})
        snap = analytics.get(sym, {})

        day_chg   = px.get("day_chg_pct", 0)
        curr_price= px.get("price") or (mv / qty if qty else 0)
        day_pnl   = qty * (curr_price - px.get("prev_close", curr_price))

        enriched.append({
            "symbol":          sym,
            "qty":             round(qty, 2),
            "avg_cost":        round(cost, 2),
            "current_price":   round(curr_price, 2),
            "market_value":    round(mv, 2),
            "unrealized_pnl":  round(upnl, 2),
            "day_change_pct":  round(day_chg, 2),
            "day_pnl_est":     round(day_pnl, 2),
            "weight_pct":      round(mv / total_value * 100, 1) if total_value else 0,
            "sector":          snap.get("sector", "Unknown"),
            "rating":          snap.get("rating", "N/A"),
            "rsi_14":          snap.get("rsi_14"),
            "trend":           snap.get("trend"),
            "composite":       snap.get("composite"),
            "signal":          snap.get("signal"),
            "news":            news_map.get(sym, []),
        })

    # Sort by absolute day impact on portfolio
    enriched.sort(
        key=lambda x: abs(x["day_pnl_est"]),
        reverse=True,
    )

    total_day_pnl = sum(p["day_pnl_est"] for p in enriched)

    return {
        "date":              datetime.now(timezone.utc).strftime("%B %d, %Y"),
        "total_portfolio_value": round(total_value, 2),
        "total_day_pnl":    round(total_day_pnl, 2),
        "total_day_pnl_pct":round(total_day_pnl / total_value * 100, 2) if total_value else 0,
        "n_positions":      len(enriched),
        "positions":        enriched,
    }


# ─────────────────────────────────────────────────────────────
# Generation
# ─────────────────────────────────────────────────────────────

def generate_holdings_explanation(
    db,
    portfolio_id: str,
    tenant_id: str,
) -> dict:
    """
    Generate the personalized holdings explanation.
    Returns structured dict for rendering.
    """
    positions = _load_positions(db, portfolio_id)
    if not positions:
        return {"error": "No open positions found."}

    symbols       = [str(p.get("symbol", "")).upper() for p in positions if p.get("symbol")]
    price_changes = _load_price_changes(db, symbols)
    news_map      = _load_news_batch(symbols)
    analytics     = _load_analytics(db, tenant_id, symbols)
    ctx           = _build_context(positions, price_changes, news_map, analytics, portfolio_id)

    try:
        client = _get_client()
    except Exception as e:
        return {"error": str(e), "_context": ctx}

    system = (
        "You are a personal portfolio advisor. "
        "Your job is to explain to an investor exactly how today's news and market "
        "moves are affecting their specific holdings — not generic market commentary. "
        "Every insight must reference their actual position: their cost basis, "
        "their P&L, their weight, their specific situation. "
        "Be direct and specific. Skip positions where nothing notable is happening. "
        "Call submit_holdings_explanation with your analysis."
    )

    # Build a concise prompt — highlight positions with news
    positions_with_news = [p for p in ctx["positions"] if p.get("news")]
    positions_moving    = [p for p in ctx["positions"] if abs(p.get("day_change_pct", 0)) > 1.0]
    notable = {p["symbol"] for p in positions_with_news + positions_moving}

    user_msg = (
        f"Explain today's impact on this portfolio ({ctx['date']}).\n\n"
        f"Portfolio overview:\n"
        f"  Total value: ${ctx['total_portfolio_value']:,.2f}\n"
        f"  Today's P&L: ${ctx['total_day_pnl']:+,.2f} ({ctx['total_day_pnl_pct']:+.2f}%)\n"
        f"  Positions: {ctx['n_positions']}\n\n"
        f"Holdings with news or significant moves today: {', '.join(notable) or 'None'}\n\n"
        f"Full position data:\n"
        f"{json.dumps(ctx['positions'], indent=2, default=str)}\n\n"
        f"For each position with news or a day move >1%:\n"
        f"- Cite the specific headline driving it\n"
        f"- Connect it to this user's actual position (their qty, cost basis, day P&L)\n"
        f"- Note what to watch\n"
        f"Skip positions with no notable news or price action today.\n"
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1500,
            system=system,
            tools=[EXPLAINER_TOOL],
            tool_choice={"type": "tool", "name": "submit_holdings_explanation"},
            messages=[{"role": "user", "content": user_msg}],
        )

        for block in message.content:
            if block.type == "tool_use" and block.name == "submit_holdings_explanation":
                result = block.input
                result["error"]        = None
                result["generated_at"] = datetime.now(timezone.utc).isoformat()
                result["_context"]     = ctx
                return result

        return {"error": "No explanation returned.", "_context": ctx}

    except Exception as e:
        return {"error": str(e), "_context": ctx}


# ─────────────────────────────────────────────────────────────
# Streamlit renderer
# ─────────────────────────────────────────────────────────────

def render_holdings_explainer(
    db,
    portfolio_id: str,
    tenant_id: str = "",
):
    """
    Render the personalized holdings explainer.

    Add to portfolio_ui.py overview tab, right after st.subheader("Overview"):

        from modules.digest.holdings_explainer import render_holdings_explainer
        render_holdings_explainer(
            db=db_session,
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
        )
    """
    st.markdown("### 🔍 What's Affecting Your Portfolio Today")
    st.caption(
        "Personalised to your holdings · Powered by Claude · "
        "Connects your positions to today's news and market moves"
    )

    if not _anthropic_available():
        st.warning("ANTHROPIC_API_KEY not set. Add it to Streamlit secrets.")
        return

    # Cache per portfolio per hour
    cache_key = (
        f"holdings_exp_{portfolio_id}_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"
    )

    col_gen, col_refresh, _ = st.columns([1, 1, 5])
    with col_gen:
        gen_btn = st.button(
            "🔍 Explain My Holdings",
            key=f"holdexp_btn_{portfolio_id}",
            type="primary",
            use_container_width=True,
        )
    with col_refresh:
        if st.button(
            "↺ Refresh",
            key=f"holdexp_refresh_{portfolio_id}",
            use_container_width=True,
        ):
            for k in list(st.session_state.keys()):
                if k.startswith(f"holdings_exp_{portfolio_id}"):
                    del st.session_state[k]
            st.rerun()

    if gen_btn:
        with st.spinner(
            "Scanning your holdings against today's news and market moves…"
        ):
            result = generate_holdings_explanation(
                db=db,
                portfolio_id=portfolio_id,
                tenant_id=tenant_id,
            )
            st.session_state[cache_key] = result

    result = st.session_state.get(cache_key)

    if not result:
        st.info(
            "Click **🔍 Explain My Holdings** to see a personalised briefing "
            "on what's happening with your specific positions today."
        )
        return

    if result.get("error"):
        st.error(f"Failed: {result['error']}")
        ctx = result.get("_context", {})
        if ctx:
            _render_context_fallback(ctx)
        return

    _render_explanation(result)


def _render_explanation(result: dict):
    """Render the full personalized explanation."""

    ctx          = result.get("_context", {})
    overall      = result.get("overall_portfolio_impact", "quiet")
    headline     = result.get("portfolio_headline", "")
    affected     = result.get("affected_positions", [])
    unaffected   = result.get("unaffected_summary", "")
    macro        = result.get("macro_context", "")
    generated_at = result.get("generated_at", "")

    # ── Overall impact header ─────────────────────────────────
    impact_cfg = {
        "net_positive": ("🟢", "#1D9E75", "Net positive day"),
        "net_negative": ("🔴", "#E24B4A", "Net negative day"),
        "mixed":        ("🟡", "#BA7517", "Mixed day"),
        "quiet":        ("⚪", "#8B949E", "Quiet day"),
    }
    icon, color, label = impact_cfg.get(overall, ("⚪", "#8B949E", ""))

    # Portfolio P&L summary
    total_pnl     = ctx.get("total_day_pnl", 0)
    total_pnl_pct = ctx.get("total_day_pnl_pct", 0)
    total_val     = ctx.get("total_portfolio_value", 0)
    n_pos         = ctx.get("n_positions", 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Today's P&L",
              f"${abs(total_pnl):,.2f}",
              delta=f"{'▲' if total_pnl >= 0 else '▼'} {abs(total_pnl_pct):.2f}%",
              delta_color="normal" if total_pnl >= 0 else "inverse")
    c2.metric("Portfolio Value", f"${total_val:,.0f}")
    c3.metric("Positions",       n_pos)
    c4.metric("Day",             f"{icon} {label}")

    if headline:
        st.markdown(
            f"<p style='font-size:15px;font-weight:500;margin:12px 0 4px'>{headline}</p>",
            unsafe_allow_html=True,
        )

    if macro:
        st.caption(f"📌 {macro}")

    st.markdown("")

    # ── Per-position impact cards ─────────────────────────────
    if not affected:
        st.info(
            "No significant news or price moves affecting your positions today. "
            "Your portfolio appears stable."
        )
    else:
        st.markdown(f"**{len(affected)} position(s) with notable activity today:**")
        st.markdown("")

        for pos in affected:
            _render_position_card(pos, ctx)

    # ── Unaffected positions note ─────────────────────────────
    if unaffected:
        st.caption(f"📋 {unaffected}")

    # ── Timestamp ─────────────────────────────────────────────
    if generated_at:
        try:
            dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            st.caption(
                f"Generated {dt.strftime('%b %d %Y %H:%M')} UTC · "
                "Personalised to your holdings · Not financial advice"
            )
        except Exception:
            pass


def _render_position_card(pos: dict, ctx: dict):
    """Render one position impact card."""
    sym       = pos.get("symbol", "")
    impact    = pos.get("impact", "neutral")
    magnitude = pos.get("impact_magnitude", "low")
    driver    = pos.get("headline_driver", "")
    context_  = pos.get("position_context", "")
    watch     = pos.get("what_to_watch", "")

    impact_cfg = {
        "positive": ("🟢", "success"),
        "negative": ("🔴", "error"),
        "mixed":    ("🟡", "warning"),
        "neutral":  ("⚪", "info"),
    }
    mag_cfg = {
        "high":   "⬆️⬆️",
        "medium": "⬆️",
        "low":    "➡️",
    }

    icon, render_fn = impact_cfg.get(impact, ("⚪", "info"))
    mag_icon = mag_cfg.get(magnitude, "")

    # Get position data from context
    pos_data = next(
        (p for p in ctx.get("positions", []) if p["symbol"] == sym),
        {}
    )
    day_chg = pos_data.get("day_change_pct", 0)
    day_pnl = pos_data.get("day_pnl_est", 0)
    weight  = pos_data.get("weight_pct", 0)

    # Build card content
    header = (
        f"{icon} **{sym}** {mag_icon} &nbsp; "
        f"`{day_chg:+.2f}%` today &nbsp; "
        f"`${day_pnl:+,.2f}` day P&L &nbsp; "
        f"`{weight:.1f}%` of portfolio"
    )

    with st.container():
        st.markdown(header, unsafe_allow_html=True)

        if driver:
            st.markdown(f"**📰 Driver:** {driver}")

        if context_:
            if impact == "positive":
                st.success(context_)
            elif impact == "negative":
                st.error(context_)
            else:
                st.info(context_)

        if watch:
            st.caption(f"👁️ Watch: {watch}")

        st.markdown("")


def _render_context_fallback(ctx: dict):
    """Show raw position data when Claude fails."""
    positions = ctx.get("positions", [])
    if not positions:
        return

    st.markdown("**Holdings summary (AI explanation unavailable):**")
    rows = [{
        "Symbol":    p["symbol"],
        "Weight":    f"{p.get('weight_pct', 0):.1f}%",
        "Day Chg":   f"{p.get('day_change_pct', 0):+.2f}%",
        "Day P&L":   f"${p.get('day_pnl_est', 0):+,.2f}",
        "News":      f"{len(p.get('news', []))} item(s)",
    } for p in positions]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)