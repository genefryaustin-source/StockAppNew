"""
modules/forex/ui/forex_regime_summary.py

Normalizes macro regime data for the Regime workspace: current
regime/confidence, risk appetite/liquidity/volatility, transition
probabilities, regime history rows, and macro/central-bank drivers.

Fixed in this pass (no-fake-data audit): normalize_regime() used to
default to a fixed "RISK_OFF" regime at 78% confidence, invented
transition probabilities (e.g. {"Risk-Off": 68%, "Neutral": 22%,
"Risk-On": 10%}), and a fabricated risk_score (72 or 64) whenever there
was no real regime data -- all presented as live model output. Now
defaults to "UNKNOWN"/0/empty. extract_regime_rows() used to fabricate
four past periods (T-5..T-2, always "Risk-Off" at made-up confidence
levels) -- it now only shows real history plus the live current regime.
extract_macro_drivers() used to show fixed Fed/ECB/BoJ/SNB commentary
("Neutral"/"Dovish"/"Accommodative"/"Defensive") that never changed -- it
now queries the real FRED-backed forex_central_bank_engine, and returns
an honestly empty list if that's unavailable too.
"""

from __future__ import annotations
from typing import Any, Dict, List

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace("%", "").replace(",", "").replace("$", "").strip()
            if value in {"", "-", "—", "None"}:
                return default
        return float(value)
    except Exception:
        return default

def _walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)

def find_regime_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    for key in ("regime", "market_regime", "macro_regime", "regime_classifier", "regime_intelligence"):
        val = payload.get(key)
        if isinstance(val, dict):
            return val
        if isinstance(val, str):
            return {"regime": val}
    for item in _walk(payload):
        if any(k in item for k in ("regime", "market_regime", "risk_appetite", "macro_score", "transition_probability")):
            return item
    return {}

def normalize_regime(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reads a real regime payload (ultimately sourced from
    forex_macro_regime_engine upstream). Previously this defaulted to a
    fixed "RISK_OFF" regime at 78% confidence, invented transition
    probabilities (e.g. {"Risk-Off": 68, ...}), and a fabricated risk_score
    (72/64) whenever the payload had nothing real to report -- all
    presented as if they were live model output. This now honestly reports
    "UNKNOWN"/0 and empty transition/risk fields when no real regime data
    is available, rather than a plausible-looking placeholder.
    """
    regime = find_regime_payload(payload)
    current = (
        regime.get("regime")
        or regime.get("market_regime")
        or regime.get("macro_regime")
        or regime.get("state")
        or "UNKNOWN"
    )
    current = str(current).replace(" ", "_").replace("-", "_").upper()
    confidence = safe_float(
        regime.get("confidence")
        or regime.get("regime_confidence")
        or regime.get("macro_score")
        or regime.get("score"),
        0.0,
    )
    risk_appetite = regime.get("risk_appetite") or ("Low" if "OFF" in current else "High" if "ON" in current else "Unknown")
    liquidity = regime.get("liquidity") or regime.get("liquidity_state") or ("Unknown" if current == "UNKNOWN" else "Normal")
    volatility = regime.get("volatility") or regime.get("volatility_state") or ("Unknown" if current == "UNKNOWN" else ("Elevated" if "OFF" in current else "Normal"))
    transition = regime.get("transition_probability") or regime.get("transition") or {}
    if not isinstance(transition, dict):
        transition = {}
    risk_score = regime.get("risk_score")
    return {
        "regime": current,
        "confidence": max(0, min(100, confidence)),
        "risk_appetite": risk_appetite,
        "liquidity": liquidity,
        "volatility": volatility,
        "macro_score": safe_float(regime.get("macro_score"), confidence),
        "risk_score": safe_float(risk_score, 0.0) if risk_score is not None else None,
        "transition_probability": transition,
        "raw": regime,
    }

def extract_regime_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Real regime history when the upstream payload actually carries one.
    Previously, whenever no history was present, this fabricated four past
    periods (T-5..T-2, always "Risk-Off" at made-up confidence levels) to
    make the timeline look populated. It now only ever shows real history
    rows plus the current, live-derived regime -- no invented past.
    """
    rows = []
    for item in _walk(payload):
        for key in ("regime_history", "history", "timeline", "regimes"):
            val = item.get(key) if isinstance(item, dict) else None
            if isinstance(val, list):
                rows.extend([x for x in val if isinstance(x, dict)])
    current = normalize_regime(payload)
    rows.append({"period": "Now", "regime": current["regime"], "confidence": current["confidence"], "risk_appetite": current["risk_appetite"]})
    return rows

def extract_macro_drivers(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Real central-bank drivers when the payload doesn't already carry them:
    queries forex_central_bank_engine (FRED-backed policy rates) instead of
    the previous fixed "Fed: Neutral / ECB: Dovish / BoJ: Accommodative /
    SNB: Defensive" commentary, which never changed regardless of actual
    policy conditions.
    """
    drivers = []
    for item in _walk(payload):
        for key in ("drivers", "market_drivers", "macro_drivers", "central_banks"):
            val = item.get(key) if isinstance(item, dict) else None
            if isinstance(val, list):
                drivers.extend([x for x in val if isinstance(x, dict)])
            elif isinstance(val, dict):
                for name, status in val.items():
                    drivers.append({"driver": name, "status": status})

    if not drivers:
        try:
            from modules.forex.forex_central_bank_engine import get_forex_central_bank_engine
            cb_data = get_forex_central_bank_engine().analyze()
            banks = cb_data.get("central_banks") if isinstance(cb_data, dict) else None
            if isinstance(banks, list):
                for item in banks:
                    if not isinstance(item, dict) or item.get("error"):
                        continue
                    rate = item.get("policy_rate")
                    rate_txt = f"{rate:.2f}%" if isinstance(rate, (int, float)) else "unavailable"
                    drivers.append({
                        "driver": item.get("central_bank", "-"),
                        "status": item.get("policy_bias", "-"),
                        "impact": f"{item.get('currency', '-')} policy rate {rate_txt}"
                                  + (" (proxy series)" if item.get("proxy") else ""),
                    })
        except Exception:
            pass

    if not drivers:
        # Still nothing real available (e.g. no FRED key configured) --
        # honestly report that instead of showing fixed bank commentary.
        return []

    regime = normalize_regime(payload)
    drivers.append({"driver": "Liquidity", "status": regime["liquidity"], "impact": "Monitor execution quality"})
    drivers.append({"driver": "Volatility", "status": regime["volatility"], "impact": "Adjust position sizing"})
    return drivers[:12]

def regime_commentary(payload: Dict[str, Any]) -> str:
    r = normalize_regime(payload)
    regime = r["regime"].replace("_", "-")
    return (
        f"Current macro regime is **{regime}** with **{r['confidence']:.0f}% confidence**. "
        f"Risk appetite is **{r['risk_appetite']}**, liquidity is **{r['liquidity']}**, "
        f"and volatility is **{r['volatility']}**. Portfolio sizing should remain aligned "
        "with regime confidence, transition risk, and liquidity conditions before execution."
    )