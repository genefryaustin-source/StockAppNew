import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from modules.analytics.models import AnalyticsSnapshot
from modules.market_data.service import get_price_history
from modules.institutional.financial_history import list_financial_periods
from modules.institutional.earnings import list_upcoming

from modules.institutional.watchlists import (
    list_watchlists,
    add_symbol,
)
from modules.analytics.rankings import rank_symbols

from modules.market_data.news_service import (
    get_finnhub_news,
    get_finnhub_sentiment,
)
def _safe_float(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _latest_snapshot(db, tenant_id, symbol):
    return (
        db.query(AnalyticsSnapshot)
        .filter(
            AnalyticsSnapshot.tenant_id == tenant_id,
            AnalyticsSnapshot.symbol == symbol,
            AnalyticsSnapshot.asof != None,
        )
        .order_by(AnalyticsSnapshot.asof.desc())
        .first()
    )


def _metric_str(val, pct=False, decimals=2):
    if val is None:
        return "N/A"
    if pct:
        return f"{val * 100:.{decimals}f}%"
    return f"{val:,.{decimals}f}"


def _render_price_chart(df, symbol):
    if df is None or df.empty:
        st.info("No price history available.")
        return

    plot_df = df.copy()
    if "Date" not in plot_df.columns or "Close" not in plot_df.columns:
        st.info("Price data missing required columns.")
        return

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(plot_df["Date"], plot_df["Close"])
    ax.set_title(f"{symbol} Price History")
    ax.set_xlabel("Date")
    ax.set_ylabel("Close")
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)


def _render_snapshot(snapshot):
    if not snapshot:
        st.warning("No analytics snapshot found for this symbol.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rating", getattr(snapshot, "rating", None) or "N/A")
    c2.metric("Composite", _metric_str(_safe_float(getattr(snapshot, "composite_score", None))))
    c3.metric("Confidence", _metric_str(_safe_float(getattr(snapshot, "confidence_score", None))))
    c4.metric("Sector", getattr(snapshot, "sector", None) or "Unknown")

    st.markdown("### Factor Scores")
    f1, f2, f3, f4, f5 = st.columns(5)
    f1.metric("Quality", _metric_str(_safe_float(getattr(snapshot, "quality_score", None))))
    f2.metric("Growth", _metric_str(_safe_float(getattr(snapshot, "growth_score", None))))
    f3.metric("Value", _metric_str(_safe_float(getattr(snapshot, "value_score", None))))
    f4.metric("Momentum", _metric_str(_safe_float(getattr(snapshot, "momentum_score", None))))
    f5.metric("Risk", _metric_str(_safe_float(getattr(snapshot, "risk_score", None))))

    st.markdown("### Core Analytics")
    df = pd.DataFrame([{
        "Revenue CAGR": _metric_str(_safe_float(getattr(snapshot, "revenue_cagr", None)), pct=True),
        "Gross Margin": _metric_str(_safe_float(getattr(snapshot, "gross_margin", None)), pct=True),
        "Operating Margin": _metric_str(_safe_float(getattr(snapshot, "operating_margin", None)), pct=True),
        "FCF Margin": _metric_str(_safe_float(getattr(snapshot, "fcf_margin", None)), pct=True),
        "P/E": _metric_str(_safe_float(getattr(snapshot, "pe_ttm", None))),
        "P/S": _metric_str(_safe_float(getattr(snapshot, "ps_ttm", None))),
        "EV/EBITDA": _metric_str(_safe_float(getattr(snapshot, "ev_ebitda", None))),
        "Trend": getattr(snapshot, "trend", None) or "N/A",
        "RSI 14": _metric_str(_safe_float(getattr(snapshot, "rsi_14", None))),
        "SMA 50": _metric_str(_safe_float(getattr(snapshot, "sma_50", None))),
        "SMA 200": _metric_str(_safe_float(getattr(snapshot, "sma_200", None))),
        "Support": _metric_str(_safe_float(getattr(snapshot, "support", None))),
        "Resistance": _metric_str(_safe_float(getattr(snapshot, "resistance", None))),
        "Vol 20D": _metric_str(_safe_float(getattr(snapshot, "vol_20d", None)), pct=True),
        "Max DD 1Y": _metric_str(_safe_float(getattr(snapshot, "max_drawdown_1y", None)), pct=True),
        "Risk Score": _metric_str(_safe_float(getattr(snapshot, "risk_score", None))),
    }])
    st.dataframe(df, use_container_width=True, hide_index=True)

    rationale = getattr(snapshot, "rating_rationale", None)
    if rationale:
        st.markdown("### Rationale")
        st.write(rationale)


def _render_financials(db, tenant_id, symbol):
    st.markdown("### Financial History")
    try:
        rows = list_financial_periods(
            db=db,
            tenant_id=tenant_id,
            symbol=symbol,
            period_type="annual",
            limit=10,
        )
    except Exception as e:
        st.info(f"Financial history unavailable: {e}")
        return

    if not rows:
        st.info("No financial history found.")
        return

    data = []
    for r in rows:
        data.append({
            "Period End": getattr(r, "period_end", None),
            "FY": getattr(r, "fiscal_year", None),
            "FP": getattr(r, "fiscal_period", None),
            "Revenue": getattr(r, "revenue", None),
            "Gross Profit": getattr(r, "gross_profit", None),
            "Operating Income": getattr(r, "operating_income", None),
            "Net Income": getattr(r, "net_income", None),
            "EPS Basic": getattr(r, "eps_basic", None),
            "EPS Diluted": getattr(r, "eps_diluted", None),
            "EBITDA": getattr(r, "ebitda", None),
            "OCF": getattr(r, "operating_cash_flow", None),
            "Capex": getattr(r, "capex", None),
            "FCF": getattr(r, "free_cash_flow", None),
            "Cash": getattr(r, "cash", None),
            "Debt": getattr(r, "total_debt", None),
            "Source": getattr(r, "source", None),
        })

    st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)


def _render_earnings(db, tenant_id, symbol):
    st.markdown("### Earnings History")
    try:
        events = list_upcoming(db, tenant_id)
    except Exception as e:
        st.info(f"Earnings unavailable: {e}")
        return

    events = [e for e in events if getattr(e, "symbol", None) == symbol]

    if not events:
        st.info("No earnings events found.")
        return

    rows = []
    for e in events[:20]:
        eps = (
            getattr(e, "eps_actual", None)
            or getattr(e, "eps_est", None)
            or getattr(e, "eps_estimate", None)
        )
        rev = (
            getattr(e, "rev_actual", None)
            or getattr(e, "revenue_actual", None)
            or getattr(e, "rev_est", None)
            or getattr(e, "revenue_estimate", None)
        )
        rows.append({
            "Event Date": getattr(e, "event_date", None) or getattr(e, "earnings_date", None),
            "Time": getattr(e, "time_of_day", None),
            "EPS": eps,
            "Revenue": rev,
            "Source": getattr(e, "source", None),
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_watchlist_actions(db, tenant_id, symbol):
    st.markdown("### Watchlist Actions")
    try:
        watchlists = list_watchlists(db, tenant_id)
    except Exception as e:
        st.info(f"Watchlists unavailable: {e}")
        return

    if not watchlists:
        st.info("No watchlists available.")
        return

    wl_map = {w.name: w.id for w in watchlists}
    chosen = st.selectbox(
        "Add symbol to watchlist",
        list(wl_map.keys()),
        key=f"dashboard_watchlist_select_{symbol}",
    )

    if st.button("Add To Watchlist", key=f"dashboard_add_watchlist_{symbol}"):
        add_symbol(db, tenant_id, wl_map[chosen], symbol)
        st.success(f"{symbol} added to {chosen}")


def _render_ranking_context(db, tenant_id, symbol):
    st.markdown("### Ranking Context")
    try:
        rows = rank_symbols(
            db=db,
            tenant_id=tenant_id,
            symbols=[symbol],
            min_confidence=0.0,
            require_composite=False,
        )
    except Exception as e:
        st.info(f"Ranking context unavailable: {e}")
        return

    if not rows:
        st.info("No ranking context available.")
        return

    r = rows[0]
    df = pd.DataFrame([{
        "Symbol": r.symbol,
        "Sector": r.sector,
        "Rating": r.rating,
        "Composite": r.composite,
        "Confidence": r.confidence,
        "Quality": r.quality,
        "Growth": r.growth,
        "Value": r.value,
        "Momentum": r.momentum,
        "Risk": r.risk,
    }])
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_stock_dashboard(db, user):
    tenant_id = user["tenant_id"]

    st.subheader("Stock Research Dashboard")

    symbol = st.text_input("Ticker", value="AAPL", key="stock_dashboard_symbol").upper().strip()

    if not symbol:
        st.info("Enter a ticker.")
        return

    snapshot = _latest_snapshot(db, tenant_id, symbol)

    c1, c2 = st.columns([2, 1])

    with c1:
        st.markdown(f"## {symbol}")
        _render_snapshot(snapshot)

    with c2:
        _render_ranking_context(db, tenant_id, symbol)
        _render_watchlist_actions(db, tenant_id, symbol)

    st.divider()

    st.markdown("### Price Chart")
    try:
        px = get_price_history(db, symbol, period="1y", interval="1d")
        _render_price_chart(px, symbol)
    except Exception as e:
        st.info(f"Price history unavailable: {e}")

    st.divider()
    _render_financials(db, tenant_id, symbol)

    st.divider()
    _render_earnings(db, tenant_id, symbol)

    # --------------------------------------------------
    # 📰 NEWS & SENTIMENT (FULL IMPLEMENTATION)
    # --------------------------------------------------

    from modules.market_data.news_service import (
        get_finnhub_news,
        get_finnhub_sentiment,
    )

    st.divider()
    st.subheader("📰 News & Sentiment")

    # --------------------------------------------------
    # 🔧 DERIVED SENTIMENT (FALLBACK ENGINE)
    # --------------------------------------------------
    def derive_sentiment_from_news(news_items):
        if not news_items:
            return None

        bullish_words = [
            "beat", "growth", "strong", "upgrade", "outperform",
            "record", "surge", "expansion", "positive"
        ]

        bearish_words = [
            "miss", "weak", "downgrade", "decline", "drop",
            "cut", "risk", "concern", "negative"
        ]

        bullish = 0
        bearish = 0

        for n in news_items:
            text = f"{n.get('headline', '')} {n.get('summary', '')}".lower()

            if any(w in text for w in bullish_words):
                bullish += 1

            if any(w in text for w in bearish_words):
                bearish += 1

        total = bullish + bearish

        if total == 0:
            return {
                "bullish": 0,
                "bearish": 0,
                "score": 0.0
            }

        score = (bullish - bearish) / total

        return {
            "bullish": bullish,
            "bearish": bearish,
            "score": score
        }

    # --------------------------------------------------
    # 🧠 FETCH DATA
    # --------------------------------------------------
    news_items = get_finnhub_news(symbol)
    sentiment = get_finnhub_sentiment(symbol)

    # Fallback if Finnhub sentiment is empty
    if not sentiment:
        sentiment = derive_sentiment_from_news(news_items)

    # --------------------------------------------------
    # 📊 SENTIMENT DISPLAY
    # --------------------------------------------------
    if sentiment:
        col1, col2, col3 = st.columns(3)

        col1.metric("Bullish", sentiment.get("bullish", 0))
        col2.metric("Bearish", sentiment.get("bearish", 0))
        col3.metric("Score", f"{sentiment.get('score', 0):.2f}")

    else:
        st.info("No sentiment data available.")

    # --------------------------------------------------
    # 📰 NEWS DISPLAY
    # --------------------------------------------------
    if news_items:
        for n in news_items[:5]:
            st.markdown(f"""
    ### {n.get("headline", "No Title")}

    {(n.get("summary") or "")[:250]}

    [Read more]({n.get("url", "#")})  
    *Source: {n.get("source", "Unknown")}*
    """)
            st.divider()

    else:
        st.warning("No news available.")