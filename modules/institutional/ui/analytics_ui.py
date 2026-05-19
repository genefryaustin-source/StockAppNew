import streamlit as st
import pandas as pd
import yfinance as yf

from modules.institutional.fundamentals import ingest_massive_fundamentals
from modules.institutional.financial_history import (
    ingest_massive_financial_history,
    list_financial_periods,
)
from modules.analytics.runner import run_full_analytics
from modules.analytics.models import AnalyticsSnapshot
from modules.market_data.news_service import (
    get_finnhub_news,
    get_finnhub_sentiment,
)

def _score_pe(pe):
    if pe is None:
        return None
    try:
        score = (40.0 - float(pe)) / (40.0 - 12.0)
        return max(min(score, 1.0), 0.0) * 100.0
    except Exception:
        return None


def _score_ps(ps):
    if ps is None:
        return None
    try:
        score = (15.0 - float(ps)) / (15.0 - 3.0)
        return max(min(score, 1.0), 0.0) * 100.0
    except Exception:
        return None


def _score_ev_ebitda(ev):
    if ev is None:
        return None
    try:
        score = (30.0 - float(ev)) / (30.0 - 8.0)
        return max(min(score, 1.0), 0.0) * 100.0
    except Exception:
        return None


def _safe_num(x):
    try:
        if x is None:
            return None
        v = float(x)
        if pd.isna(v):
            return None
        return v
    except Exception:
        return None


def _coalesce(*vals):
    for v in vals:
        if v is None:
            continue
        return v
    return None


def _normalize_valuation_fields(fundamentals):
    """
    Minimal UI-side normalization only for missing valuation fields.
    This does not change runner behavior and only helps rendering.
    """
    if not isinstance(fundamentals, dict):
        return {}

    valuation = fundamentals.get("valuation", {}) or {}

    return {
        **fundamentals,
        "pe_ttm": _safe_num(
            fundamentals.get("pe_ttm")
            or fundamentals.get("peRatioTTM")
            or fundamentals.get("pe_ratio")
            or valuation.get("pe")
        ),
        "ps_ttm": _safe_num(
            fundamentals.get("ps_ttm")
            or fundamentals.get("priceToSalesTTM")
            or fundamentals.get("ps_ratio")
            or valuation.get("ps")
        ),
        "ev_ebitda": _safe_num(
            fundamentals.get("ev_ebitda")
            or fundamentals.get("enterpriseToEbitda")
            or fundamentals.get("evToEbitda")
            or valuation.get("ev_ebitda")
        ),
    }


def _load_fundamentals_for_ui(db, tenant_id, symbol):
    """
    Safe loader for UI fallback.
    Supports both possible ingest signatures:
      - ingest_massive_fundamentals(db, tenant_id, symbol)
      - ingest_massive_fundamentals(symbol)
    """
    raw = None

    try:
        raw = ingest_massive_fundamentals(db, tenant_id, symbol)
    except TypeError:
        try:
            raw = ingest_massive_fundamentals(symbol)
        except Exception:
            raw = None
    except Exception:
        raw = None

    return _normalize_valuation_fields(raw)


def _compute_valuation_fallback(symbol):
    """
    Last-resort UI fallback for valuation display only.
    Does not affect stored analytics.
    """
    try:
        tk = yf.Ticker(symbol)

        info = {}
        try:
            info = tk.info or {}
        except Exception:
            pass

        market_cap = _safe_num(info.get("marketCap"))
        enterprise_value = _safe_num(info.get("enterpriseValue"))

        revenue = None
        net_income = None
        ebitda = None

        try:
            fin = tk.financials
            if fin is not None and not fin.empty:
                if "Total Revenue" in fin.index:
                    vals = fin.loc["Total Revenue"].dropna()
                    if not vals.empty:
                        revenue = _safe_num(vals.iloc[0])

                if "Net Income" in fin.index:
                    vals = fin.loc["Net Income"].dropna()
                    if not vals.empty:
                        net_income = _safe_num(vals.iloc[0])

                if "EBITDA" in fin.index:
                    vals = fin.loc["EBITDA"].dropna()
                    if not vals.empty:
                        ebitda = _safe_num(vals.iloc[0])
        except Exception:
            pass

        if revenue is None or net_income is None or ebitda is None:
            try:
                q = tk.quarterly_financials
                if q is not None and not q.empty:
                    if revenue is None and "Total Revenue" in q.index:
                        vals = q.loc["Total Revenue"].dropna()
                        if not vals.empty:
                            revenue = _safe_num(vals.iloc[0])
                            if revenue is not None:
                                revenue *= 4

                    if net_income is None and "Net Income" in q.index:
                        vals = q.loc["Net Income"].dropna()
                        if not vals.empty:
                            net_income = _safe_num(vals.iloc[0])
                            if net_income is not None:
                                net_income *= 4

                    if ebitda is None and "EBITDA" in q.index:
                        vals = q.loc["EBITDA"].dropna()
                        if not vals.empty:
                            ebitda = _safe_num(vals.iloc[0])
                            if ebitda is not None:
                                ebitda *= 4
            except Exception:
                pass

        pe = None
        if market_cap is not None and net_income not in (None, 0):
            pe = market_cap / net_income

        ps = None
        if market_cap is not None and revenue not in (None, 0):
            ps = market_cap / revenue

        ev_ebitda = None
        base_ev = enterprise_value if enterprise_value is not None else market_cap
        if base_ev is not None and ebitda not in (None, 0):
            ev_ebitda = base_ev / ebitda

        return pe, ps, ev_ebitda

    except Exception:
        return None, None, None


def render_analytics(db, user: dict):
    tenant_id = user["tenant_id"]

    st.subheader("Analytics Engine")

    symbol = st.text_input("Symbol", value="AAPL").upper().strip()

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("Refresh Fundamentals", type="primary"):
            try:
                ingest_massive_fundamentals(db, tenant_id, symbol)
                st.success("Fundamentals refreshed.")
            except Exception as e:
                st.error(f"Fundamentals ingestion failed: {e}")

    with c2:
        if st.button("Ingest Financial History (Annual)", type="primary"):
            try:
                n = ingest_massive_financial_history(
                    db, tenant_id, symbol, period_type="annual", limit=50
                )
                st.success(f"Ingested {n} financial periods.")
            except Exception as e:
                st.error(f"Financial history ingestion failed: {e}")

    with c3:
        if st.button("Run Analytics", type="primary"):
            try:
                row = run_full_analytics(db, tenant_id, symbol)

                if row is None:
                    st.warning(
                        f"Analytics returned no result for {symbol}. "
                        "Possible causes: insufficient price history, symbol skipped by classifier, "
                        "or missing market data."
                    )
                else:
                    st.success(
                        f"Stored. Rating: {row.rating} | Composite: {getattr(row, 'composite_score', None)}"
                    )

            except Exception as e:
                st.error(f"Analytics run failed: {e}")

    st.divider()

    latest = (
        db.query(AnalyticsSnapshot)
        .filter(
            AnalyticsSnapshot.tenant_id == tenant_id,
            AnalyticsSnapshot.symbol == symbol,
        )
        .order_by(AnalyticsSnapshot.asof.desc())
        .first()
    )

    if not latest:
        st.info("No analytics stored yet for this symbol.")
        return

    # Top tiles
    t1, t2, t3, t4, t5, t6 = st.columns(6)

    t1.metric(
        "Composite",
        f"{getattr(latest, 'composite_score', None):.1f}"
        if getattr(latest, 'composite_score', None) is not None
        else "—",
    )

    t2.metric(
        "Quality",
        f"{getattr(latest, 'quality_score', None):.1f}"
        if getattr(latest, 'quality_score', None) is not None
        else "—",
    )

    t3.metric(
        "Growth",
        f"{getattr(latest, 'growth_score', None):.1f}"
        if getattr(latest, 'growth_score', None) is not None
        else "—",
    )

    t4.metric(
        "Value",
        f"{getattr(latest, 'value_score', None):.1f}"
        if getattr(latest, 'value_score', None) is not None
        else "—",
    )

    t5.metric(
        "Momentum",
        f"{getattr(latest, 'momentum_score', None):.1f}"
        if getattr(latest, 'momentum_score', None) is not None
        else "—",
    )

    t6.metric(
        "Confidence",
        f"{getattr(latest, 'confidence_score', None):.0f}"
        if getattr(latest, 'confidence_score', None) is not None
        else "—",
    )

    st.markdown(f"### Overall Rating: **{latest.rating}**")
    st.caption(latest.rating_rationale or "")

    st.divider()

    # Value breakdown table
    st.subheader("Value Factor Breakdown")
    
    snap_pe = _safe_num(getattr(latest, "pe_ttm", None))
    snap_ps = _safe_num(getattr(latest, "ps_ttm", None))
    snap_ev = _safe_num(getattr(latest, "ev_ebitda", None))

    fundamentals = {}
    if snap_pe is None or snap_ps is None or snap_ev is None:
        fundamentals = _load_fundamentals_for_ui(db, tenant_id, symbol)

    fund_pe = _safe_num(fundamentals.get("pe_ttm")) if fundamentals else None
    fund_ps = _safe_num(fundamentals.get("ps_ttm")) if fundamentals else None
    fund_ev = _safe_num(fundamentals.get("ev_ebitda")) if fundamentals else None

    yf_pe = yf_ps = yf_ev = None
    if (
        _coalesce(snap_pe, fund_pe) is None
        or _coalesce(snap_ps, fund_ps) is None
        or _coalesce(snap_ev, fund_ev) is None
    ):
        yf_pe, yf_ps, yf_ev = _compute_valuation_fallback(symbol)

    pe = _coalesce(snap_pe, fund_pe, _safe_num(yf_pe))
    ps = _coalesce(snap_ps, fund_ps, _safe_num(yf_ps))
    ev = _coalesce(snap_ev, fund_ev, _safe_num(yf_ev))
  
    df_value = pd.DataFrame(
        [
            {"Metric": "P/E", "Raw": pe, "Score": _score_pe(pe)},
            {"Metric": "P/S", "Raw": ps, "Score": _score_ps(ps)},
            {"Metric": "EV / EBITDA", "Raw": ev, "Score": _score_ev_ebitda(ev)},
        ]
    )

    df_value["Raw"] = df_value["Raw"].apply(
        lambda x: f"{x:,.2f}" if isinstance(x, (int, float)) else "—"
    )

    df_value["Score"] = df_value["Score"].apply(
        lambda x: f"{x:,.1f}" if isinstance(x, (int, float)) else "—"
    )

    st.dataframe(df_value, use_container_width=True, hide_index=True)

    st.divider()

    metrics = {
        "Sector": getattr(latest, "sector", None) or "Unknown",
        "Revenue CAGR (3y)": latest.revenue_cagr,
        "Gross Margin": latest.gross_margin,
        "Operating Margin": latest.operating_margin,
        "FCF Margin": latest.fcf_margin,
        "P/E (TTM)": pe,
        "P/S (TTM)": ps,
        "EV/EBITDA": ev,
        "Trend": latest.trend,
        "RSI(14)": latest.rsi_14,
        "SMA(50)": getattr(latest, "sma_50", None),
        "SMA(200)": getattr(latest, "sma_200", None),
        "Support": latest.support,
        "Resistance": latest.resistance,
        "Vol(20d ann.)": latest.vol_20d,
        "Max Drawdown (1y)": latest.max_drawdown_1y,
        "Risk Score (0-100)": latest.risk_score,
        "Composite Score (0-100)": getattr(latest, "composite_score", None),
        "Confidence Score (0-100)": getattr(latest, "confidence_score", None),
        
    }

    st.json(metrics)

    st.divider()
    st.subheader("Financial History (Annual)")

    rows = list_financial_periods(db, tenant_id, symbol, period_type="annual", limit=10)

    if not rows:
        st.info("No financial history stored yet.")
        return

    hist = []

    for r in rows:
        hist.append(
            {
                "Period End": r.period_end,
                "Revenue": r.revenue,
                "Net Income": r.net_income,
                "EPS (Diluted)": r.eps_diluted,
                "FCF": r.free_cash_flow,
            }
        )

    st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True)

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