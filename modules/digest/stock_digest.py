"""
modules/digest/stock_digest.py

Stock Digest — Robinhood Cortex equivalent for Market Terminal.

Synthesizes price action, news headlines, technicals, fundamentals,
sentiment, and analyst rankings into a structured plain-English briefing
powered by Claude (Anthropic API).

Appears on the Stock Dashboard page directly below the price chart.

Usage:
    from modules.digest.stock_digest import render_stock_digest
    render_stock_digest(symbol, snapshot, news_items, sentiment, price_df)
"""

from __future__ import annotations

import os
import json
import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st


# ─────────────────────────────────────────────────────────────
# Anthropic client
# ─────────────────────────────────────────────────────────────

def _get_client():
    import anthropic
    from modules.admin.tenant_api_keys import get_provider_key
    key = get_provider_key("ANTHROPIC_API_KEY")
    if not key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set.")
    return anthropic.Anthropic(api_key=key)


def _anthropic_available() -> bool:
    try:
        from modules.admin.tenant_api_keys import get_provider_key
        key = get_provider_key("ANTHROPIC_API_KEY")
        return bool(key)
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# Tool schema — structured digest output
# ─────────────────────────────────────────────────────────────

DIGEST_TOOL = {
    "name": "submit_stock_digest",
    "description": (
        "Submit a structured stock digest explaining why a stock is moving "
        "and what investors should know right now."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "headline": {
                "type": "string",
                "description": (
                    "One punchy sentence summarising the key story for this stock right now. "
                    "Like a Bloomberg terminal headline. Max 120 characters."
                ),
            },
            "price_action": {
                "type": "string",
                "description": (
                    "1-2 sentences on recent price movement, trend, and momentum. "
                    "Reference specific numbers from the data."
                ),
            },
            "why_moving": {
                "type": "string",
                "description": (
                    "2-3 sentences explaining the primary drivers of recent price action. "
                    "Cite specific news events, earnings, macro factors, or technicals."
                ),
            },
            "fundamentals": {
                "type": "string",
                "description": (
                    "2 sentences on the company's fundamental health — "
                    "revenue growth, margins, valuation, or balance sheet strength. "
                    "Only include if data is available."
                ),
            },
            "technicals": {
                "type": "string",
                "description": (
                    "1-2 sentences on key technical levels — RSI, moving averages, "
                    "support/resistance, trend. Reference specific values from the data."
                ),
            },
            "sentiment": {
                "type": "string",
                "description": (
                    "1 sentence on news sentiment and analyst consensus. "
                    "Is the news flow bullish, bearish, or mixed?"
                ),
            },
            "what_to_watch": {
                "type": "string",
                "description": (
                    "2-3 bullet points (as a single string, each on a new line starting with •) "
                    "of the key things investors should monitor in the near term — "
                    "upcoming catalysts, risk events, price levels to watch."
                ),
            },
            "risk_flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "List of 0-3 specific risk factors for this stock right now. "
                    "Empty array if no notable risks."
                ),
            },
            "overall_tone": {
                "type": "string",
                "enum": ["Bullish", "Cautiously Bullish", "Neutral", "Cautiously Bearish", "Bearish"],
                "description": "Overall analyst tone based on all available data.",
            },
            "confidence": {
                "type": "integer",
                "description": "Confidence in the digest quality 40-95, based on data richness.",
            },
        },
        "required": [
            "headline", "price_action", "why_moving",
            "technicals", "sentiment", "what_to_watch",
            "overall_tone", "confidence",
        ],
    },
}


# ─────────────────────────────────────────────────────────────
# Data builder
# ─────────────────────────────────────────────────────────────

def _build_context(
    symbol: str,
    snapshot,
    news_items: list,
    sentiment: dict,
    price_df: Optional[pd.DataFrame],
) -> dict:
    """Build a rich context dict from all available data sources."""

    ctx: dict = {"symbol": symbol}

    # ── Price action ──────────────────────────────────────────
    if price_df is not None and not price_df.empty:
        df = price_df.copy()
        # Normalise column names
        col_map = {c: c.lower() for c in df.columns}
        df = df.rename(columns=col_map)
        if "close" in df.columns:
            closes = df["close"].dropna().tolist()
            if closes:
                last  = closes[-1]
                prev  = closes[-2] if len(closes) > 1 else last
                w_ago = closes[-5] if len(closes) > 5 else closes[0]
                m_ago = closes[-21] if len(closes) > 21 else closes[0]
                ctx["price"] = {
                    "last":         round(last, 2),
                    "day_chg_pct":  round((last - prev) / prev * 100, 2) if prev else 0,
                    "week_chg_pct": round((last - w_ago) / w_ago * 100, 2) if w_ago else 0,
                    "month_chg_pct":round((last - m_ago) / m_ago * 100, 2) if m_ago else 0,
                    "52w_high":     round(max(closes[-252:] if len(closes) > 252 else closes), 2),
                    "52w_low":      round(min(closes[-252:] if len(closes) > 252 else closes), 2),
                }

    # ── Snapshot (analytics) ──────────────────────────────────
    if snapshot:
        def _g(attr, default=None):
            v = getattr(snapshot, attr, default)
            try:
                return float(v) if v is not None else default
            except Exception:
                return v

        ctx["analytics"] = {
            "rating":           getattr(snapshot, "rating", None),
            "composite_score":  _g("composite_score"),
            "confidence_score": _g("confidence_score"),
            "sector":           getattr(snapshot, "sector", None),
            "quality_score":    _g("quality_score"),
            "growth_score":     _g("growth_score"),
            "value_score":      _g("value_score"),
            "momentum_score":   _g("momentum_score"),
            "risk_score":       _g("risk_score"),
            "rsi_14":           _g("rsi_14"),
            "sma_50":           _g("sma_50"),
            "sma_200":          _g("sma_200"),
            "support":          _g("support"),
            "resistance":       _g("resistance"),
            "trend":            getattr(snapshot, "trend", None),
            "vol_20d":          _g("vol_20d"),
            "pe_ttm":           _g("pe_ttm"),
            "ps_ttm":           _g("ps_ttm"),
            "ev_ebitda":        _g("ev_ebitda"),
            "gross_margin":     _g("gross_margin"),
            "operating_margin": _g("operating_margin"),
            "fcf_margin":       _g("fcf_margin"),
            "revenue_cagr":     _g("revenue_cagr"),
            "max_drawdown_1y":  _g("max_drawdown_1y"),
            "rating_rationale": getattr(snapshot, "rating_rationale", None),
        }
        # Remove None values to keep prompt compact
        ctx["analytics"] = {k: v for k, v in ctx["analytics"].items() if v is not None}

    # ── News headlines ────────────────────────────────────────
    if news_items:
        ctx["news"] = [
            {
                "headline": n.get("headline", ""),
                "summary":  (n.get("summary") or "")[:200],
                "source":   n.get("source", ""),
                "date":     n.get("datetime", ""),
            }
            for n in news_items[:8]
        ]

    # ── Sentiment ─────────────────────────────────────────────
    if sentiment:
        ctx["sentiment"] = {
            "bullish_count": sentiment.get("bullish", 0),
            "bearish_count": sentiment.get("bearish", 0),
            "score":         round(float(sentiment.get("score", 0)), 3),
        }

    return ctx


# ─────────────────────────────────────────────────────────────
# Core generation function
# ─────────────────────────────────────────────────────────────

def generate_digest(
    symbol: str,
    snapshot,
    news_items: list,
    sentiment: dict,
    price_df: Optional[pd.DataFrame],
) -> dict:
    """
    Generate a Stock Digest using Claude via tool use.
    Returns a structured dict ready for rendering.
    """
    ctx = _build_context(symbol, snapshot, news_items, sentiment, price_df)

    try:
        client = _get_client()
    except EnvironmentError as e:
        return {"error": str(e)}

    system_prompt = (
        "You are a senior equity analyst at an institutional research terminal. "
        "Your job is to write Stock Digests — concise, plain-English briefings that explain "
        "what is happening with a stock right now and why it matters. "
        "Be specific. Reference actual numbers from the data. "
        "Do not use jargon or hedge excessively. Write like a Bloomberg brief, not an academic paper. "
        "You must call the submit_stock_digest tool with your analysis."
    )

    user_prompt = (
        f"Write a Stock Digest for {symbol} based on this data:\n\n"
        f"{json.dumps(ctx, indent=2, default=str)}\n\n"
        f"Today is {datetime.now(timezone.utc).strftime('%B %d, %Y')}. "
        f"Focus on what is most relevant RIGHT NOW. "
        f"If news is present, lead with what the news means for the stock. "
        f"If no news, lead with price action and technicals."
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=system_prompt,
            tools=[DIGEST_TOOL],
            tool_choice={"type": "tool", "name": "submit_stock_digest"},
            messages=[{"role": "user", "content": user_prompt}],
        )

        for block in message.content:
            if block.type == "tool_use" and block.name == "submit_stock_digest":
                result = block.input
                result["symbol"] = symbol
                result["generated_at"] = datetime.now(timezone.utc).isoformat()
                result["error"] = None
                return result

        return {"error": "No digest returned from API."}

    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────
# Streamlit UI renderer
# ─────────────────────────────────────────────────────────────

def render_stock_digest(
    symbol: str,
    snapshot=None,
    news_items: Optional[list] = None,
    sentiment: Optional[dict] = None,
    price_df: Optional[pd.DataFrame] = None,
):
    """
    Render the Stock Digest card on the Stock Dashboard.
    Call this right after the price chart in stock_dashboard_ui.py:

        from modules.digest.stock_digest import render_stock_digest
        render_stock_digest(symbol, snapshot, news_items, sentiment, px)
    """
    st.markdown("---")
    st.markdown("### 🧠 AI Stock Digest")
    st.caption(
        "Powered by Claude · Synthesizes price action, news, technicals, "
        "and fundamentals into a plain-English briefing · Not financial advice"
    )

    if not _anthropic_available():
        st.warning(
            "⚠️ ANTHROPIC_API_KEY not set. "
            "Add it to Streamlit secrets to enable Stock Digests."
        )
        return

    cache_key = f"digest_{symbol}_{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"

    col_btn, col_refresh, _ = st.columns([1, 1, 5])
    with col_btn:
        generate_btn = st.button(
            "⚡ Generate Digest",
            key=f"digest_btn_{symbol}",
            type="primary",
            use_container_width=True,
        )
    with col_refresh:
        if st.button("↺ Refresh", key=f"digest_refresh_{symbol}", use_container_width=True):
            keys_to_clear = [k for k in st.session_state if k.startswith(f"digest_{symbol}")]
            for k in keys_to_clear:
                del st.session_state[k]
            st.rerun()

    if generate_btn:
        with st.spinner(f"Generating digest for {symbol}…"):
            digest = generate_digest(
                symbol=symbol,
                snapshot=snapshot,
                news_items=news_items or [],
                sentiment=sentiment or {},
                price_df=price_df,
            )
            st.session_state[cache_key] = digest

    digest = st.session_state.get(cache_key)

    if not digest:
        st.info(
            "Click **⚡ Generate Digest** to get an AI-powered briefing on "
            f"{symbol} — what's moving it, key technicals, and what to watch."
        )
        return

    if digest.get("error"):
        st.error(f"Digest generation failed: {digest['error']}")
        return

    _render_digest_card(digest, symbol)


def _render_digest_card(digest: dict, symbol: str):
    """Render the full digest card."""

    tone = digest.get("overall_tone", "Neutral")
    confidence = digest.get("confidence", 60)
    generated_at = digest.get("generated_at", "")

    tone_config = {
        "Bullish":            ("🟢", "#1D9E75", "#E1F5EE"),
        "Cautiously Bullish": ("🟡", "#4CAF50", "#F0F9F0"),
        "Neutral":            ("⚪", "#8B949E", "#F5F5F5"),
        "Cautiously Bearish": ("🟠", "#FF8C00", "#FFF3E0"),
        "Bearish":            ("🔴", "#E24B4A", "#FCEBEB"),
    }
    tone_emoji, tone_color, _ = tone_config.get(tone, ("⚪", "#8B949E", "#F5F5F5"))

    # ── Headline ──────────────────────────────────────────────
    headline = digest.get("headline", "")
    if headline:
        st.markdown(
            f"<h4 style='margin:0;padding:8px 0 4px;'>"
            f"{tone_emoji} {headline}"
            f"</h4>",
            unsafe_allow_html=True,
        )

    # ── Tone + confidence bar ─────────────────────────────────
    col_tone, col_conf, col_ts = st.columns([1, 1, 2])
    col_tone.markdown(
        f"**Tone:** <span style='color:{tone_color};font-weight:600'>{tone}</span>",
        unsafe_allow_html=True,
    )
    col_conf.markdown(f"**Confidence:** {confidence}%")
    if generated_at:
        try:
            ts = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            col_ts.caption(f"Generated {ts.strftime('%b %d %Y %H:%M')} UTC")
        except Exception:
            col_ts.caption(generated_at[:19])

    st.markdown("")

    # ── Main content sections ─────────────────────────────────
    sections = [
        ("📈 Price Action",    "price_action"),
        ("🔍 Why It's Moving", "why_moving"),
        ("📊 Fundamentals",    "fundamentals"),
        ("📉 Technicals",      "technicals"),
        ("📰 Sentiment",       "sentiment"),
    ]

    for label, key in sections:
        text = digest.get(key, "")
        if text:
            st.markdown(f"**{label}**")
            st.markdown(text)
            st.markdown("")

    # ── What to watch ─────────────────────────────────────────
    what_to_watch = digest.get("what_to_watch", "")
    if what_to_watch:
        st.markdown("**👁️ What to Watch**")
        # Render each bullet on its own line
        for line in what_to_watch.split("\n"):
            line = line.strip()
            if line:
                if not line.startswith("•"):
                    line = f"• {line}"
                st.markdown(line)
        st.markdown("")

    # ── Risk flags ────────────────────────────────────────────
    risk_flags = digest.get("risk_flags", [])
    if risk_flags:
        st.markdown("**🚩 Risk Flags**")
        for flag in risk_flags:
            st.warning(f"⚠️ {flag}")

    # ── Disclaimer ────────────────────────────────────────────
    st.caption(
        "This digest is AI-generated for informational purposes only. "
        "It is not investment advice. Always conduct your own research."
    )