from __future__ import annotations

from datetime import datetime, UTC

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


YIELD_SERIES = {
    "3M": "DGS3MO",
    "2Y": "DGS2",
    "5Y": "DGS5",
    "10Y": "DGS10",
    "30Y": "DGS30",
}

CREDIT_SERIES = {
    "HY OAS": "BAMLH0A0HYM2",
    "IG OAS": "BAMLC0A0CM",
}

INFLATION_SERIES = {
    "CPI": "CPIAUCSL",
    "5Y Breakeven": "T5YIE",
    "10Y Breakeven": "T10YIE",
}

YAHOO_YIELD_FALLBACKS = {
    "3M": "^IRX",
    "5Y": "^FVX",
    "10Y": "^TNX",
    "30Y": "^TYX",
}


def _safe_float(value):
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _fmt_pct(value, decimals=2):
    value = _safe_float(value)
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}%"


def _latest_non_null(df, col):
    if df is None or df.empty or col not in df.columns:
        return None
    values = pd.to_numeric(df[col], errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.iloc[-1])


@st.cache_data(ttl=60 * 60, show_spinner=False)
def _load_fred_series(series_id: str) -> pd.DataFrame:
    """Load FRED series with full SSL/network error isolation."""
    empty = pd.DataFrame(columns=["Date", "Value"])
    try:
        import requests
        # Use requests instead of pd.read_csv to control SSL context
        r = requests.get(
            f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
            timeout=10,
            verify=True,
        )
        if r.status_code != 200:
            return empty
        from io import StringIO
        df = pd.read_csv(StringIO(r.text))
        if "observation_date" not in df.columns or series_id not in df.columns:
            return empty
        out = df.rename(columns={"observation_date": "Date", series_id: "Value"})
        out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
        out["Value"] = pd.to_numeric(out["Value"], errors="coerce")
        return out.dropna(subset=["Date", "Value"]).sort_values("Date")
    except Exception:
        return empty


@st.cache_data(ttl=15 * 60, show_spinner=False)
def _load_yahoo_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    """Load Yahoo Finance history with full SSL/network error isolation."""
    empty = pd.DataFrame(columns=["Date", "Close"])
    try:
        # Use a fresh requests session isolated from the DB connection pool
        import requests, urllib.parse
        period_map = {"3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
        days = period_map.get(period, 365)
        import time as _time
        end_ts   = int(_time.time())
        start_ts = end_ts - days * 86400
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
            f"?period1={start_ts}&period2={end_ts}&interval=1d&events=history"
        )
        r = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json",
        }, timeout=10)
        if r.status_code != 200:
            return empty
        data = r.json()
        result = (data.get("chart") or {}).get("result") or []
        if not result:
            return empty
        timestamps = result[0].get("timestamp", [])
        closes     = (result[0].get("indicators") or {}).get("quote", [{}])[0].get("close", [])
        if not timestamps or not closes:
            return empty
        out = pd.DataFrame({
            "Date":  pd.to_datetime(timestamps, unit="s", utc=True),
            "Close": pd.to_numeric(closes, errors="coerce"),
        })
        return out.dropna(subset=["Date", "Close"]).sort_values("Date")
    except Exception:
        return empty


def _yield_from_yahoo(symbol: str):
    hist = _load_yahoo_history(symbol, period="6mo")
    value = _latest_non_null(hist, "Close")
    if value is None:
        return None
    return value / 10.0 if value > 20 else value


def _load_yield_curve():
    rows = []
    source = "FRED"
    for tenor, series_id in YIELD_SERIES.items():
        value = None
        try:
            value = _latest_non_null(_load_fred_series(series_id), "Value")
        except Exception:
            value = None

        if value is None and tenor in YAHOO_YIELD_FALLBACKS:
            source = "Yahoo fallback"
            try:
                value = _yield_from_yahoo(YAHOO_YIELD_FALLBACKS[tenor])
            except Exception:
                value = None

        rows.append({"Tenor": tenor, "Yield": value, "Source": source if value is not None else "Unavailable"})

    return pd.DataFrame(rows)


def _load_fred_metric_map(series_map):
    rows = []
    for label, series_id in series_map.items():
        try:
            df = _load_fred_series(series_id)
            latest = _latest_non_null(df, "Value")
            prev = _latest_non_null(df.iloc[:-21], "Value") if len(df) > 21 else None
            rows.append(
                {
                    "Metric": label,
                    "Value": latest,
                    "Change": latest - prev if latest is not None and prev is not None else None,
                    "Source": "FRED",
                }
            )
        except Exception:
            rows.append({"Metric": label, "Value": None, "Change": None, "Source": "Unavailable"})
    return pd.DataFrame(rows)


def _load_cpi_yoy():
    try:
        cpi = _load_fred_series("CPIAUCSL")
        if cpi.empty or len(cpi) < 13:
            return None
        cpi = cpi.copy()
        cpi["YoY"] = cpi["Value"].pct_change(12) * 100.0
        return _latest_non_null(cpi, "YoY")
    except Exception:
        return None


def _load_vix_term_structure():
    tickers = {
        "VIX": "^VIX",
        "VIX 3M": "^VIX3M",
        "VIX 6M": "^VIX6M",
    }
    rows = []
    for label, symbol in tickers.items():
        try:
            value = _latest_non_null(_load_yahoo_history(symbol, period="3mo"), "Close")
        except Exception:
            value = None
        rows.append({"Contract": label, "Value": value})
    return pd.DataFrame(rows)


def _load_proxy_price_metrics():
    proxies = {
        "HYG": "High Yield ETF",
        "LQD": "Investment Grade ETF",
        "IEF": "7-10Y Treasury ETF",
        "TIP": "TIPS ETF",
        "SPY": "S&P 500 ETF",
        "TLT": "20Y Treasury ETF",
    }
    rows = []
    for symbol, label in proxies.items():
        try:
            hist = _load_yahoo_history(symbol, period="6mo")
            latest = _latest_non_null(hist, "Close")
            prev = _latest_non_null(hist.iloc[:-21], "Close") if len(hist) > 21 else None
            rows.append(
                {
                    "Symbol": symbol,
                    "Proxy": label,
                    "Last": latest,
                    "1M Change": latest / prev - 1.0 if latest is not None and prev not in (None, 0) else None,
                }
            )
        except Exception:
            rows.append({"Symbol": symbol, "Proxy": label, "Last": None, "1M Change": None})
    return pd.DataFrame(rows)


def _macro_regime(yield_df, credit_df, inflation_yoy, vix_df):
    score = 0
    notes = []

    yields = dict(zip(yield_df["Tenor"], yield_df["Yield"])) if not yield_df.empty else {}
    y10 = _safe_float(yields.get("10Y"))
    y2 = _safe_float(yields.get("2Y"))
    y3m = _safe_float(yields.get("3M"))
    curve_10y_2y = y10 - y2 if y10 is not None and y2 is not None else None
    curve_10y_3m = y10 - y3m if y10 is not None and y3m is not None else None

    if curve_10y_2y is not None:
        if curve_10y_2y < 0:
            score -= 1
            notes.append("2s10s curve is inverted")
        elif curve_10y_2y > 0.75:
            score += 1
            notes.append("2s10s curve is positively sloped")

    if inflation_yoy is not None:
        if inflation_yoy > 3.5:
            score -= 1
            notes.append("CPI YoY is elevated")
        elif inflation_yoy < 2.5:
            score += 1
            notes.append("CPI YoY is near target range")

    hy = None
    if not credit_df.empty:
        match = credit_df[credit_df["Metric"] == "HY OAS"]
        if not match.empty:
            hy = _safe_float(match.iloc[0].get("Value"))
    if hy is not None:
        if hy > 5.0:
            score -= 1
            notes.append("high yield spreads are stressed")
        elif hy < 4.0:
            score += 1
            notes.append("high yield spreads are contained")

    vix = None
    if not vix_df.empty:
        match = vix_df[vix_df["Contract"] == "VIX"]
        if not match.empty:
            vix = _safe_float(match.iloc[0].get("Value"))
    if vix is not None:
        if vix > 25:
            score -= 1
            notes.append("VIX is elevated")
        elif vix < 18:
            score += 1
            notes.append("VIX is calm")

    if score >= 2:
        regime = "Risk-On"
    elif score <= -2:
        regime = "Risk-Off"
    else:
        regime = "Mixed"

    return {
        "regime": regime,
        "score": score,
        "notes": "; ".join(notes) if notes else "Macro signals are mixed or partially unavailable.",
        "10Y-2Y": curve_10y_2y,
        "10Y-3M": curve_10y_3m,
    }


def _yield_curve_chart(yield_df):
    fig = go.Figure()
    plot_df = yield_df.dropna(subset=["Yield"])
    fig.add_trace(
        go.Scatter(
            x=plot_df["Tenor"],
            y=plot_df["Yield"],
            mode="lines+markers",
            name="Current Yield",
            line={"color": "#1f77b4", "width": 2.5},
        )
    )
    fig.update_layout(
        title="Treasury Yield Curve",
        height=360,
        margin={"l": 20, "r": 20, "t": 50, "b": 30},
        yaxis_title="Yield %",
        xaxis_title="Tenor",
    )
    return fig


def _bar_chart(df, x_col, y_col, title, y_suffix="", color_positive=True):
    plot_df = df.dropna(subset=[y_col]).copy()
    colors = []
    for value in plot_df[y_col]:
        if color_positive:
            colors.append("#168a55" if value >= 0 else "#b42318")
        else:
            colors.append("#b42318" if value >= 0 else "#168a55")

    fig = go.Figure(
        go.Bar(
            x=plot_df[x_col],
            y=plot_df[y_col],
            marker_color=colors,
            text=[f"{v:.2f}{y_suffix}" for v in plot_df[y_col]],
            textposition="auto",
        )
    )
    fig.update_layout(
        title=title,
        height=330,
        margin={"l": 20, "r": 20, "t": 50, "b": 30},
        yaxis_title=y_suffix.strip() or "Value",
        xaxis_title="",
    )
    return fig



def render_macro_dashboard(db=None):
    """
    Macro Dashboard — all HTTP fetches are deferred behind a button click
    so they never fire during app init / DB connection pool setup.
    """
    st.subheader("🌍 Macro Dashboard")
    st.caption(
        "Yield curve · Credit spreads · Inflation · VIX term structure · "
        "Market proxies · Powered by FRED + Yahoo Finance"
    )

    if not st.session_state.get("macro_loaded", False):
        col_btn, col_note = st.columns([1, 4])
        with col_btn:
            load_btn = st.button(
                "📡 Load Macro Data",
                type="primary",
                key="macro_load_btn",
                use_container_width=True,
            )
        with col_note:
            st.info(
                "Click to load live macro data from FRED and Yahoo Finance. "
                "Loaded on demand to keep app startup fast and avoid SSL conflicts."
            )
        if not load_btn:
            return
        st.session_state["macro_loaded"] = True

    col_ts, col_r = st.columns([5, 1])
    with col_ts:
        st.caption(f"Last loaded: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    with col_r:
        if st.button("↺ Refresh", key="macro_refresh"):
            st.session_state["macro_loaded"] = False
            try:
                _load_fred_series.clear()
                _load_yahoo_history.clear()
            except Exception:
                pass
            st.rerun()

    with st.spinner("Loading macro data…"):
        try:
            yield_df      = _load_yield_curve()
            credit_df     = _load_fred_metric_map(CREDIT_SERIES)
            inflation_df  = _load_fred_metric_map({"5Y Breakeven": "T5YIE", "10Y Breakeven": "T10YIE"})
            inflation_yoy = _load_cpi_yoy()
            fed_df        = _load_fred_metric_map({"Effective Fed Funds": "FEDFUNDS"})
            vix_df        = _load_vix_term_structure()
            proxy_df      = _load_proxy_price_metrics()
            regime        = _macro_regime(yield_df, credit_df, inflation_yoy, vix_df)
        except Exception as e:
            st.error(f"Failed to load macro data: {e}")
            st.session_state["macro_loaded"] = False
            return

    y10    = _safe_float(yield_df.loc[yield_df["Tenor"] == "10Y", "Yield"].iloc[0]) if "10Y" in yield_df["Tenor"].values else None
    hy_oas = _safe_float(credit_df.loc[credit_df["Metric"] == "HY OAS", "Value"].iloc[0]) if "HY OAS" in credit_df["Metric"].values else None
    vix    = _safe_float(vix_df.loc[vix_df["Contract"] == "VIX", "Value"].iloc[0]) if "VIX" in vix_df["Contract"].values else None

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Macro Regime", regime["regime"], f"Score {regime['score']:+.0f}")
    c2.metric("10Y Treasury", _fmt_pct(y10))
    c3.metric("10Y - 2Y", _fmt_pct(regime["10Y-2Y"]))
    c4.metric("HY OAS", _fmt_pct(hy_oas))
    c5.metric("VIX", f"{vix:.2f}" if vix is not None else "N/A")
    st.caption(regime["notes"])

    tab_curve, tab_credit, tab_inflation, tab_vol, tab_proxies = st.tabs(
        ["Yield Curve", "Credit Spreads", "Inflation", "Vol / Fed Path", "Market Proxies"]
    )

    with tab_curve:
        if yield_df["Yield"].notna().any():
            st.plotly_chart(_yield_curve_chart(yield_df), use_container_width=True)
        st.dataframe(
            yield_df.style.format({"Yield": lambda v: "N/A" if pd.isna(v) else f"{v:.2f}%"}),
            use_container_width=True, hide_index=True,
        )

    with tab_credit:
        if credit_df["Value"].notna().any():
            st.plotly_chart(_bar_chart(credit_df, "Metric", "Value", "Credit Spreads", "%", color_positive=False), use_container_width=True)
        st.dataframe(
            credit_df.style.format({
                "Value":  lambda v: "N/A" if pd.isna(v) else f"{v:.2f}%",
                "Change": lambda v: "N/A" if pd.isna(v) else f"{v:+.2f} pts",
            }),
            use_container_width=True, hide_index=True,
        )

    with tab_inflation:
        i1, i2, i3 = st.columns(3)
        i1.metric("CPI YoY", _fmt_pct(inflation_yoy))
        for idx, row in inflation_df.iterrows():
            target = i2 if idx == 0 else i3
            target.metric(row["Metric"], _fmt_pct(row["Value"]))
        if inflation_df["Value"].notna().any():
            st.plotly_chart(_bar_chart(inflation_df, "Metric", "Value", "Inflation Expectations", "%"), use_container_width=True)
        st.dataframe(
            inflation_df.style.format({
                "Value":  lambda v: "N/A" if pd.isna(v) else f"{v:.2f}%",
                "Change": lambda v: "N/A" if pd.isna(v) else f"{v:+.2f} pts",
            }),
            use_container_width=True, hide_index=True,
        )

    with tab_vol:
        fed_proxy_rows = pd.DataFrame([
            {
                "Metric": "Effective Fed Funds",
                "Value": _safe_float(fed_df.iloc[0]["Value"]) if not fed_df.empty else None,
                "Readthrough": "Current policy-rate anchor",
            },
            {"Metric": "10Y - 3M Curve", "Value": regime["10Y-3M"], "Readthrough": "Negative implies restrictive / recessionary pressure"},
            {"Metric": "10Y - 2Y Curve", "Value": regime["10Y-2Y"], "Readthrough": "Positive steepening often supports cyclicals"},
        ])
        if vix_df["Value"].notna().any():
            st.plotly_chart(_bar_chart(vix_df, "Contract", "Value", "VIX Term Structure", ""), use_container_width=True)
        st.dataframe(
            vix_df.style.format({"Value": lambda v: "N/A" if pd.isna(v) else f"{v:.2f}"}),
            use_container_width=True, hide_index=True,
        )
        st.markdown("#### Fed Path Proxies")
        st.dataframe(
            fed_proxy_rows.style.format({"Value": lambda v: "N/A" if pd.isna(v) else f"{v:+.2f} pts"}),
            use_container_width=True, hide_index=True,
        )

    with tab_proxies:
        if proxy_df["1M Change"].notna().any():
            plot_df = proxy_df.copy()
            plot_df["1M Change %"] = plot_df["1M Change"] * 100.0
            st.plotly_chart(_bar_chart(plot_df, "Symbol", "1M Change %", "Macro Proxy 1M Performance", "%"), use_container_width=True)
        st.dataframe(
            proxy_df.style.format({
                "Last":      lambda v: "N/A" if pd.isna(v) else f"{v:,.2f}",
                "1M Change": lambda v: "N/A" if pd.isna(v) else f"{v:+.2%}",
            }),
            use_container_width=True, hide_index=True,
        )