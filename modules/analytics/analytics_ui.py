import streamlit as st
import pandas as pd
import yfinance as yf

from modules.institutional.fundamentals import ingest_massive_fundamentals
from modules.institutional.financial_history import ingest_massive_financial_history, list_financial_periods
from modules.analytics.runner import run_full_analytics
from modules.analytics.models import AnalyticsSnapshot
from modules.market_data.news_service import (
    get_finnhub_news,
    get_finnhub_sentiment,
)




def _score_pe(pe):
    if pe is None:
        return None
    score = (40.0 - float(pe)) / (40.0 - 12.0)
    return max(min(score, 1.0), 0.0) * 100.0


def _score_ps(ps):
    if ps is None:
        return None
    score = (15.0 - float(ps)) / (15.0 - 3.0)
    return max(min(score, 1.0), 0.0) * 100.0


def _score_ev_ebitda(ev):
    if ev is None:
        return None
    score = (30.0 - float(ev)) / (30.0 - 8.0)
    return max(min(score, 1.0), 0.0) * 100.0


def _to_float(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _first_number(*values):
    for v in values:
        n = _to_float(v)
        if n is not None:
            return n
    return None


def _get_info_safe(ticker):
    try:
        info = ticker.get_info() or {}
        if info:
            return info
    except Exception:
        pass

    try:
        info = ticker.info or {}
        if info:
            return info
    except Exception:
        pass

    return {}


def _fetch_isolated_valuation(symbol: str):
    import yfinance as yf

    try:
        ticker = yf.Ticker(symbol)

        info = ticker.info or {}

        market_cap = info.get("marketCap")

        # -----------------------------------
        # Revenue
        # -----------------------------------
        revenue = None
        try:
            fin = ticker.financials
            if fin is not None and not fin.empty and "Total Revenue" in fin.index:
                revenue = float(fin.loc["Total Revenue"].dropna().iloc[0])
        except Exception:
            pass

        # -----------------------------------
        # Net Income
        # -----------------------------------
        net_income = None
        try:
            if fin is not None and "Net Income" in fin.index:
                net_income = float(fin.loc["Net Income"].dropna().iloc[0])
        except Exception:
            pass

        # -----------------------------------
        # EBITDA
        # -----------------------------------
        ebitda = None
        try:
            if fin is not None and "EBITDA" in fin.index:
                ebitda = float(fin.loc["EBITDA"].dropna().iloc[0])
        except Exception:
            pass

        # -----------------------------------
        # Enterprise Value
        # -----------------------------------
        ev = info.get("enterpriseValue")

        # -----------------------------------
        # COMPUTE RATIOS
        # -----------------------------------
        pe = None
        if market_cap and net_income and net_income != 0:
            pe = market_cap / net_income

        ps = None
        if market_cap and revenue and revenue != 0:
            ps = market_cap / revenue

        ev_ebitda = None
        if ev and ebitda and ebitda != 0:
            ev_ebitda = ev / ebitda

        return {
            "pe_ttm": pe,
            "ps_ttm": ps,
            "ev_ebitda": ev_ebitda,
        }

    except Exception as e:
        print("VALUATION BUILD ERROR", symbol, e)
        return {
            "pe_ttm": None,
            "ps_ttm": None,
            "ev_ebitda": None,
        }


def _latest_snapshot(db, tenant_id, symbol):
    return (
        db.query(AnalyticsSnapshot)
        .filter(
            AnalyticsSnapshot.tenant_id == tenant_id,
            AnalyticsSnapshot.symbol == symbol,
        )
        .order_by(AnalyticsSnapshot.asof.desc())
        .first()
    )


def _delete_snapshot(db, tenant_id, symbol):
    try:
        (
            db.query(AnalyticsSnapshot)
            .filter(
                AnalyticsSnapshot.tenant_id == tenant_id,
                AnalyticsSnapshot.symbol == symbol,
            )
            .delete()
        )
        db.commit()
    except Exception:
        db.rollback()


def _apply_isolated_valuation_fix(db, tenant_id, symbol):
    latest = _latest_snapshot(db, tenant_id, symbol)
    if latest is None:
        return None

    vals = _fetch_isolated_valuation(symbol)

    updated = False

    if vals["pe_ttm"] is not None:
        latest.pe_ttm = vals["pe_ttm"]
        updated = True

    if vals["ps_ttm"] is not None:
        latest.ps_ttm = vals["ps_ttm"]
        updated = True

    if vals["ev_ebitda"] is not None:
        latest.ev_ebitda = vals["ev_ebitda"]
        updated = True

    if updated:
        try:
            db.commit()
        except Exception:
            db.rollback()

    return _latest_snapshot(db, tenant_id, symbol)


def render_analytics(db, user: dict):
    st.error("DEBUG: NEW ANALYTICS UI LOADED")
    st.error("🔥 RENDER_ANALYTICS IS EXECUTING")
    tenant_id = user["tenant_id"]

    st.subheader("Analytics Engine")

    symbol = st.text_input("Symbol", value="AAPL").upper().strip()

    force_rebuild = st.checkbox(
        "Force Rebuild Analytics Snapshot",
        value=True,
        key="analytics_force_rebuild",
    )

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
                    db,
                    tenant_id,
                    symbol,
                    period_type="annual",
                    limit=50,
                )
                st.success(f"Ingested {n} financial periods.")
            except Exception as e:
                st.error(f"Financial history ingestion failed: {e}")

    with c3:
        if st.button("Run Analytics", type="primary"):
            try:
                try:
                    st.cache_data.clear()
                except Exception:
                    pass

                if force_rebuild:
                    _delete_snapshot(db, tenant_id, symbol)

                try:
                    ingest_massive_fundamentals(db, tenant_id, symbol)
                except Exception as e:
                    print("FUNDAMENTALS REFRESH WARNING", symbol, e)

                row = run_full_analytics(db, tenant_id, symbol)

                if row is None:
                    st.warning(
                        f"Analytics returned no result for {symbol}. "
                        "Possible causes: insufficient price history, symbol skipped by classifier, "
                        "or missing market data."
                    )
                else:
                    latest_fixed = _apply_isolated_valuation_fix(db, tenant_id, symbol)

                    if latest_fixed is None:
                        st.warning("Analytics stored, but latest snapshot could not be reloaded.")
                    else:
                        st.success(
                            f"Stored. Rating: {latest_fixed.rating} | "
                            f"Composite: {getattr(latest_fixed, 'composite_score', None)}"
                        )

            except Exception as e:
                st.error(f"Analytics run failed: {e}")

    st.divider()

    latest = _latest_snapshot(db, tenant_id, symbol)

    if not latest:
        st.info("No analytics stored yet for this symbol.")
    else:


        t1, t2, t3, t4, t5, t6 = st.columns(6)

        t1.metric(
            "Composite",
            f"{getattr(latest,'composite_score',None):.1f}"
            if getattr(latest, 'composite_score', None) is not None
            else "—",
        )

        t2.metric(
            "Quality",
            f"{getattr(latest,'quality_score',None):.1f}"
            if getattr(latest, 'quality_score', None) is not None
            else "—",
        )

        t3.metric(
            "Growth",
            f"{getattr(latest,'growth_score',None):.1f}"
            if getattr(latest, 'growth_score', None) is not None
            else "—",
        )

        t4.metric(
            "Value",
            f"{getattr(latest,'value_score',None):.1f}"
            if getattr(latest, 'value_score', None) is not None
            else "—",
        )

        t5.metric(
            "Momentum",
            f"{getattr(latest,'momentum_score',None):.1f}"
            if getattr(latest, 'momentum_score', None) is not None
            else "—",
        )

        t6.metric(
            "Confidence",
            f"{getattr(latest,'confidence_score',None):.0f}"
            if getattr(latest, 'confidence_score', None) is not None
            else "—",
        )

        st.markdown(f"### Overall Rating: **{latest.rating}**")
        st.caption(latest.rating_rationale or "")

    st.divider()

    st.subheader("Value Factor Breakdown")

    pe = getattr(latest, "pe_ttm", None)
    ps = getattr(latest, "ps_ttm", None)
    ev = getattr(latest, "ev_ebitda", None)

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
        "Revenue CAGR (3y)": latest.revenue_cagr_3y,
        "Gross Margin": latest.gross_margin,
        "Operating Margin": latest.op_margin,
        "FCF Margin": latest.fcf_margin,
        "P/E (TTM)": latest.pe_ttm,
        "P/S (TTM)": latest.ps_ttm,
        "EV/EBITDA": latest.ev_ebitda,
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
    else:
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





