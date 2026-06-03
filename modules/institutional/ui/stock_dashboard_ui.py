import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go

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
from modules.valuation import build_dcf_base_inputs, compute_dcf_valuation


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


def _money_str(val, decimals=1):
    if val is None:
        return "N/A"
    abs_val = abs(val)
    if abs_val >= 1_000_000_000:
        return f"${val / 1_000_000_000:,.{decimals}f}B"
    if abs_val >= 1_000_000:
        return f"${val / 1_000_000:,.{decimals}f}M"
    return f"${val:,.0f}"


def _latest_close(price_df):
    try:
        if price_df is None or price_df.empty or "Close" not in price_df.columns:
            return None
        close = price_df["Close"].dropna()
        if close.empty:
            return None
        return float(close.iloc[-1])
    except Exception:
        return None


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


def _prepare_price_df(df):
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    if "Date" not in out.columns:
        return pd.DataFrame()

    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out = out.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    return out.dropna(subset=["Close"])


def _resample_to_weekly(df):
    daily = _prepare_price_df(df)
    required = {"Date", "Open", "High", "Low", "Close"}
    if daily.empty or not required.issubset(daily.columns):
        return pd.DataFrame()

    volume = daily["Volume"] if "Volume" in daily.columns else 0
    indexed = daily.assign(Volume=volume).set_index("Date")
    weekly = indexed.resample("W-FRI").agg(
        {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }
    )
    weekly = weekly.dropna(subset=["Open", "High", "Low", "Close"]).reset_index()
    return weekly


def _period_returns(df, freq):
    price_df = _prepare_price_df(df)
    if price_df.empty or "Date" not in price_df.columns:
        return pd.DataFrame()

    indexed = price_df.set_index("Date").sort_index()
    grouped = indexed.resample(freq).agg({"Close": ["first", "last"]})
    grouped.columns = ["First", "Last"]
    grouped = grouped.dropna()
    grouped["Return"] = grouped["Last"] / grouped["First"] - 1.0
    grouped = grouped.reset_index()
    grouped["Year"] = grouped["Date"].dt.year
    grouped["Month"] = grouped["Date"].dt.month
    grouped["Month Name"] = grouped["Date"].dt.strftime("%b")
    grouped["Quarter"] = "Q" + grouped["Date"].dt.quarter.astype(str)
    iso = grouped["Date"].dt.isocalendar()
    grouped["Week"] = iso.week.astype(int)
    return grouped


def _seasonality_summary(period_df, group_col, ordered_labels=None):
    if period_df.empty or group_col not in period_df.columns:
        return pd.DataFrame()

    summary = (
        period_df.groupby(group_col)["Return"]
        .agg(
            Average="mean",
            Median="median",
            WinRate=lambda vals: (vals > 0).mean(),
            Observations="count",
            Best="max",
            Worst="min",
        )
        .reset_index()
    )

    if ordered_labels:
        summary[group_col] = pd.Categorical(summary[group_col], categories=ordered_labels, ordered=True)
        summary = summary.sort_values(group_col)
    else:
        summary = summary.sort_values(group_col)

    return summary


def _seasonality_bar(summary_df, x_col, title, color_col="Average"):
    fig = go.Figure()
    colors = [
        "#168a55" if val >= 0 else "#b42318"
        for val in summary_df[color_col].fillna(0.0)
    ]
    fig.add_trace(
        go.Bar(
            x=summary_df[x_col].astype(str),
            y=summary_df[color_col] * 100.0,
            marker_color=colors,
            name="Average return",
            customdata=summary_df[["WinRate", "Observations"]].values,
            hovertemplate=(
                "%{x}<br>Average: %{y:.2f}%"
                "<br>Win rate: %{customdata[0]:.0%}"
                "<br>Observations: %{customdata[1]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_hline(y=0, line_color="#667085", line_width=1)
    fig.update_layout(
        title=title,
        height=360,
        margin={"l": 20, "r": 20, "t": 50, "b": 30},
        yaxis_title="Average Return",
        xaxis_title="",
    )
    return fig


def _render_seasonality_charts(db, symbol):
    st.markdown("### Seasonality Charts")

    c1, c2 = st.columns([1, 3])
    with c1:
        lookback = st.selectbox(
            "Seasonality lookback",
            ["1y", "2y", "5y"],
            index=2,
            key=f"seasonality_lookback_{symbol}",
        )
    with c2:
        st.caption("Historical tendencies are calculated from daily price history for the selected lookback.")

    try:
        daily_df = _prepare_price_df(get_price_history(db, symbol, period=lookback, interval="1d"))
    except Exception as e:
        st.info(f"Seasonality data unavailable: {e}")
        return

    if daily_df.empty or len(daily_df) < 60:
        st.info("Not enough daily history to calculate useful seasonality.")
        return

    monthly = _period_returns(daily_df, "ME")
    quarterly = _period_returns(daily_df, "QE")
    weekly = _period_returns(daily_df, "W-FRI")

    month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    quarter_order = ["Q1", "Q2", "Q3", "Q4"]

    month_summary = _seasonality_summary(monthly, "Month Name", month_order)
    quarter_summary = _seasonality_summary(quarterly, "Quarter", quarter_order)
    week_summary = _seasonality_summary(weekly, "Week")

    if month_summary.empty:
        st.info("Monthly seasonality could not be calculated from the available history.")
        return

    best_month = month_summary.sort_values("Average", ascending=False).iloc[0]
    worst_month = month_summary.sort_values("Average", ascending=True).iloc[0]
    best_quarter = quarter_summary.sort_values("Average", ascending=False).iloc[0] if not quarter_summary.empty else None

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Best Month",
        str(best_month["Month Name"]),
        f"{best_month['Average'] * 100:+.1f}% avg",
    )
    m2.metric(
        "Worst Month",
        str(worst_month["Month Name"]),
        f"{worst_month['Average'] * 100:+.1f}% avg",
    )
    if best_quarter is not None:
        m3.metric(
            "Best Quarter",
            str(best_quarter["Quarter"]),
            f"{best_quarter['Average'] * 100:+.1f}% avg",
        )
    m4.metric("History", f"{daily_df['Date'].dt.year.nunique()} years")

    chart_tabs = st.tabs(["Monthly", "Quarterly", "Week Of Year", "Year / Month Heatmap"])
    with chart_tabs[0]:
        st.plotly_chart(
            _seasonality_bar(month_summary, "Month Name", f"{symbol} Average Return By Month"),
            use_container_width=True,
        )
        st.dataframe(
            month_summary.style.format(
                {
                    "Average": "{:+.2%}",
                    "Median": "{:+.2%}",
                    "WinRate": "{:.0%}",
                    "Best": "{:+.2%}",
                    "Worst": "{:+.2%}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    with chart_tabs[1]:
        if quarter_summary.empty:
            st.info("Quarterly seasonality unavailable.")
        else:
            st.plotly_chart(
                _seasonality_bar(quarter_summary, "Quarter", f"{symbol} Average Return By Quarter"),
                use_container_width=True,
            )
            st.dataframe(
                quarter_summary.style.format(
                    {
                        "Average": "{:+.2%}",
                        "Median": "{:+.2%}",
                        "WinRate": "{:.0%}",
                        "Best": "{:+.2%}",
                        "Worst": "{:+.2%}",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

    with chart_tabs[2]:
        if week_summary.empty:
            st.info("Weekly seasonality unavailable.")
        else:
            top_weeks = week_summary.sort_values("Average", ascending=False).head(8)
            bottom_weeks = week_summary.sort_values("Average", ascending=True).head(8)
            week_view = pd.concat(
                [
                    top_weeks.assign(Bucket="Strongest Weeks"),
                    bottom_weeks.assign(Bucket="Weakest Weeks"),
                ],
                ignore_index=True,
            )
            fig = _seasonality_bar(week_summary, "Week", f"{symbol} Average Return By ISO Week")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(
                week_view[["Bucket", "Week", "Average", "WinRate", "Observations", "Best", "Worst"]].style.format(
                    {
                        "Average": "{:+.2%}",
                        "WinRate": "{:.0%}",
                        "Best": "{:+.2%}",
                        "Worst": "{:+.2%}",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

    with chart_tabs[3]:
        heatmap_df = monthly.pivot_table(index="Year", columns="Month Name", values="Return", aggfunc="mean")
        heatmap_df = heatmap_df.reindex(columns=month_order)
        fig = go.Figure(
            data=go.Heatmap(
                z=heatmap_df.values * 100.0,
                x=heatmap_df.columns.tolist(),
                y=heatmap_df.index.astype(str).tolist(),
                colorscale=[
                    [0.0, "#b42318"],
                    [0.5, "#ffffff"],
                    [1.0, "#168a55"],
                ],
                zmid=0,
                colorbar={"title": "Return %"},
                hovertemplate="%{y} %{x}<br>Return: %{z:.2f}%<extra></extra>",
            )
        )
        fig.update_layout(
            title=f"{symbol} Monthly Return Heatmap",
            height=420,
            margin={"l": 20, "r": 20, "t": 50, "b": 30},
        )
        st.plotly_chart(fig, use_container_width=True)


def _higher_timeframe_levels(df, label, lookback):
    price_df = _prepare_price_df(df)
    if price_df.empty or not {"High", "Low", "Close"}.issubset(price_df.columns):
        return []

    reference = price_df.iloc[-2] if len(price_df) >= 2 else price_df.iloc[-1]
    recent = price_df.tail(min(len(price_df), lookback))

    levels = [
        {
            "Label": f"{label} Prev High",
            "Price": _safe_float(reference["High"]),
            "Type": "Resistance",
            "Source": label,
        },
        {
            "Label": f"{label} Prev Low",
            "Price": _safe_float(reference["Low"]),
            "Type": "Support",
            "Source": label,
        },
        {
            "Label": f"{label} Support",
            "Price": _safe_float(recent["Low"].min()),
            "Type": "Support",
            "Source": label,
        },
        {
            "Label": f"{label} Resistance",
            "Price": _safe_float(recent["High"].max()),
            "Type": "Resistance",
            "Source": label,
        },
    ]

    clean = []
    seen = set()
    for level in levels:
        price = level["Price"]
        if price is None:
            continue
        key = (level["Label"], round(price, 4))
        if key in seen:
            continue
        seen.add(key)
        clean.append(level)
    return clean


def _snapshot_levels(snapshot):
    if not snapshot:
        return []

    levels = []
    support = _safe_float(getattr(snapshot, "support", None))
    resistance = _safe_float(getattr(snapshot, "resistance", None))
    if support is not None:
        levels.append(
            {
                "Label": "Analytics Support",
                "Price": support,
                "Type": "Support",
                "Source": "Stored Analytics",
            }
        )
    if resistance is not None:
        levels.append(
            {
                "Label": "Analytics Resistance",
                "Price": resistance,
                "Type": "Resistance",
                "Source": "Stored Analytics",
            }
        )
    return levels


def _add_level_lines(fig, levels):
    colors = {
        "Support": "#168a55",
        "Resistance": "#b42318",
    }
    dash_by_source = {
        "Daily": "dash",
        "Weekly": "dot",
        "Stored Analytics": "longdash",
    }

    for level in levels:
        price = _safe_float(level.get("Price"))
        if price is None:
            continue
        fig.add_hline(
            y=price,
            line_width=1.4,
            line_dash=dash_by_source.get(level.get("Source"), "dash"),
            line_color=colors.get(level.get("Type"), "#667085"),
            annotation_text=f"{level.get('Label')} ${price:,.2f}",
            annotation_position="right",
            annotation_font_size=11,
        )


def _pct_diff(a, b):
    try:
        if a in (None, 0) or b is None:
            return None
        return abs(float(a) - float(b)) / abs(float(a))
    except Exception:
        return None


def _fit_line(points):
    clean = [(float(x), float(y)) for x, y in points if x is not None and y is not None]
    if len(clean) < 2:
        return None

    n = len(clean)
    sx = sum(x for x, _ in clean)
    sy = sum(y for _, y in clean)
    sxx = sum(x * x for x, _ in clean)
    sxy = sum(x * y for x, y in clean)
    denom = n * sxx - sx * sx
    if denom == 0:
        return None

    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


def _line_price(line, idx):
    if line is None:
        return None
    slope, intercept = line
    return slope * idx + intercept


def _swing_points(df, length=4):
    price_df = _prepare_price_df(df)
    if price_df.empty or not {"High", "Low"}.issubset(price_df.columns):
        return []

    highs = price_df["High"].tolist()
    lows = price_df["Low"].tolist()
    swings = []
    for idx in range(length, len(price_df) - length):
        high_window = highs[idx - length: idx + length + 1]
        low_window = lows[idx - length: idx + length + 1]
        if highs[idx] == max(high_window):
            swings.append(
                {
                    "kind": "high",
                    "idx": idx,
                    "date": price_df.iloc[idx]["Date"],
                    "price": float(highs[idx]),
                }
            )
        if lows[idx] == min(low_window):
            swings.append(
                {
                    "kind": "low",
                    "idx": idx,
                    "date": price_df.iloc[idx]["Date"],
                    "price": float(lows[idx]),
                }
            )
    return sorted(swings, key=lambda row: row["idx"])


def _pattern_record(name, direction, confidence, points, notes, key_level=None, lines=None):
    return {
        "Pattern": name,
        "Direction": direction,
        "Confidence": max(0.0, min(float(confidence), 1.0)),
        "Start": points[0]["date"] if points else None,
        "End": points[-1]["date"] if points else None,
        "Key Level": key_level,
        "Notes": notes,
        "points": points,
        "lines": lines or [],
    }


def _detect_head_shoulders(price_df, swings):
    patterns = []
    recent = [s for s in swings if s["idx"] >= max(0, len(price_df) - 140)]

    for i in range(len(recent) - 4):
        seq = recent[i:i + 5]
        kinds = [s["kind"] for s in seq]
        if kinds == ["high", "low", "high", "low", "high"]:
            left, neck_a, head, neck_b, right = seq
            shoulders_close = (_pct_diff(left["price"], right["price"]) or 1) <= 0.08
            head_clear = head["price"] > max(left["price"], right["price"]) * 1.025
            neck_close = (_pct_diff(neck_a["price"], neck_b["price"]) or 1) <= 0.12
            if shoulders_close and head_clear and neck_close:
                neckline = (neck_a["price"] + neck_b["price"]) / 2
                confidence = 0.62
                confidence += min((head["price"] / max(left["price"], right["price"]) - 1) * 2.0, 0.2)
                confidence += 0.1 if neck_close else 0.0
                patterns.append(
                    _pattern_record(
                        "Head & Shoulders",
                        "Bearish",
                        confidence,
                        [left, neck_a, head, neck_b, right],
                        "Three-peak reversal candidate with a defined neckline.",
                        neckline,
                    )
                )

        if kinds == ["low", "high", "low", "high", "low"]:
            left, neck_a, head, neck_b, right = seq
            shoulders_close = (_pct_diff(left["price"], right["price"]) or 1) <= 0.08
            head_clear = head["price"] < min(left["price"], right["price"]) * 0.975
            neck_close = (_pct_diff(neck_a["price"], neck_b["price"]) or 1) <= 0.12
            if shoulders_close and head_clear and neck_close:
                neckline = (neck_a["price"] + neck_b["price"]) / 2
                confidence = 0.62
                confidence += min((min(left["price"], right["price"]) / head["price"] - 1) * 2.0, 0.2)
                confidence += 0.1 if neck_close else 0.0
                patterns.append(
                    _pattern_record(
                        "Inverse Head & Shoulders",
                        "Bullish",
                        confidence,
                        [left, neck_a, head, neck_b, right],
                        "Three-trough reversal candidate with a defined neckline.",
                        neckline,
                    )
                )
    return patterns[-2:]


def _detect_cup_handle(price_df):
    price_df = _prepare_price_df(price_df)
    if len(price_df) < 60:
        return []

    window = price_df.tail(min(len(price_df), 120)).reset_index(drop=True)
    close = window["Close"]
    split = max(20, int(len(window) * 0.45))
    left_idx = int(close.iloc[:split].idxmax())
    trough_idx = int(close.iloc[left_idx:].idxmin())
    right_slice = close.iloc[trough_idx:]
    if right_slice.empty:
        return []

    right_idx = int(right_slice.idxmax())
    if not (left_idx < trough_idx < right_idx):
        return []

    left_rim = float(close.iloc[left_idx])
    trough = float(close.iloc[trough_idx])
    right_rim = float(close.iloc[right_idx])
    rim = (left_rim + right_rim) / 2
    depth = (rim - trough) / rim if rim else 0
    rim_match = (_pct_diff(left_rim, right_rim) or 1) <= 0.10
    recovered = right_rim >= left_rim * 0.90

    handle_df = window.iloc[right_idx:].copy()
    if len(handle_df) < 5:
        return []

    handle_low_idx = int(handle_df["Low"].idxmin())
    handle_low = float(window.iloc[handle_low_idx]["Low"])
    handle_pullback = (right_rim - handle_low) / right_rim if right_rim else 1
    handle_ok = 0.02 <= handle_pullback <= 0.18

    if not (0.12 <= depth <= 0.55 and rim_match and recovered and handle_ok):
        return []

    points = [
        {"kind": "high", "idx": int(window.iloc[left_idx].name), "date": window.iloc[left_idx]["Date"], "price": left_rim},
        {"kind": "low", "idx": int(window.iloc[trough_idx].name), "date": window.iloc[trough_idx]["Date"], "price": trough},
        {"kind": "high", "idx": int(window.iloc[right_idx].name), "date": window.iloc[right_idx]["Date"], "price": right_rim},
        {"kind": "low", "idx": int(window.iloc[handle_low_idx].name), "date": window.iloc[handle_low_idx]["Date"], "price": handle_low},
        {"kind": "close", "idx": int(window.iloc[-1].name), "date": window.iloc[-1]["Date"], "price": float(window.iloc[-1]["Close"])},
    ]
    confidence = 0.58 + min(depth, 0.25) + (0.1 if rim_match else 0.0)
    return [
        _pattern_record(
            "Cup & Handle",
            "Bullish",
            confidence,
            points,
            "Rounded base with a controlled handle pullback below the rim.",
            max(left_rim, right_rim),
        )
    ]


def _detect_flag(price_df):
    price_df = _prepare_price_df(price_df)
    if len(price_df) < 35:
        return []

    window = price_df.tail(min(len(price_df), 80)).reset_index(drop=True)
    close = window["Close"]
    consolidation = window.tail(18)
    impulse = window.iloc[-38:-18] if len(window) >= 38 else window.iloc[: max(1, len(window) - 18)]
    if len(impulse) < 8 or len(consolidation) < 10:
        return []

    impulse_return = float(impulse["Close"].iloc[-1] / impulse["Close"].iloc[0] - 1.0)
    cons_return = float(consolidation["Close"].iloc[-1] / consolidation["Close"].iloc[0] - 1.0)
    cons_range = float((consolidation["High"].max() - consolidation["Low"].min()) / consolidation["Close"].mean())

    patterns = []
    if impulse_return > 0.06 and -0.08 <= cons_return <= 0.02 and cons_range <= 0.16:
        points = [
            {"kind": "low", "idx": int(impulse.index[0]), "date": impulse.iloc[0]["Date"], "price": float(impulse.iloc[0]["Low"])},
            {"kind": "high", "idx": int(impulse.index[-1]), "date": impulse.iloc[-1]["Date"], "price": float(impulse.iloc[-1]["High"])},
            {"kind": "low", "idx": int(consolidation.index[-1]), "date": consolidation.iloc[-1]["Date"], "price": float(consolidation.iloc[-1]["Low"])},
        ]
        patterns.append(
            _pattern_record(
                "Bull Flag",
                "Bullish",
                0.58 + min(impulse_return, 0.18),
                points,
                "Sharp advance followed by a tight sideways-to-down consolidation.",
                float(consolidation["High"].max()),
            )
        )

    if impulse_return < -0.06 and -0.02 <= cons_return <= 0.08 and cons_range <= 0.16:
        points = [
            {"kind": "high", "idx": int(impulse.index[0]), "date": impulse.iloc[0]["Date"], "price": float(impulse.iloc[0]["High"])},
            {"kind": "low", "idx": int(impulse.index[-1]), "date": impulse.iloc[-1]["Date"], "price": float(impulse.iloc[-1]["Low"])},
            {"kind": "high", "idx": int(consolidation.index[-1]), "date": consolidation.iloc[-1]["Date"], "price": float(consolidation.iloc[-1]["High"])},
        ]
        patterns.append(
            _pattern_record(
                "Bear Flag",
                "Bearish",
                0.58 + min(abs(impulse_return), 0.18),
                points,
                "Sharp decline followed by a tight sideways-to-up consolidation.",
                float(consolidation["Low"].min()),
            )
        )
    return patterns


def _detect_triangle_wedge(price_df, swings):
    price_df = _prepare_price_df(price_df)
    if len(price_df) < 35:
        return []

    start_idx = max(0, len(price_df) - 80)
    highs = [s for s in swings if s["kind"] == "high" and s["idx"] >= start_idx][-5:]
    lows = [s for s in swings if s["kind"] == "low" and s["idx"] >= start_idx][-5:]
    if len(highs) < 2 or len(lows) < 2:
        return []

    high_line = _fit_line([(s["idx"], s["price"]) for s in highs])
    low_line = _fit_line([(s["idx"], s["price"]) for s in lows])
    if high_line is None or low_line is None:
        return []

    high_slope = high_line[0]
    low_slope = low_line[0]
    current = len(price_df) - 1
    start_gap = (_line_price(high_line, start_idx) or 0) - (_line_price(low_line, start_idx) or 0)
    end_gap = (_line_price(high_line, current) or 0) - (_line_price(low_line, current) or 0)
    avg_price = float(price_df["Close"].tail(80).mean())
    flat_threshold = avg_price * 0.0008
    converging = end_gap > 0 and start_gap > end_gap

    if not converging:
        return []

    name = None
    direction = "Neutral"
    notes = "Converging highs and lows indicate compression."
    if high_slope < -flat_threshold and low_slope > flat_threshold:
        name = "Symmetrical Triangle"
    elif abs(high_slope) <= flat_threshold and low_slope > flat_threshold:
        name = "Ascending Triangle"
        direction = "Bullish"
        notes = "Flat resistance with rising lows."
    elif high_slope < -flat_threshold and abs(low_slope) <= flat_threshold:
        name = "Descending Triangle"
        direction = "Bearish"
        notes = "Falling highs against flat support."
    elif high_slope > flat_threshold and low_slope > flat_threshold and low_slope > high_slope:
        name = "Rising Wedge"
        direction = "Bearish"
        notes = "Both trendlines rise while range compresses."
    elif high_slope < -flat_threshold and low_slope < -flat_threshold and high_slope > low_slope:
        name = "Falling Wedge"
        direction = "Bullish"
        notes = "Both trendlines fall while range compresses."

    if not name:
        return []

    key_level = _line_price(high_line, current) if direction != "Bearish" else _line_price(low_line, current)
    points = sorted(highs[-3:] + lows[-3:], key=lambda row: row["idx"])
    lines = [
        {"name": "Upper trendline", "line": high_line, "start_idx": highs[0]["idx"], "end_idx": current},
        {"name": "Lower trendline", "line": low_line, "start_idx": lows[0]["idx"], "end_idx": current},
    ]
    compression = max(0.0, min(0.2, (start_gap - end_gap) / start_gap if start_gap else 0.0))
    return [
        _pattern_record(
            name,
            direction,
            0.58 + compression,
            points,
            notes,
            key_level,
            lines,
        )
    ]


def _detect_chart_patterns(price_df, enabled_patterns):
    chart_df = _prepare_price_df(price_df)
    if chart_df.empty or len(chart_df) < 30:
        return []

    swings = _swing_points(chart_df, length=4)
    patterns = []

    if "Head & shoulders" in enabled_patterns:
        patterns.extend(_detect_head_shoulders(chart_df, swings))
    if "Cup & handle" in enabled_patterns:
        patterns.extend(_detect_cup_handle(chart_df))
    if "Flags" in enabled_patterns:
        patterns.extend(_detect_flag(chart_df))
    if "Triangles / wedges" in enabled_patterns:
        patterns.extend(_detect_triangle_wedge(chart_df, swings))

    patterns = sorted(patterns, key=lambda row: row["Confidence"], reverse=True)
    return patterns[:5]


def _add_pattern_annotations(fig, chart_df, patterns):
    price_df = _prepare_price_df(chart_df)
    if price_df.empty:
        return

    color_by_direction = {
        "Bullish": "#0b7a53",
        "Bearish": "#b42318",
        "Neutral": "#475467",
    }

    for pattern in patterns:
        color = color_by_direction.get(pattern.get("Direction"), "#475467")
        points = pattern.get("points") or []
        plot_points = [p for p in points if 0 <= int(p.get("idx", -1)) < len(price_df)]
        if plot_points:
            fig.add_trace(
                go.Scatter(
                    x=[price_df.iloc[int(p["idx"])]["Date"] for p in plot_points],
                    y=[p["price"] for p in plot_points],
                    mode="lines+markers",
                    name=pattern["Pattern"],
                    line={"color": color, "width": 2, "dash": "dash"},
                    marker={"size": 8, "color": color},
                    hovertemplate="%{y:$,.2f}<extra>" + pattern["Pattern"] + "</extra>",
                )
            )
            anchor = plot_points[-1]
            fig.add_annotation(
                x=price_df.iloc[int(anchor["idx"])]["Date"],
                y=anchor["price"],
                text=f"{pattern['Pattern']} ({pattern['Confidence'] * 100:.0f}%)",
                showarrow=True,
                arrowhead=2,
                ax=20,
                ay=-35 if pattern.get("Direction") != "Bearish" else 35,
                bgcolor="rgba(255,255,255,0.88)",
                bordercolor=color,
                font={"color": color, "size": 11},
            )

        for line_def in pattern.get("lines") or []:
            line = line_def.get("line")
            start_idx = max(0, int(line_def.get("start_idx", 0)))
            end_idx = min(len(price_df) - 1, int(line_def.get("end_idx", len(price_df) - 1)))
            if line is None or start_idx >= end_idx:
                continue
            fig.add_trace(
                go.Scatter(
                    x=[price_df.iloc[start_idx]["Date"], price_df.iloc[end_idx]["Date"]],
                    y=[_line_price(line, start_idx), _line_price(line, end_idx)],
                    mode="lines",
                    name=line_def.get("name", "Pattern trendline"),
                    line={"color": color, "width": 1.6},
                    hoverinfo="skip",
                )
            )


def _render_multi_timeframe_chart(db, symbol, snapshot=None):
    st.markdown("### Multi-Timeframe Chart Analysis")

    timeframe_options = {
        "5m / 5D": ("5d", "5m"),
        "15m / 10D": ("10d", "15m"),
        "30m / 1M": ("1mo", "30m"),
        "60m / 3M": ("3mo", "60m"),
        "Daily / 1Y": ("1y", "1d"),
    }

    c1, c2, c3, c4 = st.columns([1, 1.1, 1.6, 1.2])
    with c1:
        timeframe_label = st.selectbox(
            "Chart timeframe",
            list(timeframe_options.keys()),
            index=1,
            key=f"mtf_timeframe_{symbol}",
        )
    with c2:
        chart_style = st.radio(
            "Chart style",
            ["Candles", "Line"],
            horizontal=True,
            key=f"mtf_chart_style_{symbol}",
        )
    with c3:
        overlays = st.multiselect(
            "Overlay levels",
            ["Daily levels", "Weekly levels", "Stored analytics levels"],
            default=["Daily levels", "Weekly levels"],
            key=f"mtf_overlays_{symbol}",
        )
    with c4:
        auto_patterns = st.checkbox(
            "Auto patterns",
            value=True,
            key=f"mtf_auto_patterns_{symbol}",
        )

    enabled_patterns = []
    if auto_patterns:
        enabled_patterns = st.multiselect(
            "Pattern recognition",
            ["Head & shoulders", "Cup & handle", "Flags", "Triangles / wedges"],
            default=["Head & shoulders", "Cup & handle", "Flags", "Triangles / wedges"],
            key=f"mtf_pattern_types_{symbol}",
        )

    period, interval = timeframe_options[timeframe_label]

    try:
        chart_df = _prepare_price_df(get_price_history(db, symbol, period=period, interval=interval))
    except Exception as e:
        st.info(f"Chart data unavailable: {e}")
        return pd.DataFrame()

    if chart_df.empty:
        st.info("No chart data available for the selected timeframe.")
        return chart_df

    levels = []
    daily_df = pd.DataFrame()

    if "Daily levels" in overlays or "Weekly levels" in overlays:
        try:
            daily_df = _prepare_price_df(get_price_history(db, symbol, period="1y", interval="1d"))
        except Exception:
            daily_df = pd.DataFrame()

    if "Daily levels" in overlays and not daily_df.empty:
        levels.extend(_higher_timeframe_levels(daily_df, "Daily", lookback=20))

    if "Weekly levels" in overlays and not daily_df.empty:
        weekly_df = _resample_to_weekly(daily_df)
        levels.extend(_higher_timeframe_levels(weekly_df, "Weekly", lookback=12))

    if "Stored analytics levels" in overlays:
        levels.extend(_snapshot_levels(snapshot))

    fig = go.Figure()
    required_ohlc = {"Open", "High", "Low", "Close"}.issubset(chart_df.columns)
    if chart_style == "Candles" and required_ohlc:
        fig.add_trace(
            go.Candlestick(
                x=chart_df["Date"],
                open=chart_df["Open"],
                high=chart_df["High"],
                low=chart_df["Low"],
                close=chart_df["Close"],
                name=f"{symbol} {interval}",
            )
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=chart_df["Date"],
                y=chart_df["Close"],
                mode="lines",
                name=f"{symbol} {interval}",
                line={"color": "#1f77b4", "width": 1.8},
            )
        )

    if len(chart_df) >= 20:
        fig.add_trace(
            go.Scatter(
                x=chart_df["Date"],
                y=chart_df["Close"].rolling(20).mean(),
                mode="lines",
                name="MA 20",
                line={"color": "#667085", "width": 1.1},
            )
        )

    _add_level_lines(fig, levels)
    patterns = _detect_chart_patterns(chart_df, enabled_patterns) if auto_patterns else []
    _add_pattern_annotations(fig, chart_df, patterns)

    fig.update_layout(
        title=f"{symbol} {timeframe_label} with Higher-Timeframe Levels & Auto Patterns",
        height=620,
        margin={"l": 20, "r": 20, "t": 60, "b": 30},
        xaxis_title="Time",
        yaxis_title="Price",
        hovermode="x unified",
        legend_orientation="h",
        legend_yanchor="bottom",
        legend_y=1.02,
        legend_xanchor="right",
        legend_x=1,
    )
    fig.update_xaxes(rangeslider_visible=False)

    st.plotly_chart(fig, use_container_width=True)

    if levels:
        levels_df = pd.DataFrame(levels)
        latest = _latest_close(chart_df)
        if latest:
            levels_df["Distance"] = (levels_df["Price"] / latest - 1.0) * 100.0
        else:
            levels_df["Distance"] = None
        st.dataframe(
            levels_df.style.format({"Price": "${:,.2f}", "Distance": "{:+.2f}%"}),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No higher-timeframe levels are available for the selected overlays.")

    if auto_patterns:
        if patterns:
            pattern_df = pd.DataFrame(
                [
                    {
                        "Pattern": pattern["Pattern"],
                        "Direction": pattern["Direction"],
                        "Confidence": pattern["Confidence"],
                        "Start": pattern["Start"],
                        "End": pattern["End"],
                        "Key Level": pattern["Key Level"],
                        "Notes": pattern["Notes"],
                    }
                    for pattern in patterns
                ]
            )
            st.markdown("#### Auto-Detected Chart Patterns")
            st.dataframe(
                pattern_df.style.format(
                    {
                        "Confidence": "{:.0%}",
                        "Key Level": lambda v: "N/A" if pd.isna(v) else f"${v:,.2f}",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No high-confidence automated chart patterns detected on the selected timeframe.")

    return chart_df


def _render_dcf_builder(db, tenant_id, symbol, price_df=None):
    st.markdown("### DCF / Valuation Model Builder")

    try:
        base = build_dcf_base_inputs(db, tenant_id, symbol)
    except Exception as e:
        st.info(f"DCF base data unavailable: {e}")
        base = {}

    base_fcf_m = (_safe_float(base.get("base_fcf")) or 1_000_000_000.0) / 1_000_000.0
    shares_m = (_safe_float(base.get("shares_outstanding")) or 1_000_000_000.0) / 1_000_000.0
    net_debt_m = (_safe_float(base.get("net_debt")) or 0.0) / 1_000_000.0
    current_price = _latest_close(price_df) or _safe_float(base.get("current_price")) or 0.0

    a1, a2, a3, a4 = st.columns(4)
    with a1:
        growth_rate = st.slider(
            "FCF growth rate",
            min_value=-20.0,
            max_value=40.0,
            value=8.0,
            step=0.5,
            format="%.1f%%",
            key=f"dcf_growth_{symbol}",
        ) / 100.0
    with a2:
        discount_rate = st.slider(
            "Discount rate",
            min_value=2.0,
            max_value=25.0,
            value=10.0,
            step=0.25,
            format="%.2f%%",
            key=f"dcf_discount_{symbol}",
        ) / 100.0
    with a3:
        terminal_multiple = st.slider(
            "Terminal multiple",
            min_value=2.0,
            max_value=35.0,
            value=14.0,
            step=0.5,
            format="%.1fx",
            key=f"dcf_terminal_multiple_{symbol}",
        )
    with a4:
        projection_years = st.slider(
            "Projection years",
            min_value=3,
            max_value=10,
            value=5,
            step=1,
            key=f"dcf_years_{symbol}",
        )

    i1, i2, i3, i4 = st.columns(4)
    with i1:
        base_fcf_m = st.number_input(
            "Base FCF ($M)",
            min_value=0.01,
            value=float(round(base_fcf_m, 2)),
            step=50.0,
            key=f"dcf_base_fcf_{symbol}",
        )
    with i2:
        shares_m = st.number_input(
            "Shares outstanding (M)",
            min_value=0.01,
            value=float(round(shares_m, 2)),
            step=25.0,
            key=f"dcf_shares_{symbol}",
        )
    with i3:
        net_debt_m = st.number_input(
            "Net debt ($M)",
            value=float(round(net_debt_m, 2)),
            step=50.0,
            key=f"dcf_net_debt_{symbol}",
        )
    with i4:
        current_price = st.number_input(
            "Current price",
            min_value=0.0,
            value=float(round(current_price, 2)),
            step=1.0,
            key=f"dcf_current_price_{symbol}",
        )

    try:
        result = compute_dcf_valuation(
            base_fcf=base_fcf_m * 1_000_000.0,
            shares_outstanding=shares_m * 1_000_000.0,
            net_debt=net_debt_m * 1_000_000.0,
            growth_rate=growth_rate,
            discount_rate=discount_rate,
            terminal_multiple=terminal_multiple,
            projection_years=projection_years,
        )
    except Exception as e:
        st.warning(f"DCF model could not be calculated: {e}")
        return

    fair_value = result["fair_value_per_share"]
    upside = (fair_value / current_price - 1.0) if current_price else None

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Fair value", f"${fair_value:,.2f}")
    m2.metric("Current price", f"${current_price:,.2f}" if current_price else "N/A")
    m3.metric("Upside / downside", f"{upside * 100:,.1f}%" if upside is not None else "N/A")
    m4.metric("Equity value", _money_str(result["equity_value"]))
    m5.metric("Enterprise value", _money_str(result["enterprise_value"]))

    projection_df = pd.DataFrame(
        [
            {
                "Year": row["year"],
                "FCF ($M)": row["fcf"] / 1_000_000.0,
                "Discount Factor": row["discount_factor"],
                "PV FCF ($M)": row["present_value"] / 1_000_000.0,
            }
            for row in result["projections"]
        ]
    )
    st.dataframe(
        projection_df.style.format(
            {
                "FCF ($M)": "{:,.1f}",
                "Discount Factor": "{:,.2f}",
                "PV FCF ($M)": "{:,.1f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    growth_cases = [growth_rate - 0.02, growth_rate, growth_rate + 0.02]
    discount_cases = [discount_rate - 0.01, discount_rate, discount_rate + 0.01]
    sensitivity_rows = []
    for g in growth_cases:
        row = {"Growth": f"{g * 100:.1f}%"}
        for d in discount_cases:
            case = compute_dcf_valuation(
                base_fcf=base_fcf_m * 1_000_000.0,
                shares_outstanding=shares_m * 1_000_000.0,
                net_debt=net_debt_m * 1_000_000.0,
                growth_rate=g,
                discount_rate=d,
                terminal_multiple=terminal_multiple,
                projection_years=projection_years,
            )
            row[f"Discount {d * 100:.1f}%"] = case["fair_value_per_share"]
        sensitivity_rows.append(row)

    st.markdown("#### Fair Value Sensitivity")
    st.dataframe(
        pd.DataFrame(sensitivity_rows).style.format(
            {col: "${:,.2f}" for col in pd.DataFrame(sensitivity_rows).columns if col != "Growth"}
        ),
        use_container_width=True,
        hide_index=True,
    )

    terminal_weight = result.get("terminal_value_weight")
    st.caption(
        "Terminal PV: "
        f"{_money_str(result['present_value_terminal'])}"
        + (f" ({terminal_weight * 100:,.1f}% of enterprise value)" if terminal_weight is not None else "")
    )


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

    px = None
    try:
        px = _render_multi_timeframe_chart(db, symbol, snapshot=snapshot)
    except Exception as e:
        st.info(f"Multi-timeframe chart unavailable: {e}")
        try:
            px = get_price_history(db, symbol, period="1y", interval="1d")
            _render_price_chart(px, symbol)
        except Exception:
            px = None

    st.divider()
    _render_seasonality_charts(db, symbol)

    st.divider()
    _render_dcf_builder(db, tenant_id, symbol, px)

    # Pre-fetch news and sentiment so the Digest can use them
    news_items, sentiment = [], {}
    try:
        news_items = get_finnhub_news(symbol) or []
        sentiment  = get_finnhub_sentiment(symbol) or {}
        if not sentiment:
            def _derive_sentiment(items):
                bull_words = ["beat","growth","strong","upgrade","outperform","record","surge","expansion","positive"]
                bear_words = ["miss","weak","downgrade","decline","drop","cut","risk","concern","negative"]
                b, bear = 0, 0
                for n in items:
                    txt = f"{n.get('headline','')} {n.get('summary','')}".lower()
                    if any(w in txt for w in bull_words): b += 1
                    if any(w in txt for w in bear_words): bear += 1
                total = b + bear
                return {"bullish": b, "bearish": bear, "score": (b - bear) / total if total else 0.0}
            sentiment = _derive_sentiment(news_items)
    except Exception:
        pass

    # ── AI Stock Digest ──────────────────────────────────────
    try:
        from modules.digest.stock_digest import render_stock_digest
        render_stock_digest(
            symbol=symbol,
            snapshot=snapshot,
            news_items=news_items if "news_items" in dir() else [],
            sentiment=sentiment if "sentiment" in dir() else {},
            price_df=px if "px" in dir() else None,
        )
    except Exception as _digest_err:
        st.caption(f"Digest unavailable: {_digest_err}")

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
