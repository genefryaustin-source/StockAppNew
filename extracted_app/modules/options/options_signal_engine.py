"""Phase 7 signal engine for autonomous options candidates."""
from __future__ import annotations
from typing import Any


def _safe(fn, *args, default=None, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        return default


def collect_execution_signals(ticker: str) -> dict[str, Any]:
    ticker = ticker.upper()
    smart = {}
    dealer = {}
    vol = {}
    portfolio = {}

    try:
        from modules.options.options_smart_money_engine import build_options_smart_money_report
        smart = build_options_smart_money_report(ticker) or {}
    except Exception as exc:
        smart = {"error": str(exc)}

    try:
        from modules.options.options_dealer_exposure_engine import build_dealer_exposure_report
        dealer = build_dealer_exposure_report(ticker) or {}
    except Exception as exc:
        dealer = {"error": str(exc)}

    try:
        from modules.options.options_volatility_dashboard import _load_report
        vol = _load_report(ticker, force_refresh=False) or {}
    except Exception as exc:
        vol = {"error": str(exc)}

    try:
        from modules.options.options_portfolio_engine import build_options_portfolio_snapshot
        portfolio = build_options_portfolio_snapshot(ticker, paper=True) or {}
    except Exception as exc:
        portfolio = {"error": str(exc)}

    signals = derive_signal_scores(smart, dealer, vol, portfolio)
    return {
        "ticker": ticker,
        "smart_money": smart,
        "dealer": dealer,
        "volatility": vol,
        "portfolio": portfolio,
        "signals": signals,
    }


def derive_signal_scores(smart: dict[str, Any], dealer: dict[str, Any], vol: dict[str, Any], portfolio: dict[str, Any]) -> dict[str, Any]:
    def n(v, d=0.0):
        try:
            return float(v or d)
        except Exception:
            return d

    sentiment = smart.get("sentiment", {}) if isinstance(smart, dict) else {}
    conviction = smart.get("conviction_score", {}) if isinstance(smart, dict) else {}
    dealer_state = str((dealer or {}).get("gamma_state") or (dealer or {}).get("state") or "Neutral")
    vol_regime = str((vol or {}).get("regime") or (vol or {}).get("volatility_regime") or "Neutral")

    smart_score = n(sentiment.get("score"), 50) * 0.5 + n(conviction.get("score"), 50) * 0.5
    dealer_score = 55.0
    if "Negative" in dealer_state or "Short" in dealer_state:
        dealer_score = 65.0
    elif "Positive" in dealer_state or "Long" in dealer_state:
        dealer_score = 45.0

    vol_score = 50.0
    if "Expansion" in vol_regime or "High" in vol_regime:
        vol_score = 65.0
    elif "Contraction" in vol_regime or "Low" in vol_regime:
        vol_score = 40.0

    combined = round((smart_score * 0.40) + (dealer_score * 0.25) + (vol_score * 0.25) + 5.0, 1)
    direction = "Bullish" if combined >= 60 else "Bearish" if combined <= 40 else "Neutral"
    return {
        "smart_money_score": round(smart_score, 1),
        "dealer_score": round(dealer_score, 1),
        "volatility_score": round(vol_score, 1),
        "combined_signal_score": combined,
        "direction": direction,
        "dealer_state": dealer_state,
        "volatility_regime": vol_regime,
    }
