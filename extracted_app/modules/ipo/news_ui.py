# ============================================================
# modules/ipo/news_ui.py
# IPO & Pre-IPO News + Sentiment UI
#
# Shared render function called from both:
#   render_ipo_center()    → context="ipo"
#   render_preipo_center() → context="preipo"
# ============================================================

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

# RerunException moved between Streamlit versions — import defensively.
try:
    from streamlit.runtime.scriptrunner import RerunException
except ImportError:
    try:
        from streamlit.runtime.scriptrunner.script_runner import RerunException
    except ImportError:
        # Streamlit 1.30+ uses a different path; fall back to base Exception
        # so the re-raise below still works (it just won't re-raise on rerun,
        # which is harmless — the rerun will still fire).
        RerunException = None  # type: ignore

from modules.ipo.news_service import (
    IPONewsArticle,
    list_ipo_news,
    news_to_dataframe,
    refresh_ipo_news,
    refresh_company_news,
    sentiment_summary,
    sentiment_over_time,
    source_breakdown,
)


# ---------------------------------------------------------------------------
# Helpers — safely re-raise RerunException regardless of Streamlit version
# ---------------------------------------------------------------------------

def _reraise_if_rerun(exc: Exception) -> None:
    """Re-raise if this is a Streamlit rerun signal, otherwise do nothing."""
    if RerunException is not None and isinstance(exc, RerunException):
        raise exc
    # Newer Streamlit raises StopException / RerunException under different names.
    # Catch by class name as a final fallback.
    if type(exc).__name__ in ("RerunException", "StopException", "RerunData"):
        raise exc


# ---------------------------------------------------------------------------
# Sentiment badge helpers
# ---------------------------------------------------------------------------

_SENTIMENT_COLORS = {
    "Bullish": "#22c55e",
    "Bearish": "#ef4444",
    "Neutral": "#94a3b8",
}

_SENTIMENT_EMOJI = {
    "Bullish": "🟢",
    "Bearish": "🔴",
    "Neutral": "⚪",
}


def _badge(label: str) -> str:
    color = _SENTIMENT_COLORS.get(label, "#94a3b8")
    emoji = _SENTIMENT_EMOJI.get(label, "⚪")
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:0.78rem;font-weight:600">{emoji} {label}</span>'
    )


def _render_sentiment_scorecard(summary: dict) -> None:
    total   = summary.get("total", 0)
    bull    = summary.get("bullish", 0)
    bear    = summary.get("bearish", 0)
    neutral = summary.get("neutral", 0)
    net     = summary.get("net_sentiment", 0.0)
    label   = summary.get("label", "Neutral")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Articles", total)
    c2.metric("🟢 Bullish", bull)
    c3.metric("🔴 Bearish", bear)
    c4.metric("⚪ Neutral", neutral)

    color = _SENTIMENT_COLORS.get(label, "#94a3b8")
    c5.markdown(
        f"""
        <div style="text-align:center;padding:8px 0">
            <div style="font-size:0.75rem;color:#888;margin-bottom:2px">Net Sentiment</div>
            <div style="font-size:1.6rem;font-weight:700;color:{color}">{net:+.1f}%</div>
            <div style="font-size:0.85rem;color:{color};font-weight:600">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_article_card(article: IPONewsArticle) -> None:
    pub     = article.published_at
    pub_str = pub.strftime("%b %d, %Y %H:%M UTC") if pub else "Unknown date"
    badge_html  = _badge(article.sentiment or "Neutral")
    title       = article.title or "Untitled"
    summary     = (article.summary or "")[:240]
    source      = article.source or "Unknown"
    url         = article.url or ""
    company     = article.company_hint or ""

    title_link  = (
        f'<a href="{url}" target="_blank" style="color:inherit;text-decoration:none;font-weight:600">{title}</a>'
        if url else f"<strong>{title}</strong>"
    )
    company_tag = (
        f' · <span style="font-size:0.78rem;color:#60a5fa">{company}</span>'
        if company else ""
    )

    st.markdown(
        f"""
        <div style="border:1px solid rgba(255,255,255,0.08);border-radius:8px;
                    padding:12px 16px;margin-bottom:8px;background:rgba(255,255,255,0.02)">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
                <span style="font-size:0.75rem;color:#94a3b8">{source}{company_tag} · {pub_str}</span>
                {badge_html}
            </div>
            <div style="font-size:0.95rem;margin-bottom:4px">{title_link}</div>
            <div style="font-size:0.82rem;color:#94a3b8">{summary}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_news_sentiment_tab(db, user, context: str = "ipo") -> None:
    """
    Renders the News & Sentiment tab.

    Parameters
    ----------
    db      : SQLAlchemy Session
    user    : dict  (standard user dict — needs tenant_id)
    context : "ipo" | "preipo"
    """
    tenant_id = user.get("tenant_id", "default_tenant")

    st.markdown("### IPO News & Sentiment Feed")
    st.caption(
        "Live IPO/pre-IPO news from RSS feeds (Renaissance Capital, IPO Monitor, "
        "Yahoo Finance), Finnhub market news, and NewsAPI. Sentiment scored automatically."
    )

    # -----------------------------------------------------------------------
    # Refresh controls
    # -----------------------------------------------------------------------
    with st.expander("Refresh news feed", expanded=True):
        r1, r2, r3, r4 = st.columns([1, 2, 1, 1])
        days_back_refresh = r1.number_input(
            "Days back", min_value=1, max_value=30, value=7, step=1,
            key=f"news_days_back_{context}",
        )
        symbol_input = r2.text_input(
            "Company ticker (optional, Finnhub-backed)", "",
            key=f"news_symbol_{context}",
        )
        btn_general = r3.button(
            "Refresh IPO News", type="primary", use_container_width=True,
            key=f"news_refresh_{context}",
        )
        btn_company = r4.button(
            "Refresh Ticker News", use_container_width=True,
            key=f"news_company_refresh_{context}",
        )

        if btn_general:
            with st.spinner("Fetching IPO news from all sources…"):
                try:
                    result = refresh_ipo_news(
                        db=db, tenant_id=tenant_id,
                        days_back=int(days_back_refresh),
                    )
                    st.success(
                        f"Fetched {result['fetched']} articles, "
                        f"{result['inserted']} new."
                    )
                    st.rerun()
                except Exception as e:
                    _reraise_if_rerun(e)
                    st.error(f"News refresh failed: {e}")

        if btn_company:
            sym = symbol_input.strip().upper()
            if not sym:
                st.warning("Enter a ticker symbol to refresh company-specific news.")
            else:
                with st.spinner(f"Fetching news for {sym}…"):
                    try:
                        result = refresh_company_news(
                            db=db, tenant_id=tenant_id,
                            symbol=sym, days_back=14,
                        )
                        st.success(
                            f"{sym}: fetched {result['fetched']}, "
                            f"inserted {result['inserted']}."
                        )
                        st.rerun()
                    except Exception as e:
                        _reraise_if_rerun(e)
                        st.error(f"Company news refresh failed: {e}")

    # -----------------------------------------------------------------------
    # Filter bar
    # -----------------------------------------------------------------------
    f1, f2, f3, f4 = st.columns([1, 1, 2, 1])
    days_view = f1.selectbox(
        "Period", [3, 7, 14, 30], index=1,
        format_func=lambda x: f"Last {x} days",
        key=f"news_period_{context}",
    )
    sentiment_filter = f2.selectbox(
        "Sentiment", ["All", "Bullish", "Bearish", "Neutral"], index=0,
        key=f"news_sentiment_{context}",
    )
    search         = f3.text_input("Search title / summary / source", "", key=f"news_search_{context}")
    company_filter = f4.text_input("Filter by company / ticker",      "", key=f"news_company_{context}")

    # -----------------------------------------------------------------------
    # Body — wrapped so any DB/render error shows inside the tab, not silently
    # -----------------------------------------------------------------------
    try:
        _render_news_body(
            db=db,
            tenant_id=tenant_id,
            context=context,
            days_view=int(days_view),
            sentiment_filter=sentiment_filter,
            search=search,
            company_filter=company_filter,
        )
    except Exception as e:
        _reraise_if_rerun(e)
        st.error(f"News & Sentiment tab error: {e}")
        st.exception(e)


def _render_news_body(
    db,
    tenant_id: str,
    context: str,
    days_view: int,
    sentiment_filter: str,
    search: str,
    company_filter: str,
) -> None:
    """Inner render — separated so the caller can catch and display errors cleanly."""

    # ---- Sentiment scorecard ----------------------------------------------
    st.divider()
    st.markdown("#### Sentiment Overview")
    summary = sentiment_summary(
        db=db,
        tenant_id=tenant_id,
        days_back=days_view,
        company_hint=company_filter.strip() or None,
    )
    _render_sentiment_scorecard(summary)

    # ---- Sentiment over time chart ----------------------------------------
    st.markdown("#### Sentiment Trend")
    trend_df = sentiment_over_time(db=db, tenant_id=tenant_id, days_back=days_view)
    if trend_df.empty:
        st.info("No trend data yet — use **Refresh IPO News** above to populate.")
    else:
        chart_df = trend_df.set_index("Date")[["Bullish", "Bearish", "Neutral"]]
        st.bar_chart(chart_df, color=["#22c55e", "#ef4444", "#94a3b8"])

    # ---- Source breakdown -------------------------------------------------
    with st.expander("Source breakdown", expanded=False):
        src_df = source_breakdown(db=db, tenant_id=tenant_id, days_back=days_view)
        if src_df.empty:
            st.info("No source data yet.")
        else:
            st.dataframe(src_df, use_container_width=True, hide_index=True)

    # ---- Article feed -----------------------------------------------------
    st.divider()
    st.markdown("#### Latest Articles")

    articles = list_ipo_news(
        db=db,
        tenant_id=tenant_id,
        days_back=days_view,
        sentiment_filter=sentiment_filter if sentiment_filter != "All" else None,
        search=search.strip() or None,
        company_hint=company_filter.strip() or None,
        limit=80,
    )

    if not articles:
        st.info(
            "No IPO news articles found for the selected filters. "
            "Use the **Refresh IPO News** button above to pull the latest articles."
        )
        return

    view_mode = st.radio(
        "Display", ["Cards", "Table"], horizontal=True,
        key=f"news_view_{context}",
    )

    if view_mode == "Table":
        df = news_to_dataframe(articles)
        if "Published" in df.columns:
            df["Published"] = (
                pd.to_datetime(df["Published"], errors="coerce")
                .dt.strftime("%Y-%m-%d %H:%M")
            )
        if "URL" in df.columns and "Title" in df.columns:
            df["Title"] = df.apply(
                lambda r: (
                    f'<a href="{r["URL"]}" target="_blank">{r["Title"]}</a>'
                    if r.get("URL") else r["Title"]
                ),
                axis=1,
            )
            df = df.drop(columns=["URL"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        for article in articles:
            _render_article_card(article)