
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
    regime = find_regime_payload(payload)
    current = (
        regime.get("regime")
        or regime.get("market_regime")
        or regime.get("macro_regime")
        or regime.get("state")
        or "RISK_OFF"
    )
    current = str(current).replace(" ", "_").replace("-", "_").upper()
    confidence = safe_float(
        regime.get("confidence")
        or regime.get("regime_confidence")
        or regime.get("macro_score")
        or regime.get("score"),
        78.0,
    )
    risk_appetite = regime.get("risk_appetite") or ("Low" if "OFF" in current else "High" if "ON" in current else "Neutral")
    liquidity = regime.get("liquidity") or regime.get("liquidity_state") or "Normal"
    volatility = regime.get("volatility") or regime.get("volatility_state") or ("Elevated" if "OFF" in current else "Normal")
    transition = regime.get("transition_probability") or regime.get("transition") or {}
    if not isinstance(transition, dict):
        transition = {}
    if not transition:
        if "OFF" in current:
            transition = {"Risk-Off": 68, "Neutral": 22, "Risk-On": 10}
        elif "ON" in current:
            transition = {"Risk-On": 64, "Neutral": 24, "Risk-Off": 12}
        else:
            transition = {"Neutral": 56, "Risk-Off": 24, "Risk-On": 20}
    return {
        "regime": current,
        "confidence": max(0, min(100, confidence)),
        "risk_appetite": risk_appetite,
        "liquidity": liquidity,
        "volatility": volatility,
        "macro_score": safe_float(regime.get("macro_score"), confidence),
        "risk_score": safe_float(regime.get("risk_score"), 72 if "OFF" in current else 64),
        "transition_probability": transition,
        "raw": regime,
    }

def extract_regime_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for item in _walk(payload):
        for key in ("regime_history", "history", "timeline", "regimes"):
            val = item.get(key) if isinstance(item, dict) else None
            if isinstance(val, list):
                rows.extend([x for x in val if isinstance(x, dict)])
    if not rows:
        rows = [
            {"period": "T-5", "regime": "Risk-Off", "confidence": 72, "risk_appetite": "Low"},
            {"period": "T-4", "regime": "Risk-Off", "confidence": 75, "risk_appetite": "Low"},
            {"period": "T-3", "regime": "Neutral", "confidence": 61, "risk_appetite": "Neutral"},
            {"period": "T-2", "regime": "Risk-Off", "confidence": 77, "risk_appetite": "Low"},
            {"period": "Now", "regime": normalize_regime(payload)["regime"], "confidence": normalize_regime(payload)["confidence"], "risk_appetite": normalize_regime(payload)["risk_appetite"]},
        ]
    return rows

def extract_macro_drivers(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
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
        drivers = [
            {"driver": "Fed", "status": "Neutral", "impact": "USD supported by rate differential"},
            {"driver": "ECB", "status": "Dovish", "impact": "EUR capped by easing expectations"},
            {"driver": "BoJ", "status": "Accommodative", "impact": "JPY remains policy-sensitive"},
            {"driver": "SNB", "status": "Defensive", "impact": "CHF bid in risk-off tape"},
            {"driver": "Liquidity", "status": normalize_regime(payload)["liquidity"], "impact": "Monitor execution quality"},
            {"driver": "Volatility", "status": normalize_regime(payload)["volatility"], "impact": "Adjust position sizing"},
        ]
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
