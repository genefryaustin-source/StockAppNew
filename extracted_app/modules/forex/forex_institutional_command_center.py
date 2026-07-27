"""
modules/forex/forex_institutional_command_center.py

Institutional-style Forex command center UI.

This redesign replaces raw JSON-first rendering with a professional terminal
layout:
- top ribbon metric cards
- left intelligence stack
- center trading desk / recommendations
- right AI briefing / calendar / alerts
- bottom operational blotter
- developer/debug JSON expander

All imports are lazy where possible to avoid circular-import startup failures.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

try:
    import plotly.graph_objects as go
except Exception:  # pragma: no cover
    go = None

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None


DEFAULT_CURRENCIES = ["USD", "EUR", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD"]
DEFAULT_PAIRS = [
    "EUR/USD", "USD/JPY", "GBP/USD", "USD/CHF", "AUD/USD", "USD/CAD", "NZD/USD",
    "EUR/JPY", "EUR/GBP", "GBP/JPY", "CHF/JPY", "AUD/JPY",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except Exception:
        return default


def _fmt_money(value: Any) -> str:
    val = _safe_float(value)
    sign = "+" if val >= 0 else "-"
    return f"{sign}${abs(val):,.2f}"


def _fmt_pct(value: Any) -> str:
    return f"{_safe_float(value):+.2f}%"


def _badge_class(value: str) -> str:
    v = str(value or "").upper()
    if any(x in v for x in ["BUY", "BULL", "LONG", "HEALTHY", "READY", "RISK_ON", "PASS", "HIGH"]):
        return "fx-positive"
    if any(x in v for x in ["SELL", "BEAR", "SHORT", "ERROR", "FAIL", "RATE", "RISK_OFF", "DEGRADED"]):
        return "fx-negative"
    if any(x in v for x in ["WATCH", "NEUTRAL", "WARNING", "MODERATE"]):
        return "fx-warning"
    return "fx-muted"


def _currency_flag(code: str) -> str:
    return {
        "USD": "🇺🇸", "EUR": "🇪🇺", "JPY": "🇯🇵", "GBP": "🇬🇧",
        "CHF": "🇨🇭", "CAD": "🇨🇦", "AUD": "🇦🇺", "NZD": "🇳🇿",
    }.get(str(code or "").upper(), "🌐")


def _normalize_pair(pair: str) -> str:
    p = str(pair or "").replace("-", "/").replace("_", "/").upper().strip()
    if "/" not in p and len(p) == 6:
        p = p[:3] + "/" + p[3:]
    return p


def _terminal_css() -> None:
    if st is None:
        return

    st.markdown(
        """
<style>
.fx-shell {
    margin-top: -0.6rem;
}
.fx-card {
    background: linear-gradient(180deg, rgba(13,30,48,.96), rgba(5,15,26,.98));
    border: 1px solid rgba(0, 218, 255, .22);
    border-radius: 12px;
    padding: 14px 16px;
    box-shadow: 0 0 0 1px rgba(255,255,255,.02) inset, 0 10px 25px rgba(0,0,0,.25);
}
.fx-card-tight {
    background: linear-gradient(180deg, rgba(13,30,48,.96), rgba(5,15,26,.98));
    border: 1px solid rgba(0, 218, 255, .18);
    border-radius: 10px;
    padding: 10px 12px;
    margin-bottom: 10px;
}
.fx-title {
    font-size: .78rem;
    color: #9db4c9;
    text-transform: uppercase;
    letter-spacing: .06em;
    margin-bottom: 4px;
}
.fx-value {
    font-size: 1.55rem;
    line-height: 1.15;
    font-weight: 800;
    color: #f4f8ff;
}
.fx-sub {
    font-size: .78rem;
    color: #9db4c9;
    margin-top: 3px;
}
.fx-positive { color: #30e07a !important; }
.fx-negative { color: #ff4d5f !important; }
.fx-warning { color: #ffb020 !important; }
.fx-muted { color: #9db4c9 !important; }
.fx-mini-bar {
    width: 100%;
    height: 8px;
    border-radius: 8px;
    background: rgba(255,255,255,.08);
    overflow: hidden;
    margin-top: 8px;
}
.fx-mini-bar-fill {
    height: 8px;
    border-radius: 8px;
    background: linear-gradient(90deg, #00d2ff, #30e07a);
}
.fx-section-head {
    display:flex;
    justify-content:space-between;
    align-items:center;
    color:#c9d7e8;
    font-weight:700;
    font-size:.92rem;
    margin-bottom:9px;
}
.fx-chip {
    display:inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    background: rgba(0, 208, 255, .10);
    border: 1px solid rgba(0, 208, 255, .25);
    font-size:.72rem;
    color:#bfefff;
}
.fx-rec-card {
    border: 1px solid rgba(255,255,255,.12);
    border-radius: 11px;
    padding: 12px;
    background: rgba(255,255,255,.035);
}
.fx-rec-card-buy {
    border-color: rgba(48,224,122,.35);
    background: linear-gradient(180deg, rgba(48,224,122,.10), rgba(255,255,255,.025));
}
.fx-rec-card-sell {
    border-color: rgba(255,77,95,.35);
    background: linear-gradient(180deg, rgba(255,77,95,.10), rgba(255,255,255,.025));
}
.fx-table-note {
    font-size:.75rem;
    color:#8ca0b6;
}
div[data-testid="stMetricValue"] {
    font-size: 1.35rem;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _metric_card(title: str, value: Any, subtitle: str = "", mood: str = "muted", progress: Optional[float] = None) -> None:
    cls = _badge_class(mood)
    bar = ""
    if progress is not None:
        pct = max(0, min(100, _safe_float(progress)))
        bar = f"""<div class="fx-mini-bar"><div class="fx-mini-bar-fill" style="width:{pct}%"></div></div>"""
    if st is None:
        return
    st.markdown(
        f"""
<div class="fx-card">
  <div class="fx-title">{title}</div>
  <div class="fx-value {cls}">{value}</div>
  <div class="fx-sub">{subtitle}</div>
  {bar}
</div>
        """,
        unsafe_allow_html=True,
    )


def _panel_title(title: str, right: str = "") -> None:
    if st is None:
        return
    st.markdown(
        f"""<div class="fx-section-head"><span>{title}</span><span class="fx-chip">{right}</span></div>""",
        unsafe_allow_html=True,
    )


def _progress_table(rows: List[Dict[str, Any]], label_col: str, value_col: str, trend_col: Optional[str] = None) -> None:
    if st is None:
        return
    if not rows:
        st.info("No data available.")
        return

    for row in rows:
        label = str(row.get(label_col, "-"))
        value = _safe_float(row.get(value_col), 0)
        trend = str(row.get(trend_col, "")) if trend_col else ""
        trend_icon = "↑" if trend.upper() in {"UP", "BULLISH", "BUY", "LONG", "STRONG"} else "↓" if trend.upper() in {"DOWN", "BEARISH", "SELL", "SHORT", "WEAK"} else "—"
        trend_cls = "fx-positive" if trend_icon == "↑" else "fx-negative" if trend_icon == "↓" else "fx-muted"
        st.markdown(
            f"""
<div style="display:grid;grid-template-columns:54px 1fr 38px 28px;gap:8px;align-items:center;margin:5px 0;">
    <div style="font-weight:800;color:#e8f2ff;">{label}</div>
    <div class="fx-mini-bar" style="margin-top:0;"><div class="fx-mini-bar-fill" style="width:{max(0,min(100,value))}%"></div></div>
    <div style="text-align:right;color:#e8f2ff;">{value:.0f}</div>
    <div class="{trend_cls}" style="font-weight:800;">{trend_icon}</div>
</div>
            """,
            unsafe_allow_html=True,
        )


def _make_dataframe(rows: Any):
    if pd is None:
        return rows if isinstance(rows, list) else []
    if rows is None:
        return pd.DataFrame()
    if isinstance(rows, pd.DataFrame):
        return rows
    if isinstance(rows, dict):
        return pd.DataFrame([rows])
    if isinstance(rows, list):
        return pd.DataFrame(rows)
    return pd.DataFrame()


def _render_df(rows: Any, height: int = 260) -> None:
    if st is None:
        return
    df = _make_dataframe(rows)
    if pd is not None and hasattr(df, "empty") and df.empty:
        st.info("No rows available.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)


def _extract_snapshot(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Pull a best-effort institutional snapshot from the existing backend.

    This function only ever returns data that came from a real engine/provider
    call. When a source is unavailable or empty, the corresponding section is
    left empty (or flagged via ``snapshot["data_status"]``) instead of being
    padded with invented numbers. The UI layer is responsible for rendering an
    honest "no data" state for empty sections.
    """
    snapshot: Dict[str, Any] = {
        "generated_at": _now(),
        "market_regime": {},
        "currency_strength": [],
        "provider_health": [],
        "recommendations": [],
        "portfolio": {},
        "positions": [],
        "open_orders": [],
        "filled_orders": [],
        "journal": [],
        "performance": {},
        "equity_curve": [],
        "ai_briefing": {},
        "economic_calendar": [],
        "central_bank_events": [],
        "alerts": [],
        "raw": {},
        # Per-section live/unavailable status, filled in below as each
        # source is actually queried. The UI uses this to label a panel
        # honestly (live / no API key configured / error) instead of
        # presenting static or missing data as real-time.
        "data_status": {
            "economic_calendar": "unknown",
            "central_bank_events": "unknown",
        },
    }

    # Terminal / command center data
    try:
        from modules.forex.forex_terminal_api import get_forex_terminal_api
        terminal = get_forex_terminal_api(db=db)
        raw = terminal.get_terminal_snapshot(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            force_refresh=force_refresh,
        )
        if isinstance(raw, dict):
            snapshot["raw"]["terminal"] = raw
            market = raw.get("market_overview") or raw.get("command_center") or raw
            if isinstance(market, dict):
                snapshot["market_regime"] = (
                    market.get("market_regime")
                    or market.get("macro_regime")
                    or market.get("regime")
                    or {}
                )
    except Exception as exc:
        snapshot["raw"]["terminal_error"] = str(exc)

    # Service command center
    try:
        from modules.forex.forex_service import get_forex_service
        service = get_forex_service(db=db)
        cc = service.get_command_center()
        snapshot["raw"]["command_center"] = cc
        if isinstance(cc, dict):
            if not snapshot["market_regime"]:
                snapshot["market_regime"] = (
                    cc.get("market_regime")
                    or cc.get("macro_regime")
                    or cc.get("regime")
                    or cc
                )
    except Exception as exc:
        snapshot["raw"]["command_center_error"] = str(exc)

    # Currency strength (live: computed from real FX quotes)
    try:
        from modules.forex.forex_currency_strength_engine import get_forex_currency_strength_engine
        strength = get_forex_currency_strength_engine()
        if hasattr(strength, "command_center_payload"):
            data = strength.command_center_payload(force_refresh=force_refresh)
        elif hasattr(strength, "scan_currencies"):
            data = strength.scan_currencies(force_refresh=force_refresh)
        elif hasattr(strength, "analyze"):
            data = strength.analyze(force_refresh=force_refresh)
        else:
            data = {}
        snapshot["raw"]["currency_strength"] = data
        snapshot["currency_strength"] = _normalize_strength(data)
    except Exception as exc:
        snapshot["raw"]["currency_strength_error"] = str(exc)

    # Market regime: if the terminal/service didn't supply one, compute a real
    # regime from live currency strength rather than defaulting to a fixed
    # value. This is a genuine calculation (forex_macro_regime_engine), not a
    # canned placeholder.
    if not snapshot["market_regime"]:
        try:
            from modules.forex.forex_macro_regime_engine import get_forex_macro_regime_engine
            regime_engine = get_forex_macro_regime_engine()
            regime_data = regime_engine.analyze(force_refresh=force_refresh)
            snapshot["raw"]["macro_regime"] = regime_data
            if isinstance(regime_data, dict):
                snapshot["market_regime"] = regime_data
        except Exception as exc:
            snapshot["raw"]["macro_regime_error"] = str(exc)

    # Institutional scanner / recommendations (live: derived from the alpha
    # model, which runs against real quotes)
    try:
        from modules.forex.forex_institutional_scanner import get_forex_institutional_scanner
        scanner = get_forex_institutional_scanner()
        scan = scanner.scan(force_refresh=force_refresh)
        snapshot["raw"]["institutional_scanner"] = scan
        recs = scan.get("top_institutional_trades") or scan.get("institutional_flow") or []
        snapshot["recommendations"].extend(_normalize_recommendations(recs))
    except Exception as exc:
        snapshot["raw"]["institutional_scanner_error"] = str(exc)

    try:
        from modules.forex.forex_alpha_model import get_forex_alpha_model
        alpha = get_forex_alpha_model()
        if hasattr(alpha, "command_center_payload"):
            alpha_data = alpha.command_center_payload(force_refresh=force_refresh)
        elif hasattr(alpha, "run_alpha_model"):
            alpha_data = alpha.run_alpha_model(force_refresh=force_refresh)
        else:
            alpha_data = {}
        snapshot["raw"]["alpha_model"] = alpha_data
        snapshot["recommendations"].extend(_normalize_recommendations(alpha_data.get("signals", [])))
    except Exception as exc:
        snapshot["raw"]["alpha_error"] = str(exc)

    # Portfolio / orders / journal
    try:
        from modules.forex.forex_trading_desk import get_forex_trading_desk
        desk = get_forex_trading_desk(db=db)
        desk_data = desk.dashboard(
            portfolio_id=portfolio_id,
            user_id=user_id,
            tenant_id=tenant_id,
            force_refresh=force_refresh,
        )
        snapshot["raw"]["trading_desk"] = desk_data
        if isinstance(desk_data, dict):
            snapshot["portfolio"] = desk_data.get("portfolio", {}) or {}
            snapshot["open_orders"] = desk_data.get("open_orders", []) or []
            snapshot["filled_orders"] = desk_data.get("filled_orders", []) or []
            snapshot["journal"] = desk_data.get("journal", {}).get("trades", []) if isinstance(desk_data.get("journal"), dict) else []
            snapshot["performance"] = desk_data.get("performance", {}) or {}
            if not snapshot.get("provider_health"):
                snapshot["provider_health"] = _normalize_provider_health(desk_data.get("provider_health", {}))
    except Exception as exc:
        snapshot["raw"]["trading_desk_error"] = str(exc)

    try:
        from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager
        pm = get_forex_portfolio_manager(db=db)
        portfolio = pm.portfolio_summary(
            portfolio_id=portfolio_id,
            user_id=user_id,
            tenant_id=tenant_id,
            force_refresh=force_refresh,
        )
        if isinstance(portfolio, dict):
            snapshot["portfolio"] = snapshot["portfolio"] or portfolio
            snapshot["positions"] = (
                portfolio.get("positions")
                or portfolio.get("open_positions")
                or portfolio.get("position_rows")
                or []
            )
    except Exception as exc:
        snapshot["raw"]["portfolio_error"] = str(exc)

    # Equity curve (live: built from persisted equity snapshots, not a chart
    # of synthetic numbers)
    try:
        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
        pe = get_forex_portfolio_engine(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )
        pe_snapshot = pe.get_terminal_snapshot(
            portfolio_id=portfolio_id,
            refresh=force_refresh,
            persist=False,
            include_orders=False,
            include_history=True,
        )
        pe_snapshot = pe_snapshot if isinstance(pe_snapshot, dict) else {}
        pe_performance = pe_snapshot.get("performance", {}) or {}
        snapshot["raw"]["equity_curve_source"] = pe_performance
        snapshot["equity_curve"] = pe_performance.get("equity_curve", []) or []
        if not snapshot["performance"]:
            snapshot["performance"] = pe_performance
    except Exception as exc:
        snapshot["raw"]["equity_curve_error"] = str(exc)

    try:
        from modules.forex.forex_provider_health import get_forex_provider_health
        ph = get_forex_provider_health().summary()
        snapshot["raw"]["provider_health"] = ph
        snapshot["provider_health"] = _normalize_provider_health(ph)
    except Exception as exc:
        snapshot["raw"]["provider_health_error"] = str(exc)

    # AI briefing
    try:
        from modules.forex.forex_ai_assistant import get_forex_ai_assistant
        ai = get_forex_ai_assistant(db=db)
        briefing = ai.daily_briefing()
        snapshot["ai_briefing"] = briefing if isinstance(briefing, dict) else {}
        snapshot["raw"]["ai_briefing"] = briefing
    except Exception as exc:
        snapshot["raw"]["ai_error"] = str(exc)
        snapshot["ai_briefing"] = {}

    # Macro / central banks -- live via FRED (providers/fred_provider.py).
    try:
        from modules.forex.forex_central_bank_engine import get_forex_central_bank_engine
        cb = get_forex_central_bank_engine()
        cb_data = cb.analyze() if hasattr(cb, "analyze") else {}
        snapshot["raw"]["central_banks"] = cb_data
        snapshot["central_bank_events"] = _normalize_central_bank_rates(cb_data)
        if isinstance(cb_data, dict) and cb_data.get("fred_configured") and snapshot["central_bank_events"]:
            snapshot["data_status"]["central_bank_events"] = "live"
        elif isinstance(cb_data, dict) and not cb_data.get("fred_configured"):
            snapshot["data_status"]["central_bank_events"] = "no_api_key"
        else:
            snapshot["data_status"]["central_bank_events"] = "error"
    except Exception as exc:
        snapshot["raw"]["central_bank_error"] = str(exc)
        snapshot["data_status"]["central_bank_events"] = "error"

    try:
        from modules.forex.forex_macro_calendar_engine import get_forex_macro_calendar_engine
        calendar_engine = get_forex_macro_calendar_engine()
        calendar_data = calendar_engine.calendar() if hasattr(calendar_engine, "calendar") else {}
        snapshot["raw"]["economic_calendar"] = calendar_data
        snapshot["economic_calendar"] = _normalize_events(calendar_data)
        if isinstance(calendar_data, dict) and calendar_data.get("fred_configured") and snapshot["economic_calendar"]:
            snapshot["data_status"]["economic_calendar"] = "live"
        elif isinstance(calendar_data, dict) and not calendar_data.get("fred_configured"):
            snapshot["data_status"]["economic_calendar"] = "no_api_key"
        else:
            snapshot["data_status"]["economic_calendar"] = "error"
    except Exception as exc:
        snapshot["raw"]["economic_calendar_error"] = str(exc)
        snapshot["data_status"]["economic_calendar"] = "error"

    snapshot["alerts"] = _build_alerts(snapshot)

    return snapshot


def _normalize_strength(data: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    if isinstance(data, dict):
        candidates = (
            data.get("currency_strength")
            or data.get("strength")
            or data.get("rankings")
            or data.get("currencies")
            or data.get("scores")
        )

        if isinstance(candidates, dict):
            for ccy, val in candidates.items():
                if isinstance(val, dict):
                    score = val.get("strength_score") or val.get("score") or val.get("normalized_score") or val.get("value")
                    trend = val.get("trend") or val.get("direction")
                else:
                    score = val
                    trend = "UP" if _safe_float(score) >= 60 else "DOWN"
                rows.append({"currency": str(ccy).upper(), "score": _safe_float(score), "trend": trend})
        elif isinstance(candidates, list):
            for item in candidates:
                if isinstance(item, dict):
                    ccy = item.get("currency") or item.get("code") or item.get("symbol")
                    rows.append({
                        "currency": str(ccy or "").upper(),
                        "score": _safe_float(item.get("strength_score") or item.get("score") or item.get("normalized_score")),
                        "trend": item.get("trend") or item.get("direction") or "",
                    })

        # Previously, whenever the reported strongest/weakest currency
        # wasn't already present in the real per-currency rows, this
        # appended a fabricated 100.0 / 35.0 score for it -- which is why
        # the strongest currency always displayed exactly "100" regardless
        # of its real strength reading. Now it only adds strongest/weakest
        # placeholders using their own real score field when the source
        # payload actually provides one; otherwise it leaves them out
        # rather than inventing a number.
        strongest_obj = data.get("strongest_currency")
        weakest_obj = data.get("weakest_currency")
        strongest = strongest_obj.get("currency") if isinstance(strongest_obj, dict) else strongest_obj
        weakest = weakest_obj.get("currency") if isinstance(weakest_obj, dict) else weakest_obj
        if strongest and not any(r["currency"] == str(strongest).upper() for r in rows):
            real_score = strongest_obj.get("strength_score") if isinstance(strongest_obj, dict) else None
            if real_score is not None:
                rows.append({"currency": str(strongest).upper(), "score": _safe_float(real_score), "trend": "UP"})
        if weakest and not any(r["currency"] == str(weakest).upper() for r in rows):
            real_score = weakest_obj.get("strength_score") if isinstance(weakest_obj, dict) else None
            if real_score is not None:
                rows.append({"currency": str(weakest).upper(), "score": _safe_float(real_score), "trend": "DOWN"})

    rows = [r for r in rows if r.get("currency")]
    rows.sort(key=lambda r: _safe_float(r.get("score")), reverse=True)
    return rows[:10]


def _provider_status_row(item: Dict[str, Any], name: Optional[str] = None) -> Dict[str, Any]:
    """
    Real router provider rows (forex_provider_router.as_row()) carry
    health_score/success_count/failure_count/avg_latency_ms, not a
    "status"/"latency"/"success" field -- so item.get("status") or
    item.get("health") or "UNKNOWN" always fell through to "UNKNOWN" for
    every provider, even a perfectly healthy one. Status/Latency/Success
    are now derived from the real fields when present, and "UNTESTED" (not
    "UNKNOWN") is reported honestly when a provider hasn't been called yet.
    """
    explicit_status = item.get("status") or item.get("health")
    if explicit_status:
        status = explicit_status
    else:
        success_count = item.get("success_count")
        failure_count = item.get("failure_count")
        health_score = item.get("health_score")
        if success_count is None and failure_count is None and health_score is None:
            status = "UNKNOWN"
        elif not (success_count or failure_count):
            status = "UNTESTED"
        else:
            score = _safe_float(health_score, 0.0)
            status = "HEALTHY" if score >= 80 else "DEGRADED" if score >= 50 else "UNHEALTHY"

    latency = item.get("latency_ms") or item.get("latency")
    if latency is None:
        avg_latency = item.get("avg_latency_ms")
        latency = f"{avg_latency:.0f} ms" if avg_latency else "-"

    success = item.get("success_rate") or item.get("success")
    if success is None:
        s, f = item.get("success_count"), item.get("failure_count")
        total = (s or 0) + (f or 0)
        success = f"{(s / total * 100):.1f}%" if total else "-"

    return {
        "provider": item.get("provider") or name or "-",
        "status": status,
        "latency": latency,
        "success": success,
    }


def _normalize_provider_health(data: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                rows.append(_provider_status_row(item))
    elif isinstance(data, dict):
        providers = data.get("providers") or data.get("provider_health") or data.get("summary") or data
        if isinstance(providers, dict):
            for name, item in providers.items():
                if isinstance(item, dict):
                    rows.append(_provider_status_row(item, name=name))
                elif isinstance(item, str):
                    rows.append({"provider": name, "status": item, "latency": "-", "success": "-"})
    return rows[:8]


def _normalize_recommendations(rows: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    if not isinstance(rows, list):
        return normalized

    for item in rows:
        if not isinstance(item, dict):
            continue
        pair = _normalize_pair(item.get("pair") or item.get("symbol") or "EUR/USD")
        rec = item.get("recommendation") or item.get("direction") or item.get("signal") or "WATCH"
        score = item.get("confidence") or item.get("confidence_score") or item.get("conviction_score") or item.get("alpha_score") or 0
        side = "BUY" if any(x in str(rec).upper() for x in ["BUY", "LONG", "BULL"]) else "SELL" if any(x in str(rec).upper() for x in ["SELL", "SHORT", "BEAR"]) else "WATCH"
        normalized.append({
            "pair": pair,
            "side": side,
            "recommendation": rec,
            "confidence": round(_safe_float(score), 1),
            "entry": item.get("entry") or item.get("entry_price") or item.get("current_price") or "-",
            "stop": item.get("stop") or item.get("stop_loss") or item.get("stop_price") or "-",
            "target": item.get("target") or item.get("take_profit") or item.get("target_price") or "-",
            "bias": item.get("institutional_bias") or item.get("bias") or side,
            "risk_reward": item.get("risk_reward") or "-",
        })

    # Deduplicate by pair / side
    seen = set()
    out = []
    for row in normalized:
        key = (row["pair"], row["side"])
        if key not in seen:
            out.append(row)
            seen.add(key)
    return out[:8]


def _normalize_events(data: Any) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    candidates = []
    if isinstance(data, dict):
        candidates = data.get("events") or data.get("central_bank_events") or data.get("calendar") or []
    elif isinstance(data, list):
        candidates = data
    if isinstance(candidates, list):
        for item in candidates:
            if isinstance(item, dict):
                events.append({
                    "date": item.get("date") or item.get("time") or "-",
                    "currency": item.get("currency") or item.get("ccy") or "-",
                    "event": item.get("event") or item.get("title") or item.get("name") or "-",
                    "impact": item.get("impact") or item.get("importance") or "Medium",
                })
    return events[:8]


def _normalize_central_bank_rates(data: Any) -> List[Dict[str, Any]]:
    """
    Shape forex_central_bank_engine's live FRED-backed rows for display:
    currency, policy rate, bias, as-of date, and whether the series is the
    bank's exact published rate or the closest live proxy available.
    """
    rows: List[Dict[str, Any]] = []
    banks = data.get("central_banks") if isinstance(data, dict) else None
    if not isinstance(banks, list):
        return rows

    for item in banks:
        if not isinstance(item, dict):
            continue
        if item.get("error"):
            rows.append({
                "central_bank": item.get("central_bank", "-"),
                "currency": item.get("currency", "-"),
                "policy_rate": "unavailable",
                "bias": "-",
                "asof": "-",
                "note": item.get("error"),
            })
            continue
        rate = item.get("policy_rate")
        rows.append({
            "central_bank": item.get("central_bank", "-"),
            "currency": item.get("currency", "-"),
            "policy_rate": f"{rate:.2f}%" if isinstance(rate, (int, float)) else "-",
            "bias": item.get("policy_bias", "-"),
            "asof": item.get("policy_rate_asof", "-"),
            "note": "proxy (closest live series)" if item.get("proxy") else "official rate",
        })
    return rows


def _build_alerts(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Alerts are derived only from real recommendations produced this session.
    When there are none, this returns an empty list -- the UI shows an
    honest "no rows available" state rather than two invented alerts.
    """
    recs = snapshot.get("recommendations") or []
    alerts = []
    for rec in recs[:3]:
        pair = rec.get("pair", "FX")
        side = rec.get("side", "WATCH")
        conf = _safe_float(rec.get("confidence"))
        alerts.append({
            "time": datetime.now(timezone.utc).strftime("%H:%M"),
            "alert": f"{pair} {side} setup confidence {conf:.0f}%",
            "severity": "High" if conf >= 85 else "Medium",
        })
    return alerts


def _market_summary(snapshot: Dict[str, Any]) -> Tuple[str, float, str, str, float]:
    """
    Derive the top-ribbon market summary strictly from live data. When a
    value genuinely is not available yet, this returns "N/A" / 0.0 rather
    than a fabricated placeholder -- callers must render that honestly.
    """
    regime_obj = snapshot.get("market_regime") or {}
    regime: Any = "N/A"
    macro_score = 0.0

    if isinstance(regime_obj, dict):
        regime = (
            regime_obj.get("macro_regime")
            or regime_obj.get("market_regime")
            or regime_obj.get("regime")
            or regime_obj.get("status")
            or regime
        )
        macro_score = _safe_float(
            regime_obj.get("macro_score")
            or regime_obj.get("score")
            or regime_obj.get("confidence")
            or macro_score
        )
    elif isinstance(regime_obj, str) and regime_obj:
        regime = regime_obj

    strength = snapshot.get("currency_strength") or []
    strongest = strength[0]["currency"] if strength else "N/A"
    weakest = sorted(strength, key=lambda r: _safe_float(r.get("score")))[0]["currency"] if strength else "N/A"

    recs = snapshot.get("recommendations") or []
    confidences = [_safe_float(r.get("confidence")) for r in recs]
    ai_conf = max(confidences) if confidences else 0.0

    return str(regime).replace("_", "-").upper(), macro_score, strongest, weakest, ai_conf


def _portfolio_metrics(snapshot: Dict[str, Any]) -> Tuple[int, float, float, float]:
    """
    Read live portfolio metrics only. If the portfolio backend genuinely has
    nothing yet (e.g. no live account/position sync configured), this returns
    honest zeros -- it no longer substitutes a fabricated demo account
    ($368,452.17 equity / 12 phantom positions) when the account is empty.
    """
    portfolio = snapshot.get("portfolio") or {}
    positions = snapshot.get("positions") or []

    if isinstance(portfolio, dict):
        summary = portfolio.get("summary") if isinstance(portfolio.get("summary"), dict) else portfolio
        open_positions = (
            summary.get("open_positions")
            or summary.get("positions")
            or summary.get("position_count")
            or len(positions)
            or 0
        )
        daily_pnl = (
            summary.get("daily_pnl")
            or summary.get("unrealized_pnl")
            or summary.get("pnl")
            or 0
        )
        daily_pct = summary.get("daily_pnl_pct") or summary.get("pnl_pct") or 0
        equity = summary.get("equity") or summary.get("portfolio_value") or summary.get("total_value") or 0
    else:
        open_positions, daily_pnl, daily_pct, equity = 0, 0, 0, 0

    return _safe_int(open_positions), _safe_float(daily_pnl), _safe_float(daily_pct), _safe_float(equity)


def _render_top_ribbon(snapshot: Dict[str, Any]) -> None:
    regime, macro_score, strongest, weakest, ai_conf = _market_summary(snapshot)
    open_positions, daily_pnl, daily_pct, equity = _portfolio_metrics(snapshot)

    cols = st.columns([1.35, 1.25, 1.25, 1.2, 1.05, 1.05, 1.25, 1.15])
    with cols[0]:
        _metric_card("Market Regime", regime, f"Macro Score: {macro_score:.0f}/100", regime, macro_score)
    with cols[1]:
        _metric_card("Strongest Currency", f"{_currency_flag(strongest)} {strongest}", "Strength leader", "BUY", 100)
    with cols[2]:
        _metric_card("Weakest Currency", f"{_currency_flag(weakest)} {weakest}", "Weakness leader", "SELL", 42)
    with cols[3]:
        _metric_card("AI Confidence", f"{ai_conf:.0f}%", "Institutional model", "HIGH", ai_conf)
    with cols[4]:
        _metric_card("Open Positions", open_positions, "Active exposure", "READY", 68)
    with cols[5]:
        _metric_card("Daily P/L", _fmt_money(daily_pnl), _fmt_pct(daily_pct), "BUY" if daily_pnl >= 0 else "SELL", 78)
    with cols[6]:
        _metric_card("Equity", f"${equity:,.2f}", "Paper / live account", "READY", 72)
    with cols[7]:
        _metric_card("Server Time", datetime.now(timezone.utc).strftime("%H:%M:%S UTC"), datetime.now(timezone.utc).strftime("%b %d, %Y"), "READY", None)


def _render_left_panel(snapshot: Dict[str, Any]) -> None:
    st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
    _panel_title("Currency Strength", "vs USD")
    _progress_table(snapshot.get("currency_strength", []), "currency", "score", "trend")
    st.markdown("</div>", unsafe_allow_html=True)

    regime, macro_score, _, _, _ = _market_summary(snapshot)
    st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
    _panel_title("Macro Environment", regime)
    st.markdown(f"**Regime:** <span class='{_badge_class(regime)}'>{regime}</span>", unsafe_allow_html=True)
    st.progress(max(0, min(100, int(macro_score))) / 100)
    st.write(f"Macro Score: **{macro_score:.0f} / 100**")
    st.write("Risk Appetite: ", "Low" if "OFF" in regime.upper() else "High")
    st.write("Liquidity: ", "Constrained" if "OFF" in regime.upper() else "Normal")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
    _panel_title("Provider Health", "live")
    _render_df(snapshot.get("provider_health", []), height=190)
    st.markdown("</div>", unsafe_allow_html=True)


def _price_chart(pair: str = "EUR/USD"):
    """
    Build an intraday price chart for `pair` from the live history pipeline
    (forex_history_service -> provider router -> real market data provider).
    Returns (None, reason) instead of a chart whenever real history rows
    aren't available -- it never draws a synthetic price path.
    """
    if go is None:
        return None, "Plotly is unavailable."

    try:
        from modules.forex.forex_history_service import get_forex_history_service
        history_service = get_forex_history_service()
        payload = history_service.fetch_from_router(pair, interval="1h")
    except Exception as exc:
        return None, f"Live chart unavailable: {exc}"

    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not rows:
        error = payload.get("error") if isinstance(payload, dict) else None
        return None, error or f"No live history returned for {pair} yet."

    x = [row.get("asof") or row.get("date") for row in rows]
    closes = [_safe_float(row.get("close")) for row in rows]
    volumes = [_safe_float(row.get("volume")) for row in rows]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=closes, mode="lines", name=pair, line=dict(width=2)))
    if any(volumes):
        fig.add_trace(go.Bar(x=x, y=volumes, name="Volume", yaxis="y2", opacity=0.25))
    fig.update_layout(
        template="plotly_dark",
        height=390,
        margin=dict(l=10, r=10, t=28, b=18),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title=f"{pair} · Live History",
        yaxis=dict(title="Price"),
        yaxis2=dict(title="Vol", overlaying="y", side="right", showgrid=False, visible=False),
        legend=dict(orientation="h"),
    )
    return fig, None


def _top_of_book(pair: str = "EUR/USD"):
    """
    Real top-of-book bid/ask/mid from the live quote pipeline. There is no
    broker/ECN market-depth feed wired into this codebase, so this
    deliberately does not synthesize a multi-level order book -- it returns
    only what a live quote actually gives us.
    """
    try:
        from modules.forex.forex_price_service import get_forex_price_service
        quote = get_forex_price_service().get_quote(pair)
    except Exception as exc:
        return None, f"Quote unavailable: {exc}"

    if not isinstance(quote, dict) or quote.get("error"):
        error = quote.get("error") if isinstance(quote, dict) else None
        return None, error or "No live quote available."

    bid = quote.get("bid")
    ask = quote.get("ask")
    mid = quote.get("mid")
    if mid is None and bid is not None and ask is not None:
        mid = (_safe_float(bid) + _safe_float(ask)) / 2

    provider = quote.get("provider", "-")
    rows = []
    if ask is not None:
        rows.append({"price": ask, "side": "Ask", "provider": provider})
    if mid is not None:
        rows.append({"price": mid, "side": "Mid", "provider": provider})
    if bid is not None:
        rows.append({"price": bid, "side": "Bid", "provider": provider})

    if not rows:
        return None, "No live quote available."
    return rows, None


def _render_recommendation_cards(recommendations: List[Dict[str, Any]]) -> None:
    if not recommendations:
        st.info("No AI recommendations available.")
        return

    cols = st.columns(min(4, max(1, len(recommendations[:4]))))
    for idx, rec in enumerate(recommendations[:4]):
        side = str(rec.get("side", "WATCH")).upper()
        cls = "fx-rec-card-buy" if side == "BUY" else "fx-rec-card-sell" if side == "SELL" else ""
        with cols[idx % len(cols)]:
            st.markdown(f'<div class="fx-rec-card {cls}">', unsafe_allow_html=True)
            st.markdown(
                f"**<span class='{_badge_class(side)}'>{side}</span> {rec.get('pair','-')}**",
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns(2)
            c1.caption("Entry")
            c1.write(rec.get("entry", "-"))
            c2.caption("Target")
            c2.write(rec.get("target", "-"))
            c1.caption("Stop")
            c1.write(rec.get("stop", "-"))
            c2.caption("Confidence")
            c2.write(f"**{_safe_float(rec.get('confidence')):.0f}%**")
            st.caption(f"Bias: {rec.get('bias', '-')}")
            st.markdown("</div>", unsafe_allow_html=True)


def _render_center_panel(snapshot: Dict[str, Any]) -> None:
    chart_pair = st.session_state.get("fx_inst_trade_pair", "EUR/USD")

    top_left, top_right = st.columns([2.2, 1])
    with top_left:
        st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
        _panel_title("Live Trading Desk", chart_pair)
        fig, chart_error = _price_chart(chart_pair)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(chart_error or "No live chart data available.")
        st.markdown("</div>", unsafe_allow_html=True)

    with top_right:
        st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
        _panel_title("Top of Book", chart_pair)
        top_of_book, book_error = _top_of_book(chart_pair)
        if top_of_book:
            _render_df(top_of_book, height=150)
        else:
            st.info(book_error or "No live quote available.")
        st.caption("Full L2 order-book depth requires a broker/ECN market-depth feed, which isn't connected -- only the live top-of-book quote is shown above.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
        _panel_title("Trade Ticket", "paper")
        pair = st.selectbox("Trade Pair", DEFAULT_PAIRS, key="fx_inst_trade_pair")
        side = st.radio("Trade Side", ["Buy", "Sell"], horizontal=True, key="fx_inst_trade_side")
        lots = st.number_input("Size (Lots)", min_value=0.01, value=1.00, step=0.01, key="fx_inst_trade_lots")
        risk = st.number_input("Risk %", min_value=0.1, value=1.0, step=0.1, key="fx_inst_trade_risk")
        if st.button(f"{side} {lots:.2f} {pair}", use_container_width=True, key="fx_inst_submit_ticket"):
            try:
                from modules.forex.forex_terminal_api import get_forex_terminal_api
                result = get_forex_terminal_api().submit_order(pair=pair, side=side.upper(), units=lots * 100000, risk_pct=risk)
                st.success("Order submitted.")
                st.json(result)
            except Exception as exc:
                st.error(f"Order submission failed: {exc}")
        st.caption("Est. margin and pip value depend on broker configuration.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
    _panel_title("AI Trade Recommendations", f"Updated {datetime.now(timezone.utc).strftime('%H:%M UTC')}")
    _render_recommendation_cards(snapshot.get("recommendations", []))
    st.markdown("</div>", unsafe_allow_html=True)


def _briefing_text(snapshot: Dict[str, Any]) -> str:
    regime, _, strongest, weakest, ai_conf = _market_summary(snapshot)
    raw = snapshot.get("ai_briefing") or {}

    if isinstance(raw, dict):
        narrative = raw.get("briefing") or raw.get("summary") or raw.get("narrative")
        if narrative:
            return str(narrative)

    if regime == "N/A" or strongest == "N/A" or weakest == "N/A":
        return "Live market-regime and currency-strength data isn't available yet -- check provider health below."

    return (
        f"Markets remain in a **{regime}** regime. "
        f"{_currency_flag(strongest)} **{strongest}** is currently the strongest currency, while "
        f"{_currency_flag(weakest)} **{weakest}** is the weakest. "
        f"AI confidence is running near **{ai_conf:.0f}%**, favoring selective institutional setups and strict risk control."
    )


def _render_right_panel(snapshot: Dict[str, Any]) -> None:
    st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
    _panel_title("AI Market Briefing", datetime.now(timezone.utc).strftime("%H:%M UTC"))
    st.markdown(_briefing_text(snapshot))
    regime, _, strongest, weakest, _ = _market_summary(snapshot)
    if strongest != "N/A" and weakest != "N/A":
        st.caption("Key Takeaways")
        st.markdown(
            f"""
- {strongest} remains a leadership currency
- {weakest} remains under pressure
- {regime} conditions favor disciplined sizing
- Watch central-bank and inflation catalysts
            """
        )
    st.markdown("</div>", unsafe_allow_html=True)

    data_status = snapshot.get("data_status", {})

    _STATUS_CHIP = {"live": "live · FRED", "no_api_key": "not connected", "error": "error", "unknown": "unknown"}
    _STATUS_CAPTION = {
        "no_api_key": "FRED_API_KEY isn't configured yet -- add it to enable this live feed.",
        "error": "The live FRED lookup failed this refresh -- see Developer/Debug for details.",
    }

    st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
    cal_status = data_status.get("economic_calendar", "unknown")
    _panel_title("Economic Calendar", _STATUS_CHIP.get(cal_status, cal_status))
    if cal_status != "live":
        st.caption(_STATUS_CAPTION.get(cal_status, "Live status unknown."))
    else:
        st.caption("Live FRED release calendar -- USD releases only (see Developer/Debug for coverage notes).")
    _render_df(snapshot.get("economic_calendar", []), height=180)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
    cb_status = data_status.get("central_bank_events", "unknown")
    _panel_title("Central Bank Policy Rates", _STATUS_CHIP.get(cb_status, cb_status))
    if cb_status != "live":
        st.caption(_STATUS_CAPTION.get(cb_status, "Live status unknown."))
    else:
        st.caption("Live FRED policy rates -- rows marked 'proxy' use the closest live series for that bank, not its exact published rate.")
    _render_df(snapshot.get("central_bank_events", []), height=170)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
    _panel_title("Alerts", str(len(snapshot.get("alerts", []))))
    _render_df(snapshot.get("alerts", []), height=160)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_bottom_panel(snapshot: Dict[str, Any]) -> None:
    st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
    tab_positions, tab_orders, tab_journal, tab_exec, tab_curve = st.tabs(
        ["Positions", "Orders", "Journal", "Executions", "Equity Curve"]
    )

    with tab_positions:
        _render_df(snapshot.get("positions") or [], height=230)

    with tab_orders:
        _render_df(snapshot.get("open_orders") or [], height=230)

    with tab_journal:
        _render_df(snapshot.get("journal") or [], height=230)

    with tab_exec:
        _render_df(snapshot.get("filled_orders") or [], height=230)

    with tab_curve:
        equity_curve = snapshot.get("equity_curve") or []
        if go is not None and equity_curve:
            x = [row.get("date") for row in equity_curve]
            y = [_safe_float(row.get("equity")) for row in equity_curve]
            fig = go.Figure(go.Scatter(x=x, y=y, mode="lines", fill="tozeroy", name="Equity"))
            fig.update_layout(template="plotly_dark", height=230, margin=dict(l=5, r=5, t=20, b=5), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        elif go is None:
            st.info("Plotly unavailable.")
        else:
            st.info("No equity history available yet.")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_debug(snapshot: Dict[str, Any]) -> None:
    with st.expander("Developer / Debug", expanded=False):
        tabs = st.tabs(["JSON View", "Raw Sources", "System Status"])
        with tabs[0]:
            st.json(snapshot)
        with tabs[1]:
            st.json(snapshot.get("raw", {}))
        with tabs[2]:
            st.write("Generated at:", snapshot.get("generated_at"))
            st.write("Status: Operational")


def render_institutional_terminal_view(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    snapshot = _extract_snapshot(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
        force_refresh=force_refresh,
    )

    if st is None:
        return snapshot

    _terminal_css()
    st.markdown('<div class="fx-shell">', unsafe_allow_html=True)

    header_left, header_right = st.columns([5, 1])
    with header_left:
        st.markdown("## 🌍 Forex Institutional Terminal")
        st.caption(f"Live • {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
    with header_right:
        if st.button("↻ Refresh", use_container_width=True, key="fx_inst_refresh"):
            snapshot = _extract_snapshot(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
                force_refresh=True,
            )

    _render_top_ribbon(snapshot)

    st.divider()

    workspace = st.radio(
        "Workspace",
        [
            "Trading Desk",
            "Command Center",
            "Portfolio",
            "Orders",
            "Risk",
            "Performance",
            "Journal",
            "AI Briefing",
            "Provider Health",
        ],
        horizontal=True,
        key="forex_institutional_terminal_workspace",
    )

    if workspace == "Trading Desk":
        left, center, right = st.columns([1.05, 2.65, 1.25])
        with left:
            _render_left_panel(snapshot)
        with center:
            _render_center_panel(snapshot)
        with right:
            _render_right_panel(snapshot)
        _render_bottom_panel(snapshot)
        _render_debug(snapshot)

    elif workspace == "Command Center":
        left, center, right = st.columns([1.1, 2.2, 1.2])
        with left:
            _render_left_panel(snapshot)
        with center:
            st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
            _panel_title("Institutional Matrix", "ranked")
            rec_df = _make_dataframe(snapshot.get("recommendations", []))
            _render_df(rec_df, height=420)
            st.markdown("</div>", unsafe_allow_html=True)
        with right:
            _render_right_panel(snapshot)
        _render_debug(snapshot)

    elif workspace == "Portfolio":
        _render_top_ribbon(snapshot)
        _render_bottom_panel(snapshot)
        _render_debug(snapshot)

    elif workspace == "Orders":
        st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
        _panel_title("Orders", "open / filled")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Open Orders")
            _render_df(snapshot.get("open_orders", []), height=360)
        with c2:
            st.subheader("Filled Orders")
            _render_df(snapshot.get("filled_orders", []), height=360)
        st.markdown("</div>", unsafe_allow_html=True)
        _render_debug(snapshot)

    elif workspace == "AI Briefing":
        _render_right_panel(snapshot)
        st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
        _panel_title("AI Trade Recommendations", "model")
        _render_recommendation_cards(snapshot.get("recommendations", []))
        st.markdown("</div>", unsafe_allow_html=True)
        _render_debug(snapshot)

    elif workspace == "Provider Health":
        st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
        _panel_title("Provider Health", "routing")
        _render_df(snapshot.get("provider_health", []), height=420)
        st.markdown("</div>", unsafe_allow_html=True)
        _render_debug(snapshot)

    else:
        st.markdown('<div class="fx-card-tight">', unsafe_allow_html=True)
        _panel_title(workspace, "summary")
        st.info(f"{workspace} dashboard will be connected here. Developer JSON remains available below.")
        st.markdown("</div>", unsafe_allow_html=True)
        _render_debug(snapshot)

    st.markdown("</div>", unsafe_allow_html=True)
    return snapshot


def render_forex_institutional_command_center(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    db = kwargs.get("db")
    tenant_id = kwargs.get("tenant_id")
    user_id = kwargs.get("user_id")
    portfolio_id = kwargs.get("portfolio_id")

    if db is None and len(args) >= 1:
        db = args[0]
    if user_id is None and len(args) >= 2:
        user_id = args[1]

    return render_institutional_terminal_view(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
        force_refresh=kwargs.get("force_refresh", False),
    )


def render(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    return render_forex_institutional_command_center(*args, **kwargs)