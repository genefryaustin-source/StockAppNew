"""
modules/digest/portfolio_digest.py

Portfolio Digest — "Here's what moved your portfolio today and why."

A daily AI briefing that:
  - Pulls live positions with market values, weights, and P&L
  - Fetches today's price changes for each holding
  - Connects each mover to relevant news headlines
  - Synthesizes everything into a structured plain-English digest via Claude

Integration — add to portfolio_ui.py inside tab_intelligence:
    from modules.digest.portfolio_digest import render_portfolio_digest
    render_portfolio_digest(
        db=db_session,
        portfolio_id=portfolio_id,
        portfolio_name=portfolio_name,
        tenant_id=tenant_id,
    )
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text


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
# Tool schema
# ─────────────────────────────────────────────────────────────

DIGEST_TOOL = {
    "name": "submit_portfolio_digest",
    "description": (
        "Submit a structured daily portfolio digest explaining what moved "
        "the portfolio today and why."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "headline": {
                "type": "string",
                "description": (
                    "One punchy sentence summarising the portfolio's day. "
                    "e.g. 'Portfolio gained 1.4% led by NVDA and META, "
                    "while energy holdings dragged.' Max 140 chars."
                ),
            },
            "portfolio_summary": {
                "type": "string",
                "description": (
                    "2-3 sentences on overall portfolio performance today — "
                    "total gain/loss, best/worst performers, sector dynamics."
                ),
            },
            "top_movers": {
                "type": "array",
                "description": "Analysis of the top 3-5 movers (up or down).",
                "items": {
                    "type": "object",
                    "properties": {
                        "symbol":      {"type": "string"},
                        "direction":   {"type": "string", "enum": ["up", "down", "flat"]},
                        "day_change_pct": {"type": "number"},
                        "pnl_impact":  {"type": "string",
                                        "description": "e.g. '+$1,240 (+0.4% of portfolio)'"},
                        "explanation": {"type": "string",
                                        "description": "1-2 sentences on WHY it moved, citing news if available."},
                    },
                    "required": ["symbol", "direction", "explanation"],
                },
            },
            "sector_commentary": {
                "type": "string",
                "description": (
                    "1-2 sentences on sector-level trends within the portfolio today. "
                    "Which sectors helped, which hurt?"
                ),
            },
            "news_impact": {
                "type": "string",
                "description": (
                    "2 sentences on the most market-moving news items that affected "
                    "holdings today. Cite specific headlines if provided."
                ),
            },
            "risk_notes": {
                "type": "string",
                "description": (
                    "1-2 sentences on any risk signals — concentrated losses, "
                    "high-risk positions moving against portfolio, or unusual volatility."
                ),
            },
            "what_to_watch": {
                "type": "string",
                "description": (
                    "2-3 bullet points (• prefix, newline separated) on what to "
                    "monitor tomorrow — upcoming earnings, key price levels, macro events."
                ),
            },
            "overall_tone": {
                "type": "string",
                "enum": ["Strong Day", "Positive", "Mixed", "Slightly Negative", "Rough Day"],
            },
            "confidence": {
                "type": "integer",
                "description": "Data quality confidence 40-95.",
            },
        },
        "required": [
            "headline", "portfolio_summary", "top_movers",
            "overall_tone", "confidence",
        ],
    },
}


# ─────────────────────────────────────────────────────────────
# Data loaders
# ─────────────────────────────────────────────────────────────

def _load_positions(db, portfolio_id: str) -> list[dict]:
    """Load positions with symbol, qty, cost_basis, market_value."""
    try:
        rows = db.execute(text("""
            SELECT symbol, qty, avg_cost, market_value, unrealized_pnl
            FROM portfolio_positions
            WHERE portfolio_id = :pid
        """), {"pid": portfolio_id}).mappings().fetchall()

        if not rows:
            # Try alternate column names
            rows = db.execute(text("""
                SELECT symbol, quantity as qty, cost_basis as avg_cost,
                       0.0 as market_value, 0.0 as unrealized_pnl
                FROM portfolio_positions
                WHERE portfolio_id = :pid
            """), {"pid": portfolio_id}).mappings().fetchall()

        return [dict(r) for r in rows] if rows else []
    except Exception as e:
        print(f"[portfolio_digest] positions load error: {e}")
        return []


def _load_price_changes(db, symbols: list[str]) -> dict:
    """
    Get today's price change % for each symbol using recent price history.
    Returns {symbol: {"price": float, "day_chg_pct": float, "prev_close": float}}
    """
    from modules.market_data.service import get_price_history

    result = {}
    for sym in symbols:
        try:
            df = get_price_history(db, sym, period="5d", interval="1d")
            if df is None or df.empty or "Close" not in df.columns:
                continue

            df = df.dropna(subset=["Close"]).sort_values(
                "Date" if "Date" in df.columns else df.columns[0]
            )

            if len(df) < 2:
                result[sym] = {
                    "price": float(df["Close"].iloc[-1]),
                    "day_chg_pct": 0.0,
                    "prev_close": float(df["Close"].iloc[-1]),
                }
                continue

            curr  = float(df["Close"].iloc[-1])
            prev  = float(df["Close"].iloc[-2])
            chg   = ((curr - prev) / prev * 100) if prev else 0.0

            result[sym] = {
                "price":       round(curr, 2),
                "day_chg_pct": round(chg, 2),
                "prev_close":  round(prev, 2),
            }
        except Exception as e:
            print(f"[portfolio_digest] price error {sym}: {e}")

    return result


def _load_news(symbols: list[str]) -> dict:
    """
    Fetch recent news for each symbol.
    Returns {symbol: [{"headline": str, "summary": str, "source": str}]}
    """
    try:
        from modules.market_data.news_service import get_finnhub_news
    except ImportError:
        return {}

    news_map = {}
    for sym in symbols[:10]:  # Cap to avoid rate limits
        try:
            items = get_finnhub_news(sym) or []
            news_map[sym] = [
                {
                    "headline": n.get("headline", ""),
                    "summary":  (n.get("summary") or "")[:180],
                    "source":   n.get("source", ""),
                }
                for n in items[:3]
            ]
        except Exception:
            pass
    return news_map


def _load_analytics(db, tenant_id: str, symbols: list[str]) -> dict:
    """Load analytics snapshots for portfolio symbols."""
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
                    "rating":    getattr(r, "rating", None),
                    "sector":    getattr(r, "sector", None),
                    "composite": getattr(r, "composite_score", None),
                    "momentum":  getattr(r, "momentum_score", None),
                    "risk":      getattr(r, "risk_score", None),
                }
        return result
    except Exception as e:
        print(f"[portfolio_digest] analytics load error: {e}")
        return {}


# ─────────────────────────────────────────────────────────────
# Context builder
# ─────────────────────────────────────────────────────────────

def _build_context(
    positions: list[dict],
    price_changes: dict,
    news_map: dict,
    analytics: dict,
    portfolio_name: str,
) -> dict:
    """Assemble the full context dict for Claude."""

    today = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # Enrich positions with live price data
    enriched = []
    total_value = 0.0
    total_pnl   = 0.0

    for pos in positions:
        sym  = str(pos.get("symbol", "")).upper()
        qty  = float(pos.get("qty") or pos.get("quantity") or 0)
        cost = float(pos.get("avg_cost") or pos.get("cost_basis") or 0)
        mkt  = float(pos.get("market_value") or 0)

        px_data = price_changes.get(sym, {})
        live_px  = px_data.get("price") or (mkt / qty if qty else 0)
        day_chg  = px_data.get("day_chg_pct", 0.0)
        prev_px  = px_data.get("prev_close", live_px)

        live_value   = qty * live_px if qty and live_px else mkt
        day_pnl      = qty * (live_px - prev_px) if qty and live_px and prev_px else 0.0
        unrealized   = qty * (live_px - cost) if qty and live_px and cost else 0.0

        total_value += live_value
        total_pnl   += day_pnl

        snap = analytics.get(sym, {})
        enriched.append({
            "symbol":       sym,
            "qty":          round(qty, 4),
            "cost_basis":   round(cost, 2),
            "live_price":   round(live_px, 2),
            "day_chg_pct":  round(day_chg, 2),
            "day_pnl_$":    round(day_pnl, 2),
            "market_value": round(live_value, 2),
            "unrealized_pnl": round(unrealized, 2),
            "sector":       snap.get("sector", "Unknown"),
            "rating":       snap.get("rating", "N/A"),
            "momentum":     snap.get("momentum"),
            "risk_score":   snap.get("risk"),
            "news":         news_map.get(sym, []),
        })

    # Sort by absolute day P&L impact
    enriched.sort(key=lambda x: abs(x.get("day_pnl_$", 0)), reverse=True)

    # Portfolio-level weight
    for p in enriched:
        p["weight_pct"] = round(p["market_value"] / total_value * 100, 2) if total_value else 0

    # Sector summary
    sector_pnl: dict = {}
    for p in enriched:
        s = p.get("sector", "Unknown")
        sector_pnl[s] = sector_pnl.get(s, 0.0) + p.get("day_pnl_$", 0.0)

    return {
        "portfolio_name":    portfolio_name,
        "date":              today,
        "total_value":       round(total_value, 2),
        "total_day_pnl":     round(total_pnl, 2),
        "total_day_pnl_pct": round(total_pnl / total_value * 100, 2) if total_value else 0,
        "n_positions":       len(enriched),
        "positions":         enriched[:15],     # Top 15 by impact for prompt efficiency
        "sector_pnl":        sector_pnl,
        "best_performer":    enriched[0]["symbol"] if enriched else None,
        "worst_performer":   enriched[-1]["symbol"] if enriched else None,
    }


# ─────────────────────────────────────────────────────────────
# Generation
# ─────────────────────────────────────────────────────────────

def generate_portfolio_digest(
    db,
    portfolio_id: str,
    portfolio_name: str,
    tenant_id: str,
) -> dict:
    """Generate the portfolio digest. Returns structured dict."""

    # Load all data
    positions = _load_positions(db, portfolio_id)
    if not positions:
        return {"error": "No positions found in portfolio."}

    symbols      = [str(p.get("symbol", "")).upper() for p in positions if p.get("symbol")]
    price_changes = _load_price_changes(db, symbols)
    news_map     = _load_news(symbols)
    analytics    = _load_analytics(db, tenant_id, symbols)

    ctx = _build_context(positions, price_changes, news_map, analytics, portfolio_name)

    # Call Claude
    try:
        client = _get_client()
    except EnvironmentError as e:
        return {"error": str(e), "_context": ctx}

    system = (
        "You are a senior portfolio manager writing a daily briefing for your clients. "
        "Write the Portfolio Digest in plain English — clear, specific, and actionable. "
        "Reference actual numbers (prices, % changes, dollar P&L) from the data. "
        "Explain WHY positions moved by connecting them to news where available. "
        "Be direct. No filler. You must call the submit_portfolio_digest tool."
    )

    user_msg = (
        f"Write a Portfolio Digest for '{portfolio_name}' for {ctx['date']}.\n\n"
        f"Portfolio data:\n{json.dumps(ctx, indent=2, default=str)}\n\n"
        f"Key points to address:\n"
        f"- Overall portfolio P&L: ${ctx['total_day_pnl']:+,.2f} "
        f"({ctx['total_day_pnl_pct']:+.2f}%)\n"
        f"- Top mover UP: {max(ctx['positions'], key=lambda x: x.get('day_chg_pct', 0))['symbol'] if ctx['positions'] else 'N/A'}\n"
        f"- Top mover DOWN: {min(ctx['positions'], key=lambda x: x.get('day_chg_pct', 0))['symbol'] if ctx['positions'] else 'N/A'}\n"
        f"- For each top mover, explain WHY using the news field in the position data.\n"
        f"- Note any sectors that had outsized impact.\n"
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1500,
            system=system,
            tools=[DIGEST_TOOL],
            tool_choice={"type": "tool", "name": "submit_portfolio_digest"},
            messages=[{"role": "user", "content": user_msg}],
        )

        for block in message.content:
            if block.type == "tool_use" and block.name == "submit_portfolio_digest":
                result = block.input
                result["error"]        = None
                result["generated_at"] = datetime.now(timezone.utc).isoformat()
                result["_context"]     = ctx
                return result

        return {"error": "No digest returned from API.", "_context": ctx}

    except Exception as e:
        return {"error": str(e), "_context": ctx}


# ─────────────────────────────────────────────────────────────
# Streamlit renderer
# ─────────────────────────────────────────────────────────────

def render_portfolio_digest(
    db,
    portfolio_id: str,
    portfolio_name: str = "Portfolio",
    tenant_id: str = "",
):
    """
    Render the Portfolio Digest card.
    Add this at the TOP of tab_intelligence in portfolio_ui.py:

        from modules.digest.portfolio_digest import render_portfolio_digest
        render_portfolio_digest(
            db=db_session,
            portfolio_id=portfolio_id,
            portfolio_name=portfolio_name or "Portfolio",
            tenant_id=tenant_id,
        )
        st.divider()
    """
    st.markdown("### 📰 Daily Portfolio Digest")
    st.caption(
        "AI-powered briefing — what moved your portfolio today and why · "
        "Powered by Claude · Not financial advice"
    )

    if not _anthropic_available():
        st.warning("ANTHROPIC_API_KEY not set. Add it to Streamlit secrets.")
        return

    # Cache key — per portfolio per hour
    cache_key = (
        f"port_digest_{portfolio_id}_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"
    )

    col_gen, col_refresh, _ = st.columns([1, 1, 5])
    with col_gen:
        gen_btn = st.button(
            "📰 Generate Digest",
            key=f"portdigest_btn_{portfolio_id}",
            type="primary",
            use_container_width=True,
        )
    with col_refresh:
        if st.button("↺ Refresh", key=f"portdigest_refresh_{portfolio_id}",
                     use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith(f"port_digest_{portfolio_id}"):
                    del st.session_state[k]
            st.rerun()

    if gen_btn:
        with st.spinner("Analysing portfolio and generating digest…"):
            digest = generate_portfolio_digest(
                db=db,
                portfolio_id=portfolio_id,
                portfolio_name=portfolio_name,
                tenant_id=tenant_id,
            )
            st.session_state[cache_key] = digest

    digest = st.session_state.get(cache_key)

    if not digest:
        st.info(
            "Click **📰 Generate Digest** to get today's portfolio briefing — "
            "what moved, why it moved, and what to watch tomorrow."
        )
        return

    if digest.get("error"):
        st.error(f"Digest failed: {digest['error']}")
        # Still show context summary if available
        ctx = digest.get("_context", {})
        if ctx:
            _render_context_fallback(ctx)
        return

    _render_digest(digest)


def _render_digest(digest: dict):
    """Render the full digest card."""

    tone = digest.get("overall_tone", "Mixed")
    confidence = digest.get("confidence", 60)
    ctx = digest.get("_context", {})

    tone_config = {
        "Strong Day":        ("🟢", "#1D9E75"),
        "Positive":          ("🟢", "#4CAF50"),
        "Mixed":             ("🟡", "#BA7517"),
        "Slightly Negative": ("🟠", "#FF8C00"),
        "Rough Day":         ("🔴", "#E24B4A"),
    }
    tone_emoji, tone_color = tone_config.get(tone, ("⚪", "#8B949E"))

    # ── Headline ──────────────────────────────────────────────
    headline = digest.get("headline", "")
    if headline:
        st.markdown(
            f"<h4 style='margin:0 0 8px 0'>{tone_emoji} {headline}</h4>",
            unsafe_allow_html=True,
        )

    # ── Portfolio-level stats from context ────────────────────
    if ctx:
        total_pnl     = ctx.get("total_day_pnl", 0)
        total_pnl_pct = ctx.get("total_day_pnl_pct", 0)
        total_val     = ctx.get("total_value", 0)
        n_pos         = ctx.get("n_positions", 0)

        pnl_color = "#1D9E75" if total_pnl >= 0 else "#E24B4A"
        arrow     = "▲" if total_pnl >= 0 else "▼"

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Portfolio Value",  f"${total_val:,.0f}")
        c2.metric("Day P&L",
                  f"${abs(total_pnl):,.2f}",
                  delta=f"{arrow} {abs(total_pnl_pct):.2f}%",
                  delta_color="normal" if total_pnl >= 0 else "inverse")
        c3.metric("Positions", n_pos)
        c4.metric(
            "Tone",
            f"{tone_emoji} {tone}",
        )
        c5.metric("Confidence", f"{confidence}%")

    st.markdown("")

    # ── Portfolio summary ─────────────────────────────────────
    summary = digest.get("portfolio_summary", "")
    if summary:
        st.markdown(summary)
        st.markdown("")

    # ── Top movers ────────────────────────────────────────────
    movers = digest.get("top_movers", [])
    if movers:
        st.markdown("**📊 Top Movers**")
        for m in movers:
            sym  = m.get("symbol", "")
            dirn = m.get("direction", "flat")
            chg  = m.get("day_change_pct")
            impact = m.get("pnl_impact", "")
            expl = m.get("explanation", "")

            icon  = "🟢" if dirn == "up" else "🔴" if dirn == "down" else "⚪"
            chg_str = f"{chg:+.2f}%" if chg is not None else ""

            with st.container():
                col_sym, col_exp = st.columns([1, 5])
                with col_sym:
                    st.markdown(
                        f"**{icon} {sym}**  \n"
                        f"`{chg_str}`  \n"
                        f"<span style='font-size:11px;color:#8B949E'>{impact}</span>",
                        unsafe_allow_html=True,
                    )
                with col_exp:
                    st.markdown(expl)
        st.markdown("")

    # ── Sector commentary ─────────────────────────────────────
    sector_text = digest.get("sector_commentary", "")
    if sector_text:
        st.markdown("**🏭 Sector Commentary**")
        st.markdown(sector_text)
        st.markdown("")

        # Sector P&L bar chart from context
        sector_pnl = ctx.get("sector_pnl", {})
        if sector_pnl:
            _render_sector_pnl_bars(sector_pnl)

    # ── News impact ───────────────────────────────────────────
    news_text = digest.get("news_impact", "")
    if news_text:
        st.markdown("**📰 News Impact**")
        st.markdown(news_text)
        st.markdown("")

    # ── Risk notes ────────────────────────────────────────────
    risk_text = digest.get("risk_notes", "")
    if risk_text:
        st.markdown("**⚠️ Risk Notes**")
        st.warning(risk_text)
        st.markdown("")

    # ── What to watch ─────────────────────────────────────────
    wtw = digest.get("what_to_watch", "")
    if wtw:
        st.markdown("**👁️ What to Watch Tomorrow**")
        for line in wtw.split("\n"):
            line = line.strip()
            if line:
                if not line.startswith("•"):
                    line = f"• {line}"
                st.markdown(line)
        st.markdown("")

    # ── Generated timestamp ───────────────────────────────────
    ts = digest.get("generated_at", "")
    if ts:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            st.caption(
                f"Generated {dt.strftime('%b %d %Y %H:%M')} UTC · "
                "For informational purposes only. Not investment advice."
            )
        except Exception:
            st.caption("For informational purposes only. Not investment advice.")


def _render_sector_pnl_bars(sector_pnl: dict):
    """Render a compact horizontal bar chart of sector P&L."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        sectors = list(sector_pnl.keys())
        values  = [sector_pnl[s] for s in sectors]

        if not any(v != 0 for v in values):
            return

        # Sort by value
        pairs  = sorted(zip(values, sectors), reverse=True)
        values = [p[0] for p in pairs]
        sectors= [p[1] for p in pairs]

        colors = ["#1D9E75" if v >= 0 else "#E24B4A" for v in values]

        fig, ax = plt.subplots(figsize=(8, max(1.5, len(sectors) * 0.4)),
                               facecolor="#0F1117")
        ax.set_facecolor("#161B22")
        ax.barh(sectors, values, color=colors, alpha=0.85, height=0.6)
        ax.axvline(0, color="#30363D", linewidth=0.8)
        ax.set_xlabel("Day P&L ($)", color="#8B949E", fontsize=8)
        ax.tick_params(colors="#8B949E", labelsize=8)
        ax.spines[:].set_color("#21262D")
        ax.grid(axis="x", color="#21262D", linewidth=0.4, alpha=0.6)
        ax.set_title("Sector P&L Today", color="#C9D1D9", fontsize=9, pad=6)

        plt.tight_layout()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    except Exception:
        pass  # Chart is bonus — never break the page


def _render_context_fallback(ctx: dict):
    """Show raw context data when Claude fails."""
    st.markdown("**Portfolio data available (AI generation failed):**")
    positions = ctx.get("positions", [])
    if positions:
        rows = [{
            "Symbol":   p["symbol"],
            "Weight":   f"{p.get('weight_pct', 0):.1f}%",
            "Day Chg":  f"{p.get('day_chg_pct', 0):+.2f}%",
            "Day P&L":  f"${p.get('day_pnl_$', 0):+,.2f}",
            "Sector":   p.get("sector", "—"),
        } for p in positions]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)