
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st = None
    pd = None

from modules.forex.ui.forex_ui_theme import inject_forex_ui_theme
from modules.forex.ui.forex_ui_layout import panel, render_section_header
from modules.forex.ui.forex_ui_status import render_status_pill
from modules.forex.ui.forex_signal_validation_summary import (
    extract_validation_rows,
    validation_table,
    validation_commentary,
    validation_metrics,
    safe_float,
)
from modules.forex.ui.forex_signal_validation_cards import render_signal_validation_kpi_ribbon
from modules.forex.ui.forex_signal_validation_charts import (
    render_validation_gauge,
    render_validation_status_mix,
    render_validation_score_bar,
    render_validation_timeline,
    render_validation_heatmap,
)
from modules.forex.ui.forex_signal_validation_adapter import (
    normalize_validation_payload,
)

def _table(rows, height=320):
    if st is None:
        return rows
    if pd is None:
        st.write(rows)
        return
    df = pd.DataFrame(rows if isinstance(rows, list) else [rows])
    if df.empty:
        st.info("No rows available.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)

def render_forex_signal_validation_workspace(payload: Optional[Dict[str, Any]] = None, *, db=None) -> Dict[str, Any]:
    payload = normalize_validation_payload(payload or {})

    signals = payload["signals"]
    summary = payload["summary"]
    analytics = payload["analytics"]

    rows = signals

    metrics = {
        "validation_score": summary.get("validation_score", 0),
        "confidence": summary.get("confidence", 0),
        "risk_reward": summary.get("risk_reward", 0),
        "signal_count": summary.get("signal_count", 0),
    }

    if st is None:
        return {"status": "READY", "rows": rows, "metrics": metrics}

    inject_forex_ui_theme(st)
    render_section_header(
        "Signal Validation Workstation",
        kicker="Institutional Validation",
        meta=datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
    )

    render_signal_validation_kpi_ribbon(rows)

    top = summary.get("top_signal") or {}
    with panel("Validation Decision Banner", kicker="Current Top Signal", meta=top.get("status", "READY")):
        c1, c2, c3, c4 = st.columns([1.25, 1, 1, 1])
        status = top.get("status", "READY")
        signal = top.get("signal", "WATCH")
        pair = top.get("pair", "EUR/USD")

        c1.markdown(f"## {signal} {pair}")
        c1.markdown(
            f"**Institutional Validation:** {status}"
        )
        c2.metric(
            "Validation Score",
            f"{summary['validation_score']:.0f}"
        )
        c3.metric(
            "Confidence",
            f"{summary['confidence']:.0f}%"
        )
        c4.metric(
            "Risk / Reward",
            f"{summary['risk_reward']:.2f}"
        )
        render_status_pill(
            top.get("status", "READY"),
            label=f"{top.get('strategy', 'Institutional')} Validation",
        )

    left, right = st.columns([1.35, 1])

    with left:

        # ----------------------------------------------------------
        # Institutional Signal Ranking
        # ----------------------------------------------------------
        with panel(
                "Validated Signal Ranking",
                kicker="Validation Results",
        ):
            table = []

            for i, row in enumerate(rows, start=1):
                table.append({

                    "Rank": i,

                    "Pair": row.get("pair", ""),

                    "Signal": row.get("signal", ""),

                    "Validation": row.get("validation_score", 0),

                    "Confidence": row.get("confidence", 0),

                    "Risk / Reward": row.get("risk_reward", 0),

                    "Status": row.get("status", "READY"),

                    "Strategy": row.get("strategy", "Institutional"),

                })

            _table(table, height=430)

        # ----------------------------------------------------------
        # AI Validation Narrative
        # ----------------------------------------------------------
        with panel(
                "Validation Narrative",
                kicker="AI Quality Review",
        ):
            st.markdown(f"""
    ### Institutional Validation Summary

    **Signals Evaluated:** {summary["signal_count"]}

    **Average Validation Score:** {analytics["average_validation"]:.1f}

    **Average Confidence:** {analytics["average_confidence"]:.1f}%

    **BUY Signals:** {analytics["buy_count"]}

    **SELL Signals:** {analytics["sell_count"]}

    **WATCH Signals:** {analytics["watch_count"]}

    The institutional validation engine has normalized all candidate
    signals, removed duplicate opportunities, ranked them by validation
    quality, and calculated confidence using the unified AI validation
    pipeline.

    Only the highest-ranked opportunity for each
    Pair / Signal / Timeframe combination is presented to the trader.
    """)

        # ----------------------------------------------------------
        # Validation Timeline
        # ----------------------------------------------------------
        with panel(
                "Validation Timeline",
                kicker="Model Quality",
        ):
            render_validation_timeline(rows)

    with right:

        with panel("Signal Quality Gauge", kicker="Success Rate"):
            render_validation_gauge(
                score=summary["validation_score"],
                confidence=summary["confidence"],
            )

        with panel("Validation Mix", kicker="Status Distribution"):
            render_validation_status_mix(rows)

        with panel("Validation Scores", kicker="Signal Ranking"):
            render_validation_score_bar(rows)

    with panel("Validation Heatmap", kicker="Quality Matrix"):
        render_validation_heatmap(rows)

    with panel("Risk & Rejection Review", kicker="Controls"):
        rejection_rows = []
        for row in rows:
            if row.get("status", "").upper() in {
                "REJECTED",
                "PENDING",
                "WATCH",
            }:
                rejection_rows.append({
                    "Pair": row.get("pair"),
                    "Signal": row.get("signal"),
                    "Status": row.get("status"),
                    "Reason": row.get("reason"),
                    "Score": row.get("validation_score"),
                    "Confidence": row.get("confidence"),
                    "Risk Reward": row.get("risk_reward"),
                })
        _table(rejection_rows or [{"Status": "READY", "Message": "No rejected signals in current validation set."}], height=300)

    return {"status": "READY", "rows": rows, "metrics": metrics}
