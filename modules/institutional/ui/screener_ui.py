import pandas as pd
import streamlit as st

from modules.analytics.models import AnalyticsSnapshot
from modules.screener.service import run_screener


def _safe_float(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _load_symbol_universe(db, tenant_id: str) -> list[str]:
    rows = (
        db.query(AnalyticsSnapshot.symbol)
        .filter(AnalyticsSnapshot.tenant_id == tenant_id)
        .distinct()
        .all()
    )
    return sorted([r[0] for r in rows if r and r[0]])


def _load_sector_options(db, tenant_id: str) -> list[str]:
    rows = (
        db.query(AnalyticsSnapshot.sector)
        .filter(
            AnalyticsSnapshot.tenant_id == tenant_id,
            AnalyticsSnapshot.sector != None,
        )
        .distinct()
        .all()
    )
    values = sorted({r[0] for r in rows if r and r[0]})
    return values


def _format_results_df(results: list[dict]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)

    rename_map = {
        "symbol": "Symbol",
        "price": "Price",
        "volume": "Volume",
        "sector": "Sector",
        "rating": "Rating",
        "composite": "Composite",
        "confidence": "Confidence",
        "quality": "Quality",
        "growth": "Growth",
        "value": "Value",
        "momentum": "Momentum",
        "risk": "Risk",
        "trend": "Trend",
        "rsi_14": "RSI 14",
        "support": "Support",
        "resistance": "Resistance",
        "pe_ttm": "P/E",
        "ps_ttm": "P/S",
        "ev_ebitda": "EV/EBITDA",
    }
    df = df.rename(columns=rename_map)

    preferred_order = [
        "Symbol",
        "Sector",
        "Rating",
        "Composite",
        "Confidence",
        "Quality",
        "Growth",
        "Value",
        "Momentum",
        "Risk",
        "Price",
        "Volume",
        "Trend",
        "RSI 14",
        "Support",
        "Resistance",
        "P/E",
        "P/S",
        "EV/EBITDA",
    ]

    cols = [c for c in preferred_order if c in df.columns]
    return df[cols]


def _render_top_cards(df: pd.DataFrame):
    if df.empty:
        return

    st.markdown("### Top Picks")

    top = df.head(3).copy()
    cols = st.columns(min(3, len(top)))

    for idx, (_, row) in enumerate(top.iterrows()):
        with cols[idx]:
            st.metric("Symbol", row.get("Symbol", "N/A"))
            st.metric("Composite", row.get("Composite", "N/A"))
            st.metric("Confidence", row.get("Confidence", "N/A"))
            st.caption(f"Sector: {row.get('Sector', 'Unknown')}")
            st.caption(f"Rating: {row.get('Rating', 'N/A')}")


def _render_summary(df: pd.DataFrame):
    if df.empty:
        return

    st.markdown("### Summary")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Matches", len(df))

    with c2:
        avg_comp = pd.to_numeric(df["Composite"], errors="coerce").mean() if "Composite" in df.columns else None
        st.metric("Avg Composite", f"{avg_comp:.2f}" if pd.notna(avg_comp) else "N/A")

    with c3:
        avg_conf = pd.to_numeric(df["Confidence"], errors="coerce").mean() if "Confidence" in df.columns else None
        st.metric("Avg Confidence", f"{avg_conf:.2f}" if pd.notna(avg_conf) else "N/A")

    with c4:
        avg_risk = pd.to_numeric(df["Risk"], errors="coerce").mean() if "Risk" in df.columns else None
        st.metric("Avg Risk", f"{avg_risk:.2f}" if pd.notna(avg_risk) else "N/A")


def render_screener(db, user: dict):
    tenant_id = user["tenant_id"]

    st.subheader("Institutional Screener")
    st.caption("Analytics-ranked screener using latest stored snapshots and current market data.")

    symbols = _load_symbol_universe(db, tenant_id)
    sectors = _load_sector_options(db, tenant_id)

    if not symbols:
        st.warning("No analytics-backed symbols found. Run analytics first.")
        return

    with st.expander("Filters", expanded=True):
        r1c1, r1c2, r1c3 = st.columns(3)
        with r1c1:
            min_price = st.number_input("Min Price", min_value=0.0, value=0.0, step=1.0)
            min_volume = st.number_input("Min Volume", min_value=0.0, value=0.0, step=100000.0)
            result_limit = st.selectbox("Max Results", [25, 50, 100, 250, 500], index=2)

        with r1c2:
            min_comp = st.slider("Min Composite", 0, 100, 60)
            min_conf = st.slider("Min Confidence", 0, 100, 60)
            max_risk = st.slider("Max Risk", 0, 100, 100)

        with r1c3:
            min_quality = st.slider("Min Quality", 0, 100, 0)
            min_growth = st.slider("Min Growth", 0, 100, 0)
            min_value = st.slider("Min Value", 0, 100, 0)
            min_momentum = st.slider("Min Momentum", 0, 100, 0)

        r2c1, r2c2 = st.columns(2)
        with r2c1:
            sector = st.selectbox("Sector", ["All"] + sectors, index=0)
            sector = None if sector == "All" else sector

        with r2c2:
            rating_in = st.multiselect(
                "Ratings",
                ["Buy", "Hold", "Sell", "N/A"],
                default=["Buy", "Hold", "Sell", "N/A"],
            )
            rating_in = rating_in if rating_in else None

    run = st.button("Run Screener", type="primary")

    if not run:
        return

    with st.spinner("Running screener..."):
        results = run_screener(
            db=db,
            tenant_id=tenant_id,
            symbols=symbols,
            min_price=float(min_price) if min_price > 0 else None,
            min_volume=float(min_volume) if min_volume > 0 else None,
            min_composite=float(min_comp) if min_comp > 0 else None,
            min_confidence=float(min_conf) if min_conf > 0 else None,
            min_quality=float(min_quality) if min_quality > 0 else None,
            min_growth=float(min_growth) if min_growth > 0 else None,
            min_value=float(min_value) if min_value > 0 else None,
            min_momentum=float(min_momentum) if min_momentum > 0 else None,
            max_risk=float(max_risk) if max_risk < 100 else None,
            sector=sector,
            rating_in=rating_in,
            limit=int(result_limit),
        )

    if not results:
        st.warning("No matches. Lower thresholds or run analytics for more symbols.")
        return

    df = _format_results_df(results)

    _render_summary(df)
    _render_top_cards(df)

    st.markdown("### Results")
    st.dataframe(df, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download CSV",
        data=csv,
        file_name="screener_results.csv",
        mime="text/csv",
    )