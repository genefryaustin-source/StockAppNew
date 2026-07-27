
from __future__ import annotations

from typing import Any, Dict

import pandas as pd
import streamlit as st

from modules.forex.ui.forex_ui_layout import panel, render_section_header
from modules.forex.ui.forex_ui_cards import ForexMetricCard, render_metric_ribbon
from modules.forex.ui.forex_ui_status import render_status_pill
from modules.forex.ui.forex_ai_charts import render_heatmap_from_rows
from modules.forex.ui.forex_ai_executive_adapter import normalize_executive_ai_payload, safe_float
from modules.forex.ui.forex_ai_consensus_engine import build_consensus, consensus_summary_text
from modules.forex.ui.forex_ai_consensus_charts import (
    render_consensus_gauge,
    render_vote_mix,
    render_model_confidence_bar,
    render_attribution_bar,
)


def _df(rows: Any) -> pd.DataFrame:
    if rows is None:
        return pd.DataFrame()
    if isinstance(rows, dict):
        return pd.DataFrame([rows])
    if isinstance(rows, list):
        return pd.DataFrame([x for x in rows if isinstance(x, dict)])
    return pd.DataFrame()


def _table(rows: Any, height: int = 320) -> None:
    df = _df(rows)
    if df.empty:
        st.info("No rows available from the current AI/Quant payload.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)


def _status_for_score(score: float) -> str:
    score = safe_float(score)
    if score >= 80:
        return "READY"
    if score >= 60:
        return "WATCH"
    return "WARNING"


def build_commentary(data: Dict[str, Any], consensus: Dict[str, Any]) -> str:
    rec = data["recommendation"]
    summary = data["summary"]
    regime = data["regime"]

    base = consensus_summary_text(consensus)

    if summary.get("signals", 0) <= 0:
        return f"""
{base}

No validated trade opportunities were found in the current AI/Quant payload.

The executive dashboard and consensus engine are wired to the live payload, but upstream engines
are not yet returning scored opportunity rows for this refresh. Check the Developer tab for the raw payload.
"""

    return f"""
{base}

Markets are currently classified as **{regime.get('regime', 'Unknown')}** with liquidity reported as
**{regime.get('liquidity', 'Unknown')}**.

The top institutional setup is **{rec.get('signal', 'WATCH')} {rec.get('pair', 'N/A')}** with
**{rec.get('confidence', 0):.0f}% AI confidence**, **{rec.get('validation_score', 0):.0f}**
validation score, and **{rec.get('risk_reward', 0):.2f}** risk/reward.

Institutional grade is **{rec.get('grade', 'Review')}**. Execution remains paper-trading only until broker
risk controls and live order routing are explicitly enabled.
"""


def render_ai_executive_dashboard(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = normalize_executive_ai_payload(payload)
    consensus = build_consensus(payload)
    rec = data["recommendation"]
    summary = data["summary"]
    regime = data["regime"]

    # Override executive confidence and decision with consensus layer.
    summary["ai_confidence"] = consensus.get("weighted_confidence", summary.get("ai_confidence", 0))
    if consensus.get("top_pair") and consensus.get("top_pair") != "N/A":
        summary["top_pair"] = consensus.get("top_pair")
        rec["pair"] = consensus.get("top_pair")
    rec["signal"] = consensus.get("executive_decision", rec.get("signal", "WATCH"))
    rec["confidence"] = consensus.get("weighted_confidence", rec.get("confidence", 0))
    rec["status"] = consensus.get("status", rec.get("status", "READY"))

    render_section_header("Executive AI Command Center", kicker="Executive", meta=data.get("status", "READY"))

    with panel("Global Market Regime", kicker="Macro"):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Regime", regime.get("regime", "Unknown"))
        c2.metric("Liquidity", regime.get("liquidity", "Unknown"))
        c3.metric("Macro Score", f"{safe_float(regime.get('macro_score')):.0f}")
        c4.metric("Consensus", f"{safe_float(consensus.get('weighted_confidence')):.0f}%")

    with panel("Institutional AI Recommendation", kicker="Executive Decision", meta=rec.get("status", "READY")):
        c1, c2, c3, c4 = st.columns([1.3, 1, 1, 1])
        with c1:
            st.markdown(f"# {rec.get('signal', 'WATCH')} {rec.get('pair', 'N/A')}")
            st.caption(f"Strategy: {rec.get('strategy', 'Institutional')}")
            render_status_pill(rec.get("status", "READY"), label=f"Agreement {safe_float(consensus.get('agreement_score')):.0f}%")
        c2.metric("Consensus", f"{safe_float(consensus.get('weighted_confidence')):.0f}%")
        c3.metric("Agreement", f"{safe_float(consensus.get('agreement_score')):.0f}%")
        c4.metric("Risk / Reward", f"{safe_float(rec.get('risk_reward')):.2f}")

    cards = [
        ForexMetricCard("AI Consensus", f"{safe_float(consensus.get('weighted_confidence')):.0f}%", "Weighted model confidence", progress=safe_float(consensus.get("weighted_confidence")), status=_status_for_score(consensus.get("weighted_confidence"))),
        ForexMetricCard("Agreement", f"{safe_float(consensus.get('agreement_score')):.0f}%", "Cross-model vote agreement", progress=safe_float(consensus.get("agreement_score")), status=_status_for_score(consensus.get("agreement_score"))),
        ForexMetricCard("Active Models", f"{consensus.get('active_models', 0)}/{consensus.get('total_models', 0)}", "Consensus engines", progress=min(safe_float(consensus.get("active_models")) * 12, 100), status="ACTIVE" if consensus.get("active_models", 0) else "WARNING"),
        ForexMetricCard("Alpha Score", f"{safe_float(summary.get('alpha_score')):.1f}", "Cross-model alpha", progress=safe_float(summary.get("alpha_score")), status=_status_for_score(summary.get("alpha_score"))),
        ForexMetricCard("Signals", summary.get("signals", 0), "Current opportunity set", progress=min(safe_float(summary.get("signals")) * 10, 100), status="READY" if summary.get("signals", 0) else "WATCH"),
        ForexMetricCard("Signal Success", f"{safe_float(summary.get('signal_success')):.0f}%", "Validation quality", progress=safe_float(summary.get("signal_success")), status=_status_for_score(summary.get("signal_success"))),
        ForexMetricCard("Top Pair", str(summary.get("top_pair", "N/A")), "Highest ranked setup", progress=100 if summary.get("top_pair") != "N/A" else 0, status="ACTIVE" if summary.get("top_pair") != "N/A" else "WATCH"),
    ]
    render_metric_ribbon(cards)

    left, right = st.columns([1.3, 1])

    with left:
        with panel("Executive Commentary", kicker="Consensus Narrative"):
            st.markdown(build_commentary(data, consensus))

        with panel("Top Opportunities", kicker="Institutional"):
            opportunities = []
            for row in data.get("opportunities", [])[:15]:
                opportunities.append(
                    {
                        "Rank": row.get("rank"),
                        "Pair": row.get("pair"),
                        "Signal": row.get("signal"),
                        "Confidence": row.get("confidence"),
                        "Validation": row.get("validation_score"),
                        "Alpha": row.get("alpha_score"),
                        "Risk / Reward": row.get("risk_reward"),
                        "Grade": row.get("institutional_grade"),
                        "Status": row.get("status"),
                    }
                )
            _table(opportunities, height=300)

        with panel("Consensus Votes", kicker="Model-by-Model"):
            _table(consensus.get("votes", []), height=300)

        with panel("Confidence Attribution", kicker="Weighted Contribution"):
            _table(consensus.get("attribution", []), height=260)

    with right:
        with panel("Consensus Gauge", kicker="AI Confidence"):
            render_consensus_gauge(consensus)

        with panel("Vote Mix", kicker="Decision Split"):
            render_vote_mix(consensus)

        with panel("Model Confidence", kicker="Engine Scores"):
            render_model_confidence_bar(consensus)

        with panel("Confidence Attribution", kicker="Contribution"):
            render_attribution_bar(consensus)

        with panel("Opportunity Heat Map", kicker="AI"):
            rows = data.get("opportunities", [])
            if rows:
                render_heatmap_from_rows(rows)
            else:
                st.info("No scored opportunity rows available for the heat map.")

    return {"executive": data, "consensus": consensus}
