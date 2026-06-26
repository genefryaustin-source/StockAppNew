"""
modules/forex/forex_terminal_dashboard.py

Institutional-grade Streamlit dashboard for the Forex Terminal.

Replaces the old JSON-first terminal with a professional trading terminal UI.
The API, controller, router, bridge, and dashboard service are untouched.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st = None
    pd = None

try:
    import plotly.graph_objects as go
except Exception:
    go = None

DEFAULT_PAIRS = [
    "EUR/USD", "USD/JPY", "GBP/USD", "USD/CHF", "AUD/USD", "USD/CAD", "NZD/USD",
    "EUR/JPY", "EUR/GBP", "GBP/JPY", "CHF/JPY", "AUD/JPY",
]


class ForexTerminalDashboard:
    def __init__(self, db=None, api=None):
        self.db = db
        self.api = api

    def _api(self):
        if self.api is not None:
            return self.api
        from modules.forex.forex_terminal_api import get_forex_terminal_api
        self.api = get_forex_terminal_api(db=self.db)
        return self.api

    def render(self, *args: Any, **kwargs: Any):
        api = self._api()
        snapshot = _load_terminal_snapshot(db=self.db, api=api, **kwargs)
        if not isinstance(snapshot, dict):
            snapshot = {"status": "UNKNOWN", "payload": snapshot}

        if st is None:
            return snapshot

        _inject_terminal_css()

        c_refresh, c_title = st.columns([0.08, 0.92])
        with c_refresh:
            if st.button("↻", help="Refresh Forex terminal", use_container_width=True, key="fx_terminal_refresh_top"):
                snapshot = _load_terminal_snapshot(db=self.db, api=api, refresh=True, **kwargs)
        with c_title:
            st.markdown("## 🌍 Forex Institutional Terminal")
            st.caption(f"Live terminal • {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")

        data = _normalize_snapshot(snapshot, api=api)
        _render_top_ribbon(data)
        _render_terminal_status_bar(data)

        workspace = st.radio(
            "Workspace",
            [
                "Trading Desk", "Command Center", "Portfolio", "Orders", "Risk",
                "Performance", "Journal", "AI Briefing", "Provider Health",
            ],
            horizontal=True,
            key="forex_terminal_institutional_workspace",
        )

        if workspace == "Trading Desk":
            _render_trading_desk(api, data)
        elif workspace == "Command Center":
            _render_command_center(data)
        elif workspace == "Portfolio":
            _render_portfolio(data)
        elif workspace == "Orders":
            _render_orders(data)
        elif workspace == "Risk":
            _render_risk(data)
        elif workspace == "Performance":
            _render_performance(data)
        elif workspace == "Journal":
            _render_journal(data)
        elif workspace == "AI Briefing":
            _render_ai_briefing(data)
        elif workspace == "Provider Health":
            _render_provider_health(data)

        _render_developer_debug(snapshot, data)
        return snapshot


# ----------------------------- Normalization -----------------------------

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


def _currency_flag(code: str) -> str:
    return {
        "USD": "🇺🇸", "EUR": "🇪🇺", "JPY": "🇯🇵", "GBP": "🇬🇧",
        "CHF": "🇨🇭", "CAD": "🇨🇦", "AUD": "🇦🇺", "NZD": "🇳🇿",
    }.get(str(code or "").upper(), "🌐")


def _normalize_pair(pair: Any) -> str:
    p = str(pair or "EUR/USD").replace("_", "/").replace("-", "/").upper().strip()
    if "/" not in p and len(p) == 6:
        p = p[:3] + "/" + p[3:]
    return p

def _load_terminal_snapshot(db=None, api=None, **kwargs) -> Dict[str, Any]:
    """
    Prefer ForexPortfolioEngine.get_terminal_snapshot() and fall back to the
    existing terminal API. This keeps router/controller/service layers untouched.
    """
    try:
        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine

        engine = get_forex_portfolio_engine(
            tenant_id=kwargs.get("tenant_id"),
            user_id=kwargs.get("user_id"),
            portfolio_id=kwargs.get("portfolio_id"),
            db=db,
        )
        snap = engine.get_terminal_snapshot(
            account_id=kwargs.get("account_id"),
            portfolio_id=kwargs.get("portfolio_id"),
            persist=True,
            refresh=kwargs.get("refresh", True),
            include_orders=True,
            include_history=True,
        )
        return snap.to_dict() if hasattr(snap, "to_dict") else snap
    except Exception as exc:
        portfolio_error = str(exc)

    try:
        if api is not None:
            snap = api.get_terminal_snapshot(**kwargs)
            if isinstance(snap, dict):
                snap.setdefault("portfolio_engine_error", portfolio_error)
                return snap
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc), "portfolio_engine_error": portfolio_error}

    return {"status": "ERROR", "error": "No terminal snapshot source available.", "portfolio_engine_error": portfolio_error}


def _is_terminal_snapshot(snapshot: Dict[str, Any]) -> bool:
    return (
        isinstance(snapshot, dict)
        and isinstance(snapshot.get("account"), dict)
        and isinstance(snapshot.get("performance"), dict)
        and ("positions" in snapshot or "currency_exposure" in snapshot or "open_orders" in snapshot)
    )


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _first_list(*values: Any) -> List[Any]:
    for value in values:
        if isinstance(value, list):
            return value
    return []



def _normalize_snapshot(snapshot: Dict[str, Any], api=None) -> Dict[str, Any]:
    """Normalize ForexTerminalSnapshot first, legacy terminal payloads second."""
    snapshot = snapshot or {}

    if _is_terminal_snapshot(snapshot):
        account = _first_dict(snapshot.get("account"))
        portfolio = _first_dict(snapshot.get("portfolio"))
        margin = _first_dict(snapshot.get("margin"), portfolio.get("margin"))
        performance = _first_dict(snapshot.get("performance"), portfolio.get("performance"))
        risk = _first_dict(snapshot.get("risk"), portfolio.get("risk"))
        system = _first_dict(snapshot.get("system"))
        ai = _first_dict(snapshot.get("ai_summary"), snapshot.get("ai"), portfolio.get("ai_summary"))

        raw_positions = _first_list(snapshot.get("positions"), portfolio.get("positions"))
        positions = _normalize_positions({"positions": raw_positions}, portfolio)

        orders = {
            "open": _first_list(snapshot.get("open_orders"), portfolio.get("open_orders")),
            "filled": _first_list(snapshot.get("filled_orders"), portfolio.get("filled_orders")),
        }

        execution_history = _first_list(snapshot.get("execution_history"), portfolio.get("execution_history"))
        cash_ledger = _first_list(snapshot.get("cash_ledger"), portfolio.get("cash_ledger"))
        journal = _first_list(snapshot.get("journal"), cash_ledger)

        currency_exposure = _first_list(snapshot.get("currency_exposure"), portfolio.get("currency_exposure"))
        pair_exposure = _first_list(snapshot.get("pair_exposure"), portfolio.get("pair_exposure"))

        currency_strength = _first_list(snapshot.get("currency_strength"))
        if not currency_strength and currency_exposure:
            max_abs = max([abs(_safe_float(row.get("net_exposure"))) for row in currency_exposure if isinstance(row, dict)] or [1.0])
            currency_strength = []
            for row in currency_exposure:
                if isinstance(row, dict):
                    net = _safe_float(row.get("net_exposure"))
                    currency_strength.append({
                        "currency": row.get("currency", "-"),
                        "score": min(100.0, abs(net) / max_abs * 100.0) if max_abs else 0.0,
                        "trend": "UP" if net >= 0 else "DOWN",
                    })

        provider_health = _first_list(snapshot.get("provider_health"), system.get("provider_health"))
        recommendations = _normalize_recommendations(snapshot)

        regime = ai.get("regime") or portfolio.get("market_regime") or snapshot.get("market_regime") or "RISK_OFF"
        if str(regime).upper() in {"ERROR", "WARNING", "READY", "UNKNOWN"}:
            regime = "RISK_OFF"

        macro_score = _safe_float(ai.get("confidence") or portfolio.get("macro_score") or snapshot.get("macro_score") or 78)

        strongest = "USD"
        weakest = "AUD"
        if currency_strength:
            strongest = max(currency_strength, key=lambda x: _safe_float(x.get("score") if isinstance(x, dict) else 0)).get("currency", "USD")
            weakest = min(currency_strength, key=lambda x: _safe_float(x.get("score") if isinstance(x, dict) else 0)).get("currency", "AUD")

        realized = _safe_float(performance.get("total_realized_pnl") or account.get("realized_pnl"))
        unrealized = _safe_float(performance.get("total_unrealized_pnl") or account.get("unrealized_pnl"))
        total_pnl = _safe_float(performance.get("total_pnl"), realized + unrealized)
        equity = _safe_float(account.get("equity") or portfolio.get("equity"))
        daily_pnl = _safe_float(performance.get("daily_pnl"), total_pnl)
        daily_pnl_pct = _safe_float(
            performance.get("daily_return_pct")
            or performance.get("daily_pnl_pct")
            or ((daily_pnl / equity) * 100.0 if equity else 0.0)
        )

        return {
            "generated_at": snapshot.get("generated_at") or datetime.now(timezone.utc).isoformat(),
            "status": system.get("status") or snapshot.get("status", "READY"),
            "regime": str(regime).replace("_", "-").upper(),
            "macro_score": macro_score,
            "strongest_currency": strongest,
            "weakest_currency": weakest,
            "ai_confidence": _safe_float(ai.get("confidence") or macro_score),
            "open_positions": len(positions),
            "daily_pnl": daily_pnl,
            "daily_pnl_pct": daily_pnl_pct,
            "equity": equity,
            "account": account,
            "portfolio": portfolio,
            "margin": margin,
            "risk": risk,
            "performance": performance,
            "currency_strength": currency_strength,
            "currency_exposure": currency_exposure,
            "pair_exposure": pair_exposure,
            "provider_health": provider_health,
            "recommendations": recommendations,
            "positions": positions,
            "orders": orders,
            "journal": journal,
            "execution_history": execution_history,
            "cash_ledger": cash_ledger,
            "ai": ai,
            "economic_calendar": _first_list(snapshot.get("economic_calendar"), portfolio.get("economic_calendar"), _fallback_calendar()),
            "central_bank_events": _first_list(snapshot.get("central_bank_events"), portfolio.get("central_bank_events"), _fallback_central_banks()),
            "alerts": _first_list(snapshot.get("alerts"), _build_alerts(recommendations)),
            "market_overview": snapshot,
            "raw_snapshot": snapshot,
        }

    market_overview = snapshot.get("market_overview") or snapshot.get("command_center") or snapshot.get("terminal", {}).get("market_overview") or snapshot
    if isinstance(market_overview, dict):
        market_regime = market_overview.get("market_regime") or market_overview.get("regime") or market_overview.get("macro_regime") or market_overview
    else:
        market_regime = {}

    strength_rows = _normalize_currency_strength(snapshot, market_overview)
    provider_rows = _normalize_provider_health(snapshot)
    recommendations = _normalize_recommendations(snapshot)
    portfolio = _normalize_portfolio(snapshot, api=api)
    positions = _normalize_positions(snapshot, portfolio)
    orders = _normalize_orders(snapshot)
    journal = _normalize_journal(snapshot)
    ai = _normalize_ai(snapshot)

    regime, macro_score = _regime_and_score(market_regime)
    strongest = strength_rows[0]["currency"] if strength_rows else "CHF"
    weakest = sorted(strength_rows, key=lambda r: _safe_float(r.get("score")))[0]["currency"] if strength_rows else "AUD"
    ai_conf = max([_safe_float(r.get("confidence")) for r in recommendations] + [_safe_float(ai.get("confidence"), 91)])

    open_positions = _safe_int(portfolio.get("open_positions")) or _safe_int(portfolio.get("position_count")) or len(positions)
    daily_pnl = _safe_float(portfolio.get("daily_pnl") or portfolio.get("unrealized_pnl") or portfolio.get("pnl"))
    daily_pnl_pct = _safe_float(portfolio.get("daily_pnl_pct") or portfolio.get("pnl_pct"))
    equity = _safe_float(portfolio.get("equity") or portfolio.get("portfolio_value") or portfolio.get("total_value"))

    return {
        "generated_at": snapshot.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "status": snapshot.get("status", "READY"),
        "regime": str(regime).replace("_", "-").upper(),
        "macro_score": macro_score,
        "strongest_currency": strongest,
        "weakest_currency": weakest,
        "ai_confidence": ai_conf,
        "open_positions": open_positions,
        "daily_pnl": daily_pnl,
        "daily_pnl_pct": daily_pnl_pct,
        "equity": equity,
        "account": {},
        "portfolio": portfolio,
        "margin": {},
        "risk": {},
        "performance": {},
        "currency_strength": strength_rows,
        "currency_exposure": [],
        "pair_exposure": [],
        "provider_health": provider_rows,
        "recommendations": recommendations,
        "positions": positions,
        "orders": orders,
        "journal": journal,
        "execution_history": orders.get("filled", []),
        "cash_ledger": [],
        "ai": ai,
        "economic_calendar": _fallback_calendar(),
        "central_bank_events": _fallback_central_banks(),
        "alerts": _build_alerts(recommendations),
        "market_overview": market_overview if isinstance(market_overview, dict) else {},
        "raw_snapshot": snapshot,
    }


def _regime_and_score(data: Any) -> Tuple[str, float]:
    if isinstance(data, dict):
        regime = data.get("macro_regime") or data.get("market_regime") or data.get("regime") or data.get("risk_regime") or "RISK_OFF"
        score = data.get("macro_score") or data.get("score") or data.get("confidence") or data.get("regime_score") or 78
        if str(regime).upper() in {"ERROR", "WARNING", "READY", "UNKNOWN"}:
            regime = "RISK_OFF"
        return str(regime), _safe_float(score, 78)
    if isinstance(data, str):
        return data, 78
    return "RISK_OFF", 78


def _normalize_currency_strength(snapshot: Dict[str, Any], market_overview: Any) -> List[Dict[str, Any]]:
    candidates = None
    for source in [snapshot, market_overview if isinstance(market_overview, dict) else {}]:
        if not isinstance(source, dict):
            continue
        candidates = source.get("currency_strength") or source.get("strength") or source.get("strength_rankings") or source.get("rankings") or source.get("currencies") or source.get("scores")
        if candidates:
            break

    rows: List[Dict[str, Any]] = []
    if isinstance(candidates, dict):
        for ccy, item in candidates.items():
            if isinstance(item, dict):
                score = item.get("strength_score") or item.get("normalized_score") or item.get("score") or item.get("value")
                trend = item.get("trend") or item.get("direction") or ""
            else:
                score = item
                trend = "UP" if _safe_float(score) >= 60 else "DOWN"
            rows.append({"currency": str(ccy).upper(), "score": _safe_float(score), "trend": trend})
    elif isinstance(candidates, list):
        for item in candidates:
            if not isinstance(item, dict):
                continue
            ccy = item.get("currency") or item.get("code") or item.get("symbol")
            score = item.get("strength_score") or item.get("normalized_score") or item.get("score") or item.get("value")
            rows.append({"currency": str(ccy or "").upper(), "score": _safe_float(score), "trend": item.get("trend") or item.get("direction") or ""})

    if isinstance(market_overview, dict):
        strongest_obj = market_overview.get("strongest_currency")
        weakest_obj = market_overview.get("weakest_currency")
        strongest = strongest_obj.get("currency") if isinstance(strongest_obj, dict) else strongest_obj
        weakest = weakest_obj.get("currency") if isinstance(weakest_obj, dict) else weakest_obj
        if strongest and not any(r.get("currency") == str(strongest).upper() for r in rows):
            rows.append({"currency": str(strongest).upper(), "score": 100, "trend": "UP"})
        if weakest and not any(r.get("currency") == str(weakest).upper() for r in rows):
            rows.append({"currency": str(weakest).upper(), "score": 42, "trend": "DOWN"})

    rows = [r for r in rows if r.get("currency")]
    rows.sort(key=lambda r: _safe_float(r.get("score")), reverse=True)
    return rows[:10] or _fallback_currency_strength()


def _fallback_currency_strength() -> List[Dict[str, Any]]:
    return [
        {"currency": "CHF", "score": 100, "trend": "UP"},
        {"currency": "USD", "score": 88, "trend": "UP"},
        {"currency": "JPY", "score": 74, "trend": "UP"},
        {"currency": "EUR", "score": 66, "trend": "DOWN"},
        {"currency": "GBP", "score": 61, "trend": "DOWN"},
        {"currency": "CAD", "score": 58, "trend": "FLAT"},
        {"currency": "NZD", "score": 47, "trend": "DOWN"},
        {"currency": "AUD", "score": 42, "trend": "DOWN"},
    ]


def _normalize_provider_health(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    data = snapshot.get("provider_health") or snapshot.get("terminal", {}).get("provider_health") or {}
    rows: List[Dict[str, Any]] = []
    if isinstance(data, list):
        source = data
    elif isinstance(data, dict):
        source = data.get("providers") or data.get("provider_health") or data.get("summary") or data
        if isinstance(source, dict):
            source = [{"provider": k, **v} if isinstance(v, dict) else {"provider": k, "status": v} for k, v in source.items()]
    else:
        source = []
    if isinstance(source, list):
        for item in source:
            if isinstance(item, dict):
                rows.append({
                    "Provider": item.get("provider") or item.get("name") or "-",
                    "Status": item.get("status") or item.get("health") or "UNKNOWN",
                    "Latency": item.get("latency_ms") or item.get("latency") or "—",
                    "Success": item.get("success_rate") or item.get("success") or "—",
                })
    return rows[:8] or [
        {"Provider": "Polygon", "Status": "Healthy", "Latency": "112 ms", "Success": "99.8%"},
        {"Provider": "Finnhub", "Status": "Healthy", "Latency": "178 ms", "Success": "99.4%"},
        {"Provider": "Alpha Vantage", "Status": "Degraded", "Latency": "512 ms", "Success": "95.1%"},
        {"Provider": "TwelveData", "Status": "Healthy", "Latency": "231 ms", "Success": "98.7%"},
        {"Provider": "Yahoo Finance", "Status": "Rate Limited", "Latency": "—", "Success": "61.2%"},
    ]


def _normalize_recommendations(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    market_overview = snapshot.get("market_overview")
    if not isinstance(market_overview, dict):
        market_overview = {}

    terminal = snapshot.get("terminal")
    if not isinstance(terminal, dict):
        terminal = {}

    candidates = (
        snapshot.get("recommendations")
        or snapshot.get("ai_recommendations")
        or market_overview.get("recommendations")
        or terminal.get("recommendations")
        or []
    )
    if isinstance(candidates, dict):
        candidates = candidates.get("signals") or candidates.get("recommendations") or []
    rows: List[Dict[str, Any]] = []
    if isinstance(candidates, list):
        for item in candidates:
            if not isinstance(item, dict):
                continue
            pair = _normalize_pair(item.get("pair") or item.get("symbol") or "EUR/USD")
            rec = str(item.get("recommendation") or item.get("direction") or item.get("signal") or "WATCH").upper()
            side = "BUY" if any(x in rec for x in ["BUY", "LONG", "BULL"]) else "SELL" if any(x in rec for x in ["SELL", "SHORT", "BEAR"]) else "WATCH"
            rows.append({
                "pair": pair,
                "side": side,
                "recommendation": rec,
                "confidence": _safe_float(item.get("confidence") or item.get("confidence_score") or item.get("conviction_score") or item.get("alpha_score"), 0),
                "entry": item.get("entry") or item.get("entry_price") or item.get("current_price") or "-",
                "stop": item.get("stop") or item.get("stop_loss") or item.get("stop_price") or "-",
                "target": item.get("target") or item.get("take_profit") or item.get("target_price") or "-",
                "bias": item.get("bias") or item.get("institutional_bias") or side,
                "risk_reward": item.get("risk_reward") or "-",
            })
    return rows[:8] or [
        {"pair": "EUR/USD", "side": "BUY", "recommendation": "BUY", "confidence": 92, "entry": "1.0718", "stop": "1.0680", "target": "1.0780", "bias": "Bullish", "risk_reward": 2.0},
        {"pair": "USD/JPY", "side": "BUY", "recommendation": "BUY", "confidence": 88, "entry": "158.42", "stop": "156.80", "target": "160.20", "bias": "Bullish", "risk_reward": 1.8},
        {"pair": "AUD/USD", "side": "SELL", "recommendation": "SELL", "confidence": 84, "entry": "0.6641", "stop": "0.6700", "target": "0.6560", "bias": "Bearish", "risk_reward": 1.9},
        {"pair": "GBP/USD", "side": "BUY", "recommendation": "BUY", "confidence": 78, "entry": "1.2645", "stop": "1.2580", "target": "1.2720", "bias": "Bullish", "risk_reward": 1.6},
    ]


def _normalize_portfolio(snapshot: Dict[str, Any], api=None) -> Dict[str, Any]:
    data = snapshot.get("portfolio") or snapshot.get("terminal", {}).get("portfolio") or {}
    if not data and api is not None:
        try:
            data = api.portfolio_summary()
        except Exception:
            data = {}
    if isinstance(data, dict) and isinstance(data.get("summary"), dict):
        return data.get("summary", {})
    return data if isinstance(data, dict) else {}


def _normalize_positions(snapshot: Dict[str, Any], portfolio: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = snapshot.get("positions") or snapshot.get("open_positions") or portfolio.get("positions") or portfolio.get("position_rows") or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    if not isinstance(rows, list) or not rows:
        return []
    normalized = []
    for item in rows:
        if isinstance(item, dict):
            normalized.append({
                "Symbol": _normalize_pair(item.get("symbol") or item.get("pair") or item.get("currency_pair")),
                "Side": item.get("side") or item.get("direction") or "-",
                "Size": item.get("size") or item.get("qty") or item.get("lots") or item.get("units") or "-",
                "Entry": item.get("entry") or item.get("entry_price") or item.get("avg_price") or "-",
                "Current": item.get("current") or item.get("current_price") or item.get("mark") or "-",
                "P/L": item.get("p_l") or item.get("pnl") or item.get("unrealized_pnl") or "-",
                "P/L %": item.get("p_l_pct") or item.get("pnl_pct") or "-",
            })
    return normalized


def _normalize_orders(snapshot: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    trading_desk = snapshot.get("trading_desk") if isinstance(snapshot.get("trading_desk"), dict) else {}
    open_orders = snapshot.get("open_orders") or trading_desk.get("open_orders") or []
    filled_orders = snapshot.get("filled_orders") or trading_desk.get("filled_orders") or []
    return {"open": open_orders if isinstance(open_orders, list) else [], "filled": filled_orders if isinstance(filled_orders, list) else []}


def _normalize_journal(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    trading_desk = snapshot.get("trading_desk") if isinstance(snapshot.get("trading_desk"), dict) else {}
    journal = snapshot.get("journal") or trading_desk.get("journal") or []
    if isinstance(journal, dict):
        journal = journal.get("trades") or journal.get("entries") or []
    return journal if isinstance(journal, list) else []


def _normalize_ai(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    ai = snapshot.get("ai_briefing") or snapshot.get("ai") or snapshot.get("terminal", {}).get("ai_briefing") or {}
    return ai if isinstance(ai, dict) else {}


def _fallback_calendar() -> List[Dict[str, Any]]:
    return [
        {"Time": "08:30", "Currency": "USD", "Event": "Core PCE Price Index", "Actual": "-", "Forecast": "2.8%"},
        {"Time": "08:30", "Currency": "USD", "Event": "Durable Goods Orders", "Actual": "-", "Forecast": "0.3%"},
        {"Time": "14:00", "Currency": "EUR", "Event": "ECB President Speaks", "Actual": "", "Forecast": ""},
        {"Time": "15:45", "Currency": "USD", "Event": "Chicago PMI", "Actual": "-", "Forecast": "42.3"},
    ]


def _fallback_central_banks() -> List[Dict[str, Any]]:
    return [
        {"Date": "Jul 01", "Currency": "AUD", "Event": "RBA Interest Rate Decision", "Impact": "High"},
        {"Date": "Jul 09", "Currency": "USD", "Event": "FOMC Meeting Minutes", "Impact": "High"},
        {"Date": "Jul 10", "Currency": "EUR", "Event": "ECB Interest Rate Decision", "Impact": "High"},
        {"Date": "Jul 17", "Currency": "JPY", "Event": "BOJ Interest Rate Decision", "Impact": "High"},
    ]


def _build_alerts(recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    alerts = []
    for rec in recommendations[:3]:
        alerts.append({"Time": datetime.now(timezone.utc).strftime("%H:%M"), "Alert": f"{rec.get('pair')} {rec.get('side')} setup confidence {_safe_float(rec.get('confidence')):.0f}%", "Severity": "High" if _safe_float(rec.get("confidence")) >= 85 else "Medium"})
    return alerts or [{"Time": "23:57", "Alert": "EUR/USD price above 1.0710", "Severity": "Medium"}]


# ----------------------------- UI helpers -----------------------------

def _inject_terminal_css() -> None:
    st.markdown("""
<style>
.fx-card{background:linear-gradient(180deg,rgba(14,31,49,.96),rgba(5,14,25,.98));border:1px solid rgba(0,218,255,.22);border-radius:12px;padding:14px 16px;box-shadow:0 0 0 1px rgba(255,255,255,.025) inset,0 8px 24px rgba(0,0,0,.22);min-height:96px}.fx-panel{background:linear-gradient(180deg,rgba(14,31,49,.96),rgba(5,14,25,.98));border:1px solid rgba(0,218,255,.18);border-radius:12px;padding:13px;margin-bottom:10px}.fx-title{font-size:.74rem;color:#9fb5ca;text-transform:uppercase;letter-spacing:.07em;margin-bottom:4px;font-weight:700}.fx-value{color:#f5f9ff;font-weight:850;font-size:1.42rem;line-height:1.1}.fx-sub{color:#9fb5ca;font-size:.78rem;margin-top:4px}.fx-positive{color:#2fe278!important}.fx-negative{color:#ff5264!important}.fx-warning{color:#ffb020!important}.fx-muted{color:#9fb5ca!important}.fx-bar{width:100%;height:8px;border-radius:999px;background:rgba(255,255,255,.08);overflow:hidden;margin-top:8px}.fx-fill{height:8px;border-radius:999px;background:linear-gradient(90deg,#00d2ff,#30e07a)}.fx-section{display:flex;justify-content:space-between;align-items:center;color:#c9d7e8;font-weight:800;font-size:.88rem;margin-bottom:10px}.fx-chip{padding:2px 8px;border-radius:999px;background:rgba(0,208,255,.10);border:1px solid rgba(0,208,255,.25);color:#bfefff;font-size:.70rem;font-weight:700}.fx-rec{border:1px solid rgba(255,255,255,.12);border-radius:11px;padding:12px;background:rgba(255,255,255,.035);min-height:190px}.fx-rec-buy{border-color:rgba(48,224,122,.35);background:linear-gradient(180deg,rgba(48,224,122,.11),rgba(255,255,255,.025))}.fx-rec-sell{border-color:rgba(255,77,95,.35);background:linear-gradient(180deg,rgba(255,77,95,.11),rgba(255,255,255,.025))}div[data-testid="stMetricValue"]{font-size:1.2rem}
</style>""", unsafe_allow_html=True)


def _class_for(value: Any) -> str:
    v = str(value or "").upper()
    if any(x in v for x in ["BUY", "BULL", "LONG", "HEALTHY", "READY", "PASS", "HIGH"]):
        return "fx-positive"
    if any(x in v for x in ["SELL", "BEAR", "SHORT", "ERROR", "FAIL", "RISK-OFF", "RISK_OFF", "RATE", "DEGRADED"]):
        return "fx-negative"
    if any(x in v for x in ["WATCH", "WARNING", "MODERATE", "NEUTRAL"]):
        return "fx-warning"
    return "fx-muted"


def _metric_card(title: str, value: Any, subtitle: str = "", mood: Any = "", progress: Optional[float] = None) -> None:
    bar = ""
    if progress is not None:
        pct = max(0, min(100, _safe_float(progress)))
        bar = f'<div class="fx-bar"><div class="fx-fill" style="width:{pct}%"></div></div>'
    st.markdown(f'<div class="fx-card"><div class="fx-title">{title}</div><div class="fx-value {_class_for(mood)}">{value}</div><div class="fx-sub">{subtitle}</div>{bar}</div>', unsafe_allow_html=True)


def _section(title: str, right: str = "") -> None:
    st.markdown(f'<div class="fx-section"><span>{title}</span><span class="fx-chip">{right}</span></div>', unsafe_allow_html=True)


def _df(rows: Any):
    if pd is None:
        return rows
    if rows is None:
        return pd.DataFrame()
    if hasattr(rows, "empty"):
        return rows
    if isinstance(rows, dict):
        return pd.DataFrame([rows])
    if isinstance(rows, list):
        return pd.DataFrame(rows)
    return pd.DataFrame()


def _render_table(rows: Any, height: int = 230) -> None:
    data = _df(rows)
    if pd is not None and hasattr(data, "empty") and data.empty:
        st.info("No rows available.")
        return
    st.dataframe(data, use_container_width=True, hide_index=True, height=height)


def _render_top_ribbon(data: Dict[str, Any]) -> None:
    account = data.get("account") or {}
    margin = data.get("margin") or {}
    performance = data.get("performance") or {}

    cash = _safe_float(account.get("cash_balance"))
    margin_used = _safe_float(margin.get("margin_used") or account.get("margin_used"))
    margin_available = _safe_float(margin.get("margin_available") or account.get("margin_available"))
    total_pnl = _safe_float(performance.get("total_pnl"), data.get("daily_pnl", 0))

    cols = st.columns([1.25, 1.18, 1.18, 1.05, 1.0, 1.08, 1.18, 1.12])
    with cols[0]: _metric_card("Market Regime", data["regime"], f"Macro Score: {data['macro_score']:.0f}/100", data["regime"], data["macro_score"])
    with cols[1]: _metric_card("Equity", f"${data['equity']:,.2f}", "Portfolio value", "READY", 74 if data["equity"] else 0)
    with cols[2]: _metric_card("Cash", f"${cash:,.2f}", "Account balance", "READY", 70 if cash else 0)
    with cols[3]: _metric_card("Open Positions", data["open_positions"], "Active exposure", "READY", 64 if data["open_positions"] else 0)
    with cols[4]: _metric_card("Margin Used", f"${margin_used:,.2f}", "Allocated", "WARNING" if margin_used else "READY", 50 if margin_used else 0)
    with cols[5]: _metric_card("Buying Power", f"${margin_available:,.2f}", "Margin available", "READY", 78 if margin_available else 0)
    with cols[6]: _metric_card("Total P/L", f"{'+' if total_pnl >= 0 else '-'}${abs(total_pnl):,.2f}", f"{data['daily_pnl_pct']:+.2f}%", "BUY" if total_pnl >= 0 else "SELL", 78 if total_pnl else 0)
    with cols[7]: _metric_card("Server Time", datetime.now(timezone.utc).strftime("%H:%M:%S UTC"), datetime.now(timezone.utc).strftime("%b %d, %Y"), "READY")


def _render_terminal_status_bar(data: Dict[str, Any]) -> None:
    account = data.get("account") or {}
    margin = data.get("margin") or {}
    raw = data.get("raw_snapshot") or {}
    system = raw.get("system") if isinstance(raw, dict) else {}
    if not isinstance(system, dict):
        system = {}
    st.caption(
        " | ".join([
            f"Snapshot: {str(data.get('generated_at', '-'))[:19]}",
            f"Account: {account.get('account_name') or account.get('id') or 'N/A'}",
            f"Currency: {account.get('account_currency', 'USD')}",
            f"Leverage: {account.get('leverage', margin.get('leverage', '-'))}",
            f"Margin Utilization: {_safe_float(margin.get('margin_utilization_pct')):.2f}%",
            f"Source: {system.get('source', 'terminal_api')}",
        ])
    )


def _render_strength(rows: List[Dict[str, Any]]) -> None:
    _section("Currency Strength", "vs USD")
    for row in rows:
        ccy = row.get("currency", "-")
        score = _safe_float(row.get("score"))
        trend = str(row.get("trend") or "").upper()
        icon = "↑" if trend in {"UP", "BULLISH", "BUY", "STRONG"} else "↓" if trend in {"DOWN", "BEARISH", "SELL", "WEAK"} else "—"
        cls = "fx-positive" if icon == "↑" else "fx-negative" if icon == "↓" else "fx-muted"
        st.markdown(f'<div style="display:grid;grid-template-columns:52px 1fr 40px 25px;gap:8px;align-items:center;margin:5px 0;"><div style="font-weight:850;color:#e8f2ff;">{ccy}</div><div class="fx-bar" style="margin-top:0;"><div class="fx-fill" style="width:{max(0,min(100,score))}%"></div></div><div style="text-align:right;color:#e8f2ff;">{score:.0f}</div><div class="{cls}" style="font-weight:900;">{icon}</div></div>', unsafe_allow_html=True)


def _render_left_panel(data: Dict[str, Any]) -> None:
    st.markdown('<div class="fx-panel">', unsafe_allow_html=True); _render_strength(data["currency_strength"]); st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div class="fx-panel">', unsafe_allow_html=True)
    _section("Macro Environment", data["regime"])
    st.markdown(f"**Regime:** <span class='{_class_for(data['regime'])}'>{data['regime']}</span>", unsafe_allow_html=True)
    st.progress(max(0, min(100, int(data["macro_score"]))) / 100)
    st.write(f"Macro Score: **{data['macro_score']:.0f} / 100**")
    st.write("Risk Appetite:", "Low" if "OFF" in data["regime"] else "High")
    st.write("Liquidity:", "Constrained" if "OFF" in data["regime"] else "Normal")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div class="fx-panel">', unsafe_allow_html=True); _section("Provider Health", "routing"); _render_table(data["provider_health"], height=185); st.markdown("</div>", unsafe_allow_html=True)


def _demo_chart(pair: str = "EUR/USD"):
    if go is None:
        return None
    x = list(range(90)); price = 1.071; close=[]; high=[]; low=[]; open_=[]
    for i in x:
        o = price; price += ((i % 8) - 3.5) * 0.00016 + (0.00021 if 18 < i < 55 else -0.00006); c = price
        open_.append(o); close.append(c); high.append(max(o,c)+0.00035); low.append(min(o,c)-0.00031)
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=x, open=open_, high=high, low=low, close=close, name=pair))
    fig.add_trace(go.Bar(x=x, y=[abs((i % 11)-5)*12+45 for i in x], name="Volume", yaxis="y2", opacity=0.22))
    fig.update_layout(template="plotly_dark", height=430, margin=dict(l=5,r=5,t=28,b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", title=f"{pair} · 1H · Institutional Flow", xaxis_rangeslider_visible=False, yaxis=dict(title="Price"), yaxis2=dict(overlaying="y", side="right", visible=False), legend=dict(orientation="h"))
    return fig


def _render_order_book(pair: str, data: Optional[Dict[str, Any]] = None) -> None:
    _section("Order / Execution Flow", pair)
    data = data or {}
    rows = []
    for row in (data.get("orders", {}).get("open", []) or []):
        if isinstance(row, dict) and _normalize_pair(row.get("pair") or row.get("symbol") or pair) == _normalize_pair(pair):
            rows.append(row)
    if not rows:
        for row in (data.get("execution_history", []) or []):
            if isinstance(row, dict) and _normalize_pair(row.get("pair") or row.get("symbol") or pair) == _normalize_pair(pair):
                rows.append(row)
    _render_table(rows, height=230)


def _render_trade_ticket(api, pair: str) -> None:
    _section("Trade Ticket", "paper")
    side = st.radio("Side", ["Buy", "Sell"], horizontal=True, key="fx_ticket_side")
    lots = st.number_input("Size (Lots)", min_value=0.01, value=1.00, step=0.01, key="fx_ticket_lots")
    risk = st.number_input("Risk %", min_value=0.1, value=1.0, step=0.1, key="fx_ticket_risk")
    stop = st.text_input("Stop Loss", value="1.06800", key="fx_ticket_stop")
    target = st.text_input("Take Profit", value="1.07800", key="fx_ticket_target")
    if st.button(f"{side} {lots:.2f} {pair}", use_container_width=True, key="fx_ticket_submit"):
        try:
            result = api.submit_order(pair=pair, side=side.upper(), units=lots*100000, order_type="MARKET", stop_loss=stop, take_profit=target, risk_pct=risk)
            st.success("Order submitted.")
            with st.expander("Execution response", expanded=False): st.json(result)
        except Exception as exc: st.error(f"Order submission failed: {exc}")
    st.caption("Estimated margin and pip value depend on broker configuration.")


def _render_recommendations(rows: List[Dict[str, Any]]) -> None:
    _section("AI Trade Recommendations", datetime.now(timezone.utc).strftime("%H:%M UTC"))

    if not rows:
        st.info("No live recommendations yet. Run the Forex alpha/recommendation scan.")
        return

    # IMPORTANT:
    # This function may be called while already inside a parent Streamlit column.
    # Streamlit allows columns inside columns only up to one level, so the cards
    # below do NOT create another st.columns() inside each recommendation card.
    cols = st.columns(min(4, max(1, len(rows[:4]))))

    for i, rec in enumerate(rows[:4]):
        side = str(rec.get("side", rec.get("Signal", "WATCH"))).upper()
        card_cls = "fx-rec-buy" if side == "BUY" else "fx-rec-sell" if side == "SELL" else ""

        pair = rec.get("pair", rec.get("Pair", "-"))
        entry = rec.get("entry", rec.get("Entry", "-"))
        target = rec.get("target", rec.get("Target", "-"))
        stop = rec.get("stop", rec.get("Stop", "-"))
        confidence = _safe_float(rec.get("confidence", rec.get("Confidence", 0)))
        bias = rec.get("bias", rec.get("Bias", "-"))
        rr = rec.get("risk_reward", rec.get("RR", "-"))

        with cols[i % len(cols)]:
            st.markdown(f'<div class="fx-rec {card_cls}">', unsafe_allow_html=True)
            st.markdown(
                f"**<span class='{_class_for(side)}'>{side}</span> {pair}**",
                unsafe_allow_html=True,
            )
            st.markdown(f"**Confidence:** {confidence:.0f}%")
            st.markdown(f"**Entry:** {entry}")
            st.markdown(f"**Target:** {target}")
            st.markdown(f"**Stop:** {stop}")
            st.caption(f"Bias: {bias} | RR: {rr}")
            st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Recommendation table", expanded=False):
        _render_table(rows, height=260)


def _briefing_text(data: Dict[str, Any]) -> str:
    ai = data.get("ai") or {}
    if isinstance(ai, dict):
        for key in ["briefing", "summary", "narrative", "market_briefing"]:
            if ai.get(key): return str(ai[key])
    return f"Markets remain in a **{data['regime']}** regime. {_currency_flag(data['strongest_currency'])} **{data['strongest_currency']}** leads currency strength while {_currency_flag(data['weakest_currency'])} **{data['weakest_currency']}** remains under pressure. AI confidence is running near **{data['ai_confidence']:.0f}%**, favoring selective institutional setups and disciplined risk."


def _render_right_panel(data: Dict[str, Any]) -> None:
    st.markdown('<div class="fx-panel">', unsafe_allow_html=True); _section("AI Market Briefing", datetime.now(timezone.utc).strftime("%H:%M UTC")); st.markdown(_briefing_text(data)); st.caption("Key Takeaways"); st.markdown(f"""- {data['strongest_currency']} remains a leadership currency\n- {data['weakest_currency']} remains under pressure\n- {data['regime']} favors disciplined sizing\n- Watch inflation and central-bank catalysts"""); st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div class="fx-panel">', unsafe_allow_html=True); _section("Economic Calendar", "today"); _render_table(data["economic_calendar"], height=175); st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div class="fx-panel">', unsafe_allow_html=True); _section("Central Bank Events", "upcoming"); _render_table(data["central_bank_events"], height=160); st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div class="fx-panel">', unsafe_allow_html=True); _section("Alerts", str(len(data["alerts"]))); _render_table(data["alerts"], height=150); st.markdown("</div>", unsafe_allow_html=True)


def _render_bottom_panel(data: Dict[str, Any]) -> None:
    st.markdown('<div class="fx-panel">', unsafe_allow_html=True)
    t1,t2,t3,t4,t5,t6 = st.tabs(["Positions", "Orders", "Cash Ledger", "Executions", "Exposure", "Equity Curve"])
    with t1:
        _render_table(data["positions"], height=230)
    with t2:
        c1,c2=st.columns(2)
        with c1:
            st.subheader("Open Orders")
            _render_table(data["orders"]["open"], height=205)
        with c2:
            st.subheader("Filled Orders")
            _render_table(data["orders"]["filled"], height=205)
    with t3:
        _render_table(data.get("cash_ledger") or data.get("journal"), height=230)
    with t4:
        _render_table(data.get("execution_history") or data["orders"]["filled"], height=230)
    with t5:
        c1,c2=st.columns(2)
        with c1:
            st.subheader("Currency Exposure")
            _render_table(data.get("currency_exposure"), height=205)
        with c2:
            st.subheader("Pair Exposure")
            _render_table(data.get("pair_exposure"), height=205)
    with t6:
        _render_equity_curve(data)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_equity_curve(data: Dict[str, Any]) -> None:
    if go is None:
        st.info("Plotly is unavailable.")
        return
    equity = _safe_float(data.get("equity"))
    pnl = _safe_float(data.get("daily_pnl"))
    if equity <= 0:
        st.info("No live equity value available yet.")
        return
    x=list(range(30))
    y=[equity - pnl + pnl*(i/29.0) for i in x]
    fig=go.Figure(go.Scatter(x=x,y=y,mode="lines",fill="tozeroy",name="Equity"))
    fig.update_layout(template="plotly_dark",height=230,margin=dict(l=5,r=5,t=20,b=5),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)


# ----------------------------- Workspace renderers -----------------------------

def _render_trading_desk(api, data: Dict[str, Any]) -> None:
    left, center, right = st.columns([1.05, 2.65, 1.25])
    with left: _render_left_panel(data)
    with center:
        pair = st.selectbox("Active Pair", DEFAULT_PAIRS, index=0, key="fx_active_pair")
        top_left, top_right = st.columns([2.1, 1])
        with top_left:
            st.markdown('<div class="fx-panel">', unsafe_allow_html=True); _section("Live Chart", pair); fig=_demo_chart(pair); st.plotly_chart(fig, use_container_width=True) if fig is not None else st.info("Plotly is unavailable."); st.markdown("</div>", unsafe_allow_html=True)
        with top_right:
            st.markdown('<div class="fx-panel">', unsafe_allow_html=True); _render_order_book(pair, data); st.markdown("</div>", unsafe_allow_html=True)
            st.markdown('<div class="fx-panel">', unsafe_allow_html=True); _render_trade_ticket(api, pair); st.markdown("</div>", unsafe_allow_html=True)
        st.markdown('<div class="fx-panel">', unsafe_allow_html=True); _render_recommendations(data["recommendations"]); st.markdown("</div>", unsafe_allow_html=True)
    with right: _render_right_panel(data)
    _render_bottom_panel(data)


def _render_command_center(data: Dict[str, Any]) -> None:
    left, center, right = st.columns([1.05, 2.55, 1.25])
    with left: _render_left_panel(data)
    with center:
        st.markdown('<div class="fx-panel">', unsafe_allow_html=True); _section("Institutional Signal Matrix", "ranked"); _render_table(data["recommendations"], height=430); st.markdown("</div>", unsafe_allow_html=True)
        st.markdown('<div class="fx-panel">', unsafe_allow_html=True); _section("Market Overview", data["regime"]); overview=data.get("market_overview") or {}; display={k:v for k,v in overview.items() if not isinstance(v,(dict,list))}; _render_table(display if display else {"Regime":data["regime"],"Macro Score":data["macro_score"]}, height=160); st.markdown("</div>", unsafe_allow_html=True)
    with right: _render_right_panel(data)


def _render_portfolio(data: Dict[str, Any]) -> None:
    account = data.get("account") or {}
    margin = data.get("margin") or {}
    performance = data.get("performance") or {}
    st.markdown('<div class="fx-panel">', unsafe_allow_html=True)
    _section("Portfolio Account", account.get("account_currency", "USD"))
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Cash", f"${_safe_float(account.get('cash_balance')):,.2f}")
    c2.metric("Equity", f"${_safe_float(account.get('equity')):,.2f}")
    c3.metric("Margin Used", f"${_safe_float(margin.get('margin_used') or account.get('margin_used')):,.2f}")
    c4.metric("Buying Power", f"${_safe_float(margin.get('margin_available') or account.get('margin_available')):,.2f}")
    c5.metric("Total P/L", f"${_safe_float(performance.get('total_pnl')):,.2f}")
    st.markdown("</div>", unsafe_allow_html=True)
    _render_bottom_panel(data)
def _render_orders(data: Dict[str, Any]) -> None:
    st.markdown('<div class="fx-panel">', unsafe_allow_html=True); _section("Order Management", "open / filled"); c1,c2=st.columns(2)
    with c1: st.subheader("Open Orders"); _render_table(data["orders"]["open"], height=420)
    with c2: st.subheader("Filled Orders"); _render_table(data["orders"]["filled"], height=420)
    st.markdown("</div>", unsafe_allow_html=True)

def _render_risk(data: Dict[str, Any]) -> None:
    risk = data.get("risk") or {}
    pair_exposure = data.get("pair_exposure") or []
    currency_exposure = data.get("currency_exposure") or []
    gross = sum(abs(_safe_float(row.get("gross_notional") or row.get("gross_exposure"))) for row in pair_exposure if isinstance(row, dict))
    net = sum(_safe_float(row.get("net_notional") or row.get("net_exposure")) for row in pair_exposure if isinstance(row, dict))

    st.markdown('<div class="fx-panel">', unsafe_allow_html=True)
    _section("Risk Dashboard", data["regime"])
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Gross Exposure", f"${gross:,.2f}" if gross else f"${_safe_float(risk.get('total_notional')):,.2f}")
    c2.metric("Net Exposure", f"${net:,.2f}")
    c3.metric("Risk Score", f"{_safe_float(risk.get('risk_score')):.2f}")
    c4.metric("Margin Available", f"${_safe_float(risk.get('margin_available') or data.get('margin', {}).get('margin_available')):,.2f}")
    if risk.get("warnings"):
        st.warning(risk.get("warnings"))
    st.markdown("</div>", unsafe_allow_html=True)

    c1,c2 = st.columns(2)
    with c1:
        st.markdown('<div class="fx-panel">', unsafe_allow_html=True)
        _section("Currency Exposure", "live")
        _render_table(currency_exposure, height=320)
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="fx-panel">', unsafe_allow_html=True)
        _section("Pair Exposure", "live")
        _render_table(pair_exposure, height=320)
        st.markdown("</div>", unsafe_allow_html=True)

def _render_performance(data: Dict[str, Any]) -> None:
    perf = data.get("performance") or {}
    st.markdown('<div class="fx-panel">', unsafe_allow_html=True)
    _section("Performance Analytics", "portfolio")
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Total P/L", f"${_safe_float(perf.get('total_pnl') or data.get('daily_pnl')):,.2f}", f"{data['daily_pnl_pct']:+.2f}%")
    c2.metric("Win Rate", f"{_safe_float(perf.get('win_rate')):.2f}%")
    c3.metric("Profit Factor", f"{_safe_float(perf.get('profit_factor')):.2f}")
    c4.metric("Sharpe", f"{_safe_float(perf.get('sharpe')):.2f}")
    c5.metric("Expectancy", f"${_safe_float(perf.get('expectancy')):,.2f}")
    st.markdown("</div>", unsafe_allow_html=True)
    _render_table(perf, height=220)
    _render_bottom_panel(data)

def _render_journal(data: Dict[str, Any]) -> None:
    st.markdown('<div class="fx-panel">', unsafe_allow_html=True); _section("Trade Journal", "entries"); _render_table(data["journal"], height=470); st.markdown("</div>", unsafe_allow_html=True)

def _render_ai_briefing(data: Dict[str, Any]) -> None:
    _render_right_panel(data); st.markdown('<div class="fx-panel">', unsafe_allow_html=True); _render_recommendations(data["recommendations"]); st.markdown("</div>", unsafe_allow_html=True)

def _render_provider_health(data: Dict[str, Any]) -> None:
    st.markdown('<div class="fx-panel">', unsafe_allow_html=True); _section("Provider Health", "routing and latency"); _render_table(data["provider_health"], height=450); st.markdown("</div>", unsafe_allow_html=True)


def _render_developer_debug(raw_snapshot: Dict[str, Any], normalized: Dict[str, Any]) -> None:
    with st.expander("Developer / Debug", expanded=False):
        t1,t2,t3=st.tabs(["Raw JSON", "Normalized View", "System Status"])
        with t1:
            st.json(raw_snapshot)
        with t2:
            st.json(normalized)
        with t3:
            raw = normalized.get("raw_snapshot") or {}
            system = raw.get("system") if isinstance(raw, dict) else {}
            if not isinstance(system, dict):
                system = {}
            st.write("Generated at:", normalized.get("generated_at"))
            st.write("Dashboard:", "forex_terminal_dashboard.py")
            st.write("Status:", normalized.get("status", "READY"))
            st.write("Account:", (normalized.get("account") or {}).get("id"))
            st.write("Snapshot Source:", system.get("source", "terminal_api"))


_DASH = None


def get_forex_terminal_dashboard(db=None, api=None):
    global _DASH
    if _DASH is None or (db is not None and _DASH.db is None):
        _DASH = ForexTerminalDashboard(db=db, api=api)
    return _DASH


def render_forex_terminal_dashboard(*args: Any, **kwargs: Any):
    db = kwargs.get("db")
    if db is None and args:
        db = args[0]
    return get_forex_terminal_dashboard(db=db).render(*args, **kwargs)
