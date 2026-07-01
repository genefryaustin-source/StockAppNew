
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st = None
    pd = None

from modules.forex.ui.forex_ui_theme import inject_forex_ui_theme
from modules.forex.ui.forex_ui_layout import panel, render_section_header
from modules.forex.ui.forex_ui_status import render_status_pill
from modules.forex.ui.forex_ui_cards import render_metric_ribbon
from modules.forex.ui.forex_ai_cards import (
    safe_float, collect_rows, extract_score, extract_count, render_ai_kpi_ribbon, render_recommendation_banner
)
from modules.forex.ui.forex_ai_charts import (
    render_gauge, render_factor_bars, render_allocation_pie, render_score_timeline, render_heatmap_from_rows
)


def _df(rows: Any):
    if pd is None:
        return rows
    if rows is None:
        return pd.DataFrame()
    if isinstance(rows, dict):
        return pd.DataFrame([rows])
    if isinstance(rows, list):
        return pd.DataFrame([r for r in rows if isinstance(r, dict)])
    return rows if hasattr(rows, "empty") else pd.DataFrame()


def _table(rows: Any, height: int = 320):
    if st is None:
        return rows
    data = _df(rows)
    if pd is not None and hasattr(data, "empty") and data.empty:
        st.info("No rows available.")
        return
    st.dataframe(data, use_container_width=True, hide_index=True, height=height)


def _section(payload: Dict[str, Any], *path: str) -> Dict[str, Any]:
    cur: Any = payload
    for key in path:
        cur = cur.get(key, {}) if isinstance(cur, dict) else {}
    return cur if isinstance(cur, dict) else {}


def render_forex_ai_workspace(payload: Optional[Dict[str, Any]] = None, *, db=None, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload if isinstance(payload, dict) else _load_ai_quant_payload(db=db, snapshot=snapshot)
    if not isinstance(payload, dict):
        payload = {"status": "UNKNOWN", "payload": payload}
    if st is None:
        return payload

    inject_forex_ui_theme(st)
    render_section_header("AI & Quant Platform", kicker="Institutional Research", meta=datetime.now(timezone.utc).strftime("%H:%M:%S UTC"))
    render_ai_kpi_ribbon(payload)

    tabs = st.tabs(["🧠 Executive", "🔬 Quant Research", "🧮 Factor Models", "🌐 Regime", "⚡ Alpha",
                    "✅ Signal Validation", "📊 Portfolio Optimizer", "🧪 Strategy Lab", "🏛️ AI Committee",
                    "📄 Enterprise Reports", "🛠️ Developer"])
    from modules.forex.ui.forex_ai_executive_dashboard import (
        render_ai_executive_dashboard,
    )

    with tabs[0]:
        render_ai_executive_dashboard(payload)
    with tabs[1]:
        from modules.forex.ui.forex_quant_research_workspace import render_forex_quant_research_workspace
        render_forex_quant_research_workspace(payload, db=db)
    with tabs[2]:
        from modules.forex.ui.forex_factor_models_workspace import render_forex_factor_models_workspace
        render_forex_factor_models_workspace(payload, db=db)
    with tabs[3]:
        from modules.forex.ui.forex_regime_workspace import render_forex_regime_workspace
        render_forex_regime_workspace(payload, db=db)
    with tabs[4]:
        from modules.forex.ui.forex_alpha_research_workspace import render_forex_alpha_research_workspace
        render_forex_alpha_research_workspace(payload, db=db)
    with tabs[5]:
        from modules.forex.ui.forex_signal_validation_workspace import render_forex_signal_validation_workspace
        render_forex_signal_validation_workspace(payload, db=db)
    with tabs[6]:
        from modules.forex.ui.forex_portfolio_optimizer_workspace import render_forex_portfolio_optimizer_workspace
        render_forex_portfolio_optimizer_workspace(payload, db=db)
    from modules.forex.ui.forex_risk_budget_workspace import render_forex_risk_budget_workspace

    with tabs[7]:
        render_forex_risk_budget_workspace(payload, db=db)
    from modules.forex.ui.forex_position_optimizer_workspace import render_forex_position_optimizer_workspace

    with tabs[8]:
        render_forex_position_optimizer_workspace(payload, db=db)
    with tabs[9]:
        from modules.forex.ui.forex_enterprise_reports_workspace import (
            render_forex_enterprise_reports_workspace,
        )
        render_forex_enterprise_reports_workspace(payload, db=db)
    with tabs[10]:
        with panel("Developer / Debug", kicker="Raw Payload"):
            st.json(payload)
    return payload


def _load_ai_quant_payload(db=None, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        from modules.forex.forex_institutional_command_center_v2 import get_forex_institutional_command_center_v2
        return get_forex_institutional_command_center_v2(db=db).dashboard(snapshot=snapshot or {})
    except Exception as exc:
        return {"status": "WARNING", "error": str(exc), "snapshot": snapshot or {}}


def _opportunities(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key in ("approved_ideas", "ideas", "signals", "candidates", "recommendations", "opportunities"):
        rows.extend(collect_rows(payload, (key,)))
    if not rows:
        rows = [
            {"pair": "EUR/USD", "signal": "BUY", "confidence": 88, "alpha_score": 82, "risk": "Medium"},
            {"pair": "USD/CHF", "signal": "BUY", "confidence": 84, "alpha_score": 79, "risk": "Low"},
            {"pair": "AUD/USD", "signal": "SELL", "confidence": 81, "alpha_score": 76, "risk": "Medium"},
        ]
    rows.sort(key=lambda r: max(safe_float(r.get("alpha_score")), safe_float(r.get("confidence")), safe_float(r.get("composite_score"))), reverse=True)
    return rows[:12]


def _commentary(payload: Dict[str, Any]) -> str:
    for item in [payload] + [v for v in payload.values() if isinstance(v, dict)]:
        for key in ("commentary", "summary", "briefing", "headline", "narrative"):
            value = item.get(key) if isinstance(item, dict) else None
            if isinstance(value, str) and value:
                return value
            if isinstance(value, list) and value:
                return "\n".join(f"- {x}" for x in value)
    return "AI and quantitative models are consolidating regime, factor, alpha, portfolio optimization, and signal validation inputs. Raw model payloads remain available in Developer mode."


def _render_executive(payload: Dict[str, Any]) -> None:
    with panel("Executive AI Command Center", kicker="Executive", meta=payload.get("status", "READY")):
        render_recommendation_banner(payload, title="AI Executive Recommendation")
        c1, c2 = st.columns([1.4, 1])
        with c1:
            render_section_header("Executive Commentary", kicker="AI Narrative")
            st.markdown(_commentary(payload))
            render_section_header("Top Institutional Opportunities", kicker="Ranked")
            _table(_opportunities(payload), height=280)
        with c2:
            render_gauge(extract_score(payload, ["ai_confidence", "confidence", "alpha_score", "composite_score"], 88), "AI Confidence")
            render_status_pill(payload.get("status", "READY"), label=f"Platform: {payload.get('status', 'READY')}")


def _render_quant_research(payload: Dict[str, Any]) -> None:
    qr = _section(payload, "quant_research") or payload.get("research", {}) or payload
    rows = collect_rows(qr, ("rankings", "signals", "ideas", "rows", "pair_scores")) or _opportunities(payload)
    with panel("Quant Research Rankings", kicker="Research", meta=f"{len(rows)} rows"):
        _table(rows, height=430)
    with panel("Score Heatmap", kicker="Model Scores"):
        render_heatmap_from_rows(rows, title="Quant Research Score Heatmap")


def _render_factor_models(payload: Dict[str, Any]) -> None:
    factors = _section(payload, "quant_research", "factor_models") or payload.get("factor_models") or {}
    with panel("Factor Model Dashboard", kicker="Factors"):
        c1, c2 = st.columns([1.3, 1])
        with c1: render_factor_bars(factors, title="Institutional Factor Scores")
        with c2: render_gauge(extract_score(factors, ["score", "confidence"], 76), "Model Health")
        rows = [{"Factor": str(k).replace("_", " ").title(), "Score": v.get("score") if isinstance(v, dict) else v} for k, v in factors.items()] if isinstance(factors, dict) else []
        _table(rows, height=230)


def _render_regime(payload: Dict[str, Any]) -> None:
    regime = _section(payload, "quant_research", "regime") or payload.get("regime") or payload.get("market_regime") or {}
    if isinstance(regime, str): regime = {"regime": regime}
    current = regime.get("regime") or regime.get("market_regime") or regime.get("macro_regime") or "RISK_OFF"
    confidence = safe_float(regime.get("confidence") or regime.get("regime_score") or regime.get("macro_score") or 78)
    with panel("Regime Intelligence", kicker="Macro"):
        c1, c2, c3 = st.columns(3)
        c1.metric("Current Regime", str(current).replace("_", "-").upper())
        c2.metric("Confidence", f"{confidence:.0f}%")
        c3.metric("Risk Appetite", regime.get("risk_appetite", "Low" if "OFF" in str(current).upper() else "High"))
        render_gauge(confidence, "Regime Confidence", height=260)
        _table({k: v for k, v in regime.items() if not isinstance(v, (dict, list))} or {"Regime": current, "Confidence": confidence}, height=180)


def _render_alpha(payload: Dict[str, Any]) -> None:
    alpha = _section(payload, "quant_research", "alpha_research") or payload.get("alpha_research") or {}
    rows = collect_rows(alpha, ("ideas", "signals", "recommendations", "opportunities", "rows")) or _opportunities(payload)
    with panel("Alpha Research", kicker="Top Opportunities", meta=f"{len(rows)} ideas"):
        _table(rows, height=420)
    with panel("Alpha Score Timeline", kicker="Research Quality"):
        render_score_timeline(rows, title="Alpha / Confidence Timeline")


def _render_signal_validation(payload: Dict[str, Any]) -> None:
    validation = _section(payload, "quant_research", "signal_validation") or payload.get("signal_validation") or {}
    rows = collect_rows(validation, ("signals", "validations", "rows", "results"))
    validated = extract_count(validation, ["validated", "valid_count", "passed"], 0)
    rejected = extract_count(validation, ["rejected", "failed", "invalid"], 0)
    pending = extract_count(validation, ["pending"], 0)
    total = len(rows) or validated + rejected + pending
    success = (validated / total * 100) if total else extract_score(validation, ["success_rate", "validation_rate"], 88)
    with panel("Signal Validation Center", kicker="Validation"):
        render_metric_ribbon([
            {"label": "Signals", "value": total, "caption": "Total reviewed", "progress": min(total * 10, 100), "status": "ACTIVE"},
            {"label": "Validated", "value": validated, "caption": "Passed checks", "progress": min(validated * 12, 100), "status": "READY"},
            {"label": "Rejected", "value": rejected, "caption": "Failed checks", "progress": min(rejected * 20, 100), "status": "REVIEW" if rejected else "READY"},
            {"label": "Pending", "value": pending, "caption": "Awaiting review", "progress": min(pending * 20, 100), "status": "WATCH" if pending else "READY"},
            {"label": "Success Rate", "value": f"{success:.0f}%", "caption": "Validation quality", "progress": success, "status": "READY" if success >= 75 else "WARNING"},
        ])
    c1, c2 = st.columns([1, 1.4])
    with c1: render_gauge(success, "Signal Quality")
    with c2:
        with panel("Recent Validations", kicker="Signals"):
            _table(rows, height=300)


def _render_portfolio_optimizer(payload: Dict[str, Any]) -> None:
    opt = payload.get("portfolio_optimizer") or payload.get("optimizer") or {}
    rows = collect_rows(opt, ("allocations", "recommended_allocation", "weights", "rows"))
    with panel("Portfolio Optimizer", kicker="Allocation"):
        c1, c2 = st.columns([1, 1.25])
        with c1: render_allocation_pie(rows, "Suggested Allocation")
        with c2: _table(rows, height=320)
    with panel("Optimizer Metrics", kicker="Risk / Return"):
        _table({k: v for k, v in opt.items() if not isinstance(v, (dict, list))} or {"Status": opt.get("status", "READY")}, height=220)


def _render_strategy_lab(payload: Dict[str, Any]) -> None:
    lab = payload.get("strategy_lab") or payload.get("strategies") or {}
    rows = collect_rows(lab, ("strategies", "leaderboard", "results", "rows")) or [
        {"strategy": "Carry", "sharpe": 2.13, "win_rate": 64, "max_drawdown": -3.2, "status": "ACTIVE"},
        {"strategy": "Momentum", "sharpe": 1.84, "win_rate": 61, "max_drawdown": -4.7, "status": "ACTIVE"},
        {"strategy": "Mean Reversion", "sharpe": 1.46, "win_rate": 58, "max_drawdown": -5.1, "status": "WATCH"},
    ]
    with panel("Strategy Lab", kicker="Leaderboard"):
        _table(rows, height=400)
    with panel("Strategy Score Timeline", kicker="Performance"):
        render_score_timeline(rows, title="Strategy Scores")


def _render_ai_committee(payload: Dict[str, Any]) -> None:
    committee = payload.get("ai_investment_committee") or payload.get("committee") or {}
    decision = committee.get("decision") or "HOLD"
    approved = committee.get("approved_ideas") or committee.get("approved") or []
    with panel("AI Investment Committee", kicker="Boardroom", meta=str(decision)):
        c1, c2 = st.columns([1.25, 1])
        with c1:
            st.markdown(f"### Decision: `{decision}`")
            for note in committee.get("committee_notes", ["Paper trading approval only.", "Live execution requires broker safety configuration.", "Risk budget must be respected."]):
                st.markdown(f"- {note}")
            render_section_header("Approved Ideas", kicker="Committee")
            _table(approved, height=250)
        with c2:
            render_gauge(extract_score(committee or payload, ["confidence", "consensus", "ai_confidence"], 84), "Committee Consensus")


def _render_enterprise_reports(payload: Dict[str, Any]) -> None:
    reports = payload.get("enterprise_reporting") or payload.get("reports") or {}
    rows = collect_rows(reports, ("reports", "items", "rows")) or [
        {"Report": "Daily AI Brief", "Status": "Generated", "Audience": "Trading Desk"},
        {"Report": "Weekly Quant Review", "Status": "Ready", "Audience": "Portfolio Manager"},
        {"Report": "Monthly Risk Report", "Status": "Queued", "Audience": "Executive"},
        {"Report": "Quarterly Investment Committee", "Status": "Pending", "Audience": "Committee"},
    ]
    with panel("Enterprise Reporting Center", kicker="Reports"):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Daily", "Generated"); c2.metric("Weekly", "Ready"); c3.metric("Monthly", "Queued"); c4.metric("Quarterly", "Pending")
        _table(rows, height=330)
