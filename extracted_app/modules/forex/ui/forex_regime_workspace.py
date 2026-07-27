
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
from modules.forex.ui.forex_regime_summary import normalize_regime, extract_regime_rows, extract_macro_drivers, regime_commentary
from modules.forex.ui.forex_regime_cards import render_regime_kpi_ribbon
from modules.forex.ui.forex_regime_charts import (
    render_regime_gauge,
    render_transition_probability,
    render_regime_timeline,
    render_macro_driver_bar,
)

def _table(rows, height=300):
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

def render_forex_regime_workspace(payload: Optional[Dict[str, Any]] = None, *, db=None) -> Dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    regime = normalize_regime(payload)
    history = extract_regime_rows(payload)
    drivers = extract_macro_drivers(payload)

    if st is None:
        return {"status": "READY", "regime": regime, "history": history, "drivers": drivers}

    inject_forex_ui_theme(st)
    render_section_header(
        "Regime Intelligence Workstation",
        kicker="Macro Regime",
        meta=datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
    )

    render_regime_kpi_ribbon(payload)

    with panel("Global Market Regime", kicker="Current State", meta=str(regime["regime"])):
        c1, c2 = st.columns([1.3, 1])
        with c1:
            st.markdown(
                f"""
<div style="font-size:2.2rem;font-weight:950;color:var(--fx-cyan);">
{regime['regime'].replace('_', '-')}
</div>
<div class="fx-muted" style="margin-top:5px;">
Risk Appetite: {regime['risk_appetite']} • Liquidity: {regime['liquidity']} • Volatility: {regime['volatility']}
</div>
""",
                unsafe_allow_html=True,
            )
            render_status_pill("READY" if regime["confidence"] >= 70 else "WATCH", label=f"Confidence {regime['confidence']:.0f}%")
            st.markdown(regime_commentary(payload))
        with c2:
            render_regime_gauge(payload)

    left, right = st.columns([1.25, 1])

    with left:
        with panel("Transition Probability", kicker="Forward Regime Risk"):
            render_transition_probability(payload)

        with panel("Regime History", kicker="Timeline"):
            render_regime_timeline(history)

        with panel("Macro Driver Table", kicker="Central Banks / Liquidity / Volatility"):
            _table(drivers, height=330)

    with right:
        with panel("Macro Driver Impact", kicker="Driver Scores"):
            render_macro_driver_bar(drivers)

        with panel("Regime Detail", kicker="Normalized Payload"):
            detail = {k: v for k, v in regime.items() if k not in {"raw", "transition_probability"}}
            _table(detail, height=260)

        with panel("Execution Guidance", kicker="Risk Controls"):
            guidance = _execution_guidance(regime)
            _table(guidance, height=280)

    return {"status": "READY", "regime": regime, "history": history, "drivers": drivers}

def _execution_guidance(regime: Dict[str, Any]):
    risk_off = "OFF" in str(regime.get("regime", "")).upper()
    high_conf = float(regime.get("confidence") or 0) >= 75
    return [
        {"Control": "Position Sizing", "Guidance": "Reduce risk units" if risk_off else "Normal sizing", "Status": "WATCH" if risk_off else "READY"},
        {"Control": "Currency Bias", "Guidance": "Favor safe-haven and liquidity pairs" if risk_off else "Favor carry / growth-sensitive pairs", "Status": "READY"},
        {"Control": "Execution", "Guidance": "Use limit/TWAP in thin liquidity" if risk_off else "Standard paper execution", "Status": "READY"},
        {"Control": "AI Approval", "Guidance": "Require committee confirmation" if high_conf else "Await stronger confirmation", "Status": "READY" if high_conf else "WATCH"},
        {"Control": "Stop Discipline", "Guidance": "Tighten stops in elevated volatility", "Status": "WATCH" if str(regime.get("volatility")).lower() in {"high", "elevated"} else "READY"},
    ]
