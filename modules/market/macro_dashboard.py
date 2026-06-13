from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
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

FRED_TIMEOUT_SECONDS = 8
YAHOO_TIMEOUT_SECONDS = 8
MAX_WORKERS = 6


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


def _empty_fred_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["Date", "Value"])


def _empty_yahoo_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["Date", "Close"])


def _fetch_fred_series_raw(series_id: str) -> pd.DataFrame:
    """
    Raw FRED fetch used inside worker threads.

    Important:
    This function is intentionally NOT decorated with st.cache_data because
    Streamlit cache calls from worker threads can produce incomplete / empty
    results in deployed apps.
    """
    empty = _empty_fred_df()

    try:
        import requests
        from io import StringIO

        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 StockApp",
                "Accept": "text/csv,text/plain,*/*",
            },
            timeout=FRED_TIMEOUT_SECONDS,
        )

        if response.status_code != 200 or not response.text:
            return empty

        df = pd.read_csv(StringIO(response.text))

        if "observation_date" not in df.columns or series_id not in df.columns:
            return empty

        out = df.rename(columns={"observation_date": "Date", series_id: "Value"})
        out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
        out["Value"] = pd.to_numeric(out["Value"], errors="coerce")

        return out.dropna(subset=["Date", "Value"]).sort_values("Date")

    except Exception:
        return empty


def _fetch_yahoo_history_raw(symbol: str, period: str = "1y") -> pd.DataFrame:
    """
    Raw Yahoo chart fetch used inside worker threads.
    """
    empty = _empty_yahoo_df()

    try:
        import requests
        import time as _time
        import urllib.parse

        period_map = {
            "3mo": 90,
            "6mo": 180,
            "1y": 365,
            "2y": 730,
        }

        days = period_map.get(period, 365)
        end_ts = int(_time.time())
        start_ts = end_ts - days * 86400

        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{urllib.parse.quote(symbol)}"
            f"?period1={start_ts}&period2={end_ts}&interval=1d&events=history"
        )

        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "application/json",
            },
            timeout=YAHOO_TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            return empty

        data = response.json()
        result = (data.get("chart") or {}).get("result") or []

        if not result:
            return empty

        first = result[0]
        timestamps = first.get("timestamp") or []
        quote = ((first.get("indicators") or {}).get("quote") or [{}])[0]
        closes = quote.get("close") or []

        if not timestamps or not closes:
            return empty

        out = pd.DataFrame({
            "Date": pd.to_datetime(timestamps, unit="s", utc=True),
            "Close": pd.to_numeric(closes, errors="coerce"),
        })

        return out.dropna(subset=["Date", "Close"]).sort_values("Date")

    except Exception:
        return empty


def _parallel_load_fred(series_ids: list[str]) -> dict[str, pd.DataFrame]:
    unique_ids = list(dict.fromkeys(series_ids))
    results: dict[str, pd.DataFrame] = {}

    if not unique_ids:
        return results

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(unique_ids))) as executor:
        future_map = {
            executor.submit(_fetch_fred_series_raw, series_id): series_id
            for series_id in unique_ids
        }

        for future in as_completed(future_map):
            series_id = future_map[future]
            try:
                results[series_id] = future.result()
            except Exception:
                results[series_id] = _empty_fred_df()

    return results


def _parallel_load_yahoo(requests_: list[tuple[str, str]]) -> dict[tuple[str, str], pd.DataFrame]:
    unique_requests = list(dict.fromkeys(requests_))
    results: dict[tuple[str, str], pd.DataFrame] = {}

    if not unique_requests:
        return results

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(unique_requests))) as executor:
        future_map = {
            executor.submit(_fetch_yahoo_history_raw, symbol, period): (symbol, period)
            for symbol, period in unique_requests
        }

        for future in as_completed(future_map):
            key = future_map[future]
            try:
                results[key] = future.result()
            except Exception:
                results[key] = _empty_yahoo_df()

    return results


def _yield_from_yahoo_history(hist: pd.DataFrame):
    value = _latest_non_null(hist, "Close")
    if value is None:
        return None
    return value / 10.0 if value > 20 else value


def _build_yield_curve(
    fred_data: dict[str, pd.DataFrame],
    yahoo_data: dict[tuple[str, str], pd.DataFrame],
) -> pd.DataFrame:
    rows = []

    for tenor, series_id in YIELD_SERIES.items():
        value = _latest_non_null(fred_data.get(series_id), "Value")
        source = "FRED"

        if value is None and tenor in YAHOO_YIELD_FALLBACKS:
            fallback_symbol = YAHOO_YIELD_FALLBACKS[tenor]
            value = _yield_from_yahoo_history(
                yahoo_data.get((fallback_symbol, "6mo"), _empty_yahoo_df())
            )
            source = "Yahoo fallback"

        rows.append({
            "Tenor": tenor,
            "Yield": value,
            "Source": source if value is not None else "Unavailable",
        })

    return pd.DataFrame(rows)


def _build_fred_metric_map(
    series_map: dict[str, str],
    fred_data: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows = []

    for label, series_id in series_map.items():
        df = fred_data.get(series_id, _empty_fred_df())
        latest = _latest_non_null(df, "Value")
        prev = _latest_non_null(df.iloc[:-21], "Value") if len(df) > 21 else None

        rows.append({
            "Metric": label,
            "Value": latest,
            "Change": latest - prev if latest is not None and prev is not None else None,
            "Source": "FRED" if latest is not None else "Unavailable",
        })

    return pd.DataFrame(rows)


def _build_cpi_yoy(fred_data: dict[str, pd.DataFrame]):
    cpi = fred_data.get("CPIAUCSL", _empty_fred_df())

    if cpi.empty or len(cpi) < 13:
        return None

    cpi = cpi.copy()
    cpi["YoY"] = cpi["Value"].pct_change(12) * 100.0

    return _latest_non_null(cpi, "YoY")


def _build_vix_term_structure(yahoo_data: dict[tuple[str, str], pd.DataFrame]) -> pd.DataFrame:
    tickers = {
        "VIX": "^VIX",
        "VIX 3M": "^VIX3M",
        "VIX 6M": "^VIX6M",
    }

    rows = []

    for label, symbol in tickers.items():
        value = _latest_non_null(
            yahoo_data.get((symbol, "3mo"), _empty_yahoo_df()),
            "Close",
        )
        rows.append({"Contract": label, "Value": value})

    return pd.DataFrame(rows)


def _build_proxy_price_metrics(yahoo_data: dict[tuple[str, str], pd.DataFrame]) -> pd.DataFrame:
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
        hist = yahoo_data.get((symbol, "6mo"), _empty_yahoo_df())
        latest = _latest_non_null(hist, "Close")
        prev = _latest_non_null(hist.iloc[:-21], "Close") if len(hist) > 21 else None

        rows.append({
            "Symbol": symbol,
            "Proxy": label,
            "Last": latest,
            "1M Change": latest / prev - 1.0 if latest is not None and prev not in (None, 0) else None,
        })

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


@st.cache_data(ttl=30 * 60, show_spinner=False)
def _load_macro_snapshot() -> dict:
    """
    Load all macro data concurrently and cache the completed snapshot.

    The raw worker functions are intentionally not Streamlit cached.
    """
    fred_ids = list(YIELD_SERIES.values())
    fred_ids += list(CREDIT_SERIES.values())
    fred_ids += ["T5YIE", "T10YIE", "CPIAUCSL", "FEDFUNDS"]

    yahoo_requests = [
        ("^IRX", "6mo"),
        ("^FVX", "6mo"),
        ("^TNX", "6mo"),
        ("^TYX", "6mo"),
        ("^VIX", "3mo"),
        ("^VIX3M", "3mo"),
        ("^VIX6M", "3mo"),
        ("HYG", "6mo"),
        ("LQD", "6mo"),
        ("IEF", "6mo"),
        ("TIP", "6mo"),
        ("SPY", "6mo"),
        ("TLT", "6mo"),
    ]

    fred_data = _parallel_load_fred(fred_ids)
    yahoo_data = _parallel_load_yahoo(yahoo_requests)

    yield_df = _build_yield_curve(fred_data, yahoo_data)
    credit_df = _build_fred_metric_map(CREDIT_SERIES, fred_data)
    inflation_df = _build_fred_metric_map(
        {
            "5Y Breakeven": "T5YIE",
            "10Y Breakeven": "T10YIE",
        },
        fred_data,
    )
    inflation_yoy = _build_cpi_yoy(fred_data)
    fed_df = _build_fred_metric_map({"Effective Fed Funds": "FEDFUNDS"}, fred_data)
    vix_df = _build_vix_term_structure(yahoo_data)
    proxy_df = _build_proxy_price_metrics(yahoo_data)
    regime = _macro_regime(yield_df, credit_df, inflation_yoy, vix_df)

    return {
        "loaded_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "yield_df": yield_df,
        "credit_df": credit_df,
        "inflation_df": inflation_df,
        "inflation_yoy": inflation_yoy,
        "fed_df": fed_df,
        "vix_df": vix_df,
        "proxy_df": proxy_df,
        "regime": regime,
        "fred_loaded": {
            key: not value.empty
            for key, value in fred_data.items()
        },
        "yahoo_loaded": {
            f"{key[0]}:{key[1]}": not value.empty
            for key, value in yahoo_data.items()
        },
    }


def render_macro_dashboard(db=None):
    st.subheader("🌍 Macro Dashboard")
    st.caption(
        "Yield curve · Credit spreads · Inflation · VIX term structure · "
        "Market proxies · Powered by FRED + Yahoo Finance"
    )

    if "macro_snapshot" not in st.session_state:
        st.session_state["macro_snapshot"] = None

    col_btn, col_note, col_refresh = st.columns([1, 4, 1])

    with col_btn:
        load_btn = st.button(
            "📡 Load Macro Data",
            type="primary",
            key="macro_load_btn",
            use_container_width=True,
        )

    with col_note:
        st.info(
            "Click to load macro data. Data is fetched on demand, cached, "
            "and loaded concurrently to keep the rest of the app fast."
        )

    with col_refresh:
        refresh_btn = st.button(
            "↺ Refresh",
            key="macro_refresh",
            use_container_width=True,
        )

    if refresh_btn:
        st.session_state["macro_snapshot"] = None
        try:
            _load_macro_snapshot.clear()
        except Exception:
            pass
        st.rerun()

    if load_btn:
        with st.spinner("Loading macro data…"):
            st.session_state["macro_snapshot"] = _load_macro_snapshot()
        st.rerun()

    snapshot = st.session_state.get("macro_snapshot")

    if not snapshot:
        return

    st.caption(f"Last loaded: {snapshot.get('loaded_at', 'N/A')}")

    yield_df = snapshot["yield_df"]
    credit_df = snapshot["credit_df"]
    inflation_df = snapshot["inflation_df"]
    inflation_yoy = snapshot["inflation_yoy"]
    fed_df = snapshot["fed_df"]
    vix_df = snapshot["vix_df"]
    proxy_df = snapshot["proxy_df"]
    regime = snapshot["regime"]

    # continue with metrics/tabs here

    tab_curve, tab_credit, tab_inflation, tab_vol, tab_proxies = st.tabs(
        ["Yield Curve", "Credit Spreads", "Inflation", "Vol / Fed Path", "Market Proxies"]
    )

    with tab_curve:

        if yield_df["Yield"].notna().any():
            st.plotly_chart(_yield_curve_chart(yield_df), use_container_width=True)

        display_df = yield_df.copy()

        if "Yield" in display_df.columns:
            display_df["Yield"] = display_df["Yield"].apply(
                lambda v: "N/A" if pd.isna(v) else f"{v:.2f}%"
            )

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
        )

    with tab_credit:
        st.write("TAB CREDIT START")
        if "Value" in credit_df.columns and credit_df["Value"].notna().any():
            st.plotly_chart(
                _bar_chart(
                    credit_df,
                    "Metric",
                    "Value",
                    "Credit Spreads",
                    "%",
                    color_positive=False,
                ),
                use_container_width=True,
            )

        display_df = credit_df.copy()

        if "Value" in display_df.columns:
            display_df["Value"] = display_df["Value"].apply(
                lambda v: "N/A" if pd.isna(v) else f"{float(v):.2f}%"
            )

        if "Change" in display_df.columns:
            display_df["Change"] = display_df["Change"].apply(
                lambda v: "N/A" if pd.isna(v) else f"{float(v):+.2f} pts"
            )

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
        )

    with tab_inflation:

        i1, i2, i3 = st.columns(3)
        i1.metric("CPI YoY", _fmt_pct(inflation_yoy))

        for idx, row in inflation_df.iterrows():
            target = i2 if idx == 0 else i3
            target.metric(row["Metric"], _fmt_pct(row["Value"]))

        if "Value" in inflation_df.columns and inflation_df["Value"].notna().any():
            st.plotly_chart(
                _bar_chart(
                    inflation_df,
                    "Metric",
                    "Value",
                    "Inflation Expectations",
                    "%",
                ),
                use_container_width=True,
            )

        display_df = inflation_df.copy()

        if "Value" in display_df.columns:
            display_df["Value"] = display_df["Value"].apply(
                lambda v: "N/A" if pd.isna(v) else f"{float(v):.2f}%"
            )

        if "Change" in display_df.columns:
            display_df["Change"] = display_df["Change"].apply(
                lambda v: "N/A" if pd.isna(v) else f"{float(v):+.2f} pts"
            )

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
        )

    with tab_vol:

        fed_value = None
        if fed_df is not None and not fed_df.empty and "Value" in fed_df.columns:
            fed_value = _safe_float(fed_df.iloc[0]["Value"])

        fed_proxy_rows = pd.DataFrame([
            {
                "Metric": "Effective Fed Funds",
                "Value": fed_value,
                "Readthrough": "Current policy-rate anchor",
            },
            {
                "Metric": "10Y - 3M Curve",
                "Value": regime.get("10Y-3M"),
                "Readthrough": "Negative implies restrictive / recessionary pressure",
            },
            {
                "Metric": "10Y - 2Y Curve",
                "Value": regime.get("10Y-2Y"),
                "Readthrough": "Positive steepening often supports cyclicals",
            },
        ])

        if "Value" in vix_df.columns and vix_df["Value"].notna().any():
            st.plotly_chart(
                _bar_chart(
                    vix_df,
                    "Contract",
                    "Value",
                    "VIX Term Structure",
                    "",
                ),
                use_container_width=True,
            )

        display_df = vix_df.copy()

        if "Value" in display_df.columns:
            display_df["Value"] = display_df["Value"].apply(
                lambda v: "N/A" if pd.isna(v) else f"{float(v):.2f}"
            )

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### Fed Path Proxies")

        display_df = fed_proxy_rows.copy()

        if "Value" in display_df.columns:
            display_df["Value"] = display_df["Value"].apply(
                lambda v: "N/A" if pd.isna(v) else f"{float(v):+.2f} pts"
            )

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
        )

    with tab_proxies:
        if "1M Change" in proxy_df.columns and proxy_df["1M Change"].notna().any():
            plot_df = proxy_df.copy()
            plot_df["1M Change %"] = plot_df["1M Change"] * 100.0

            st.plotly_chart(
                _bar_chart(
                    plot_df,
                    "Symbol",
                    "1M Change %",
                    "Macro Proxy 1M Performance",
                    "%",
                ),
                use_container_width=True,
            )

        display_df = proxy_df.copy()

        if "Last" in display_df.columns:
            display_df["Last"] = display_df["Last"].apply(
                lambda v: "N/A" if pd.isna(v) else f"{float(v):,.2f}"
            )

        if "1M Change" in display_df.columns:
            display_df["1M Change"] = display_df["1M Change"].apply(
                lambda v: "N/A" if pd.isna(v) else f"{float(v):+.2%}"
            )

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Macro data load diagnostics", expanded=False):
        st.write("FRED series loaded")
        st.json(snapshot.get("fred_loaded", {}))
        st.write("Yahoo series loaded")
        st.json(snapshot.get("yahoo_loaded", {}))
