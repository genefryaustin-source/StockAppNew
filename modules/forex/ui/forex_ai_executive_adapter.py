
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace("%", "").replace("$", "").replace(",", "").strip()
            if value in {"", "-", "—", "None", "nan"}:
                return default
        return float(value)
    except Exception:
        return default


def normalize_pair(pair: Any, default: str = "EUR/USD") -> str:
    value = str(pair or default).upper().strip()
    value = value.replace("-", "").replace("_", "").replace("/", "").replace(" ", "")
    if len(value) == 6:
        return f"{value[:3]}/{value[3:]}"
    return value or default


def walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item)


def first_value(payload: Any, keys: List[str], default: Any = None) -> Any:
    if isinstance(payload, dict):
        for key in keys:
            if key in payload and payload[key] not in (None, ""):
                return payload[key]
        for node in walk(payload):
            if not isinstance(node, dict):
                continue
            for key in keys:
                if key in node and node[key] not in (None, ""):
                    return node[key]
    return default


def collect_rows(payload: Any, keys: Tuple[str, ...]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return rows
    for node in walk(payload):
        if not isinstance(node, dict):
            continue
        for key in keys:
            value = node.get(key)
            if isinstance(value, list):
                rows.extend([x for x in value if isinstance(x, dict)])
            elif isinstance(value, dict):
                for name, nested in value.items():
                    if isinstance(nested, dict):
                        row = dict(nested)
                        row.setdefault("pair", name)
                        rows.append(row)
    return rows


SCORE_KEYS = [
    "validation_score",
    "confidence",
    "confidence_score",
    "ai_confidence",
    "overall_confidence",
    "composite_score",
    "alpha_score",
    "score",
    "quality_score",
    "conviction",
    "conviction_score",
]


def best_score(row: Dict[str, Any], default: float = 0.0) -> float:
    return max([safe_float(row.get(k)) for k in SCORE_KEYS] + [default])


def signal_from_row(row: Dict[str, Any]) -> str:
    value = row.get("signal") or row.get("recommendation") or row.get("action") or row.get("side") or "WATCH"
    value = str(value).upper()
    if value in {"STRONG_BUY", "BUY", "LONG"}:
        return "BUY"
    if value in {"STRONG_SELL", "SELL", "SHORT", "REDUCE"}:
        return "SELL"
    return "WATCH"


def status_from_scores(confidence: float, validation: float, rr: float) -> str:
    score = max(confidence, validation)
    if score >= 90 and rr >= 2.0:
        return "APPROVED"
    if score >= 80 and rr >= 1.5:
        return "PAPER VERIFIED"
    if score >= 70:
        return "UNDER REVIEW"
    if score >= 60:
        return "WATCH"
    return "REJECTED"


def institutional_grade(confidence: float, validation: float, alpha: float, rr: float) -> str:
    score = (confidence * 0.35) + (validation * 0.30) + (alpha * 0.25) + min(rr * 10, 10)
    if score >= 94:
        return "A+"
    if score >= 88:
        return "A"
    if score >= 82:
        return "A-"
    if score >= 76:
        return "B+"
    if score >= 70:
        return "B"
    if score >= 60:
        return "Review"
    return "Reject"


def _calculate_rr(row: Dict[str, Any]) -> float:
    entry = safe_float(row.get("entry") or row.get("entry_price") or row.get("current_price"))
    target = safe_float(row.get("target") or row.get("target_price"))
    stop = safe_float(row.get("stop") or row.get("stop_price"))
    if entry > 0 and target > 0 and stop > 0:
        risk = abs(entry - stop)
        reward = abs(target - entry)
        if risk > 0:
            return round(reward / risk, 2)
    return 0.0


def _expected_return(row: Dict[str, Any]) -> str:
    entry = safe_float(row.get("entry") or row.get("entry_price") or row.get("current_price"))
    target = safe_float(row.get("target") or row.get("target_price"))
    if entry > 0 and target > 0:
        return f"{((target - entry) / entry * 100):.2f}%"
    return "N/A"


def extract_opportunities(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = collect_rows(
        payload,
        (
            "approved_ideas",
            "validated_signals",
            "signals",
            "recommendations",
            "opportunities",
            "ideas",
            "candidates",
            "rows",
            "rankings",
            "pair_scores",
        ),
    )
    clean: List[Dict[str, Any]] = []
    seen = set()
    for index, row in enumerate(raw):
        pair = normalize_pair(row.get("pair") or row.get("symbol") or row.get("currency_pair") or row.get("instrument") or f"FX-{index + 1}")
        signal = signal_from_row(row)
        timeframe = str(row.get("timeframe") or row.get("horizon") or "1H")
        key = (pair, signal, timeframe)
        if key in seen:
            continue
        seen.add(key)

        confidence = max(
            safe_float(row.get("confidence")),
            safe_float(row.get("confidence_score")),
            safe_float(row.get("ai_confidence")),
            safe_float(row.get("conviction")),
            safe_float(row.get("conviction_score")),
            best_score(row),
        )
        validation = max(
            safe_float(row.get("validation_score")),
            safe_float(row.get("quality_score")),
            safe_float(row.get("composite_score")),
            confidence,
        )
        alpha = max(
            safe_float(row.get("alpha_score")),
            safe_float(row.get("composite_score")),
            safe_float(row.get("score")),
            validation,
        )
        rr = max(safe_float(row.get("risk_reward")), safe_float(row.get("rr")), _calculate_rr(row))
        status = status_from_scores(confidence, validation, rr)

        out = dict(row)
        out.update(
            {
                "pair": pair,
                "signal": signal,
                "timeframe": timeframe,
                "confidence": round(confidence, 2),
                "validation_score": round(validation, 2),
                "alpha_score": round(alpha, 2),
                "risk_reward": round(rr, 2),
                "status": row.get("status") or row.get("validation_status") or status,
                "institutional_grade": institutional_grade(confidence, validation, alpha, rr),
                "expected_return": row.get("expected_return") or row.get("expected_return_pct") or row.get("target_return") or _expected_return(row),
                "strategy": row.get("strategy") or row.get("model") or "Institutional",
                "rationale": row.get("rationale") or row.get("reason") or row.get("explanation") or "",
            }
        )
        clean.append(out)

    clean.sort(
        key=lambda item: (
            safe_float(item.get("validation_score")),
            safe_float(item.get("confidence")),
            safe_float(item.get("alpha_score")),
            safe_float(item.get("risk_reward")),
        ),
        reverse=True,
    )
    for rank, row in enumerate(clean, start=1):
        row["rank"] = rank
    return clean


def validation_success(rows: List[Dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    approved = 0
    for row in rows:
        status = str(row.get("status") or row.get("validation_status") or "").upper()
        score = best_score(row)
        if status in {"APPROVED", "VALIDATED", "READY", "PAPER VERIFIED", "PASSED", "PASS"} or score >= 75:
            approved += 1
    return round(approved / len(rows) * 100, 2)


def extract_regime(payload: Dict[str, Any]) -> Dict[str, Any]:
    regime_obj: Dict[str, Any] = {}
    for key in ("market_regime", "regime", "macro_regime", "regime_intelligence"):
        value = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(value, dict):
            regime_obj = value
            break
        if isinstance(value, str):
            regime_obj = {"regime": value}
            break

    if not regime_obj:
        for node in walk(payload):
            if isinstance(node, dict) and any(k in node for k in ("regime", "market_regime", "macro_score", "risk_appetite")):
                regime_obj = node
                break

    current = regime_obj.get("regime") or regime_obj.get("market_regime") or regime_obj.get("macro_regime") or "Unknown"
    macro_score = max(
        safe_float(regime_obj.get("macro_score")),
        safe_float(regime_obj.get("score")),
        safe_float(first_value(payload, ["macro_score", "regime_score"], 0)),
    )
    liquidity = regime_obj.get("liquidity") or regime_obj.get("liquidity_state") or first_value(payload, ["liquidity", "liquidity_state"], "Unknown")

    return {
        "regime": str(current).replace("_", "-").title(),
        "liquidity": liquidity,
        "macro_score": round(macro_score, 2),
        "risk_appetite": regime_obj.get("risk_appetite") or first_value(payload, ["risk_appetite"], "Unknown"),
        "raw": regime_obj,
    }


def extract_market_drivers(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for node in walk(payload):
        if not isinstance(node, dict):
            continue
        for key in ("central_banks", "drivers", "market_drivers", "macro_drivers"):
            value = node.get(key)
            if isinstance(value, list):
                rows.extend([x for x in value if isinstance(x, dict)])
            elif isinstance(value, dict):
                for name, detail in value.items():
                    if isinstance(detail, dict):
                        row = dict(detail)
                        row.setdefault("driver", name)
                    else:
                        row = {"driver": name, "bias": detail}
                    rows.append(row)

    clean = []
    seen = set()
    for row in rows:
        driver = str(row.get("driver") or row.get("bank") or row.get("name") or "").strip()
        if not driver:
            continue
        key = driver.upper()
        if key in seen:
            continue
        seen.add(key)
        clean.append(
            {
                "Driver": driver,
                "Bias": row.get("bias") or row.get("status") or row.get("policy_bias") or "Neutral",
                "Impact": row.get("impact") or row.get("summary") or row.get("rationale") or "",
                "Score": safe_float(row.get("score") or row.get("impact_score") or row.get("confidence")),
            }
        )
    return clean[:12]


def active_models(payload: Dict[str, Any]) -> Tuple[int, List[Dict[str, Any]]]:
    model_sections = {
        "Quant Research": payload.get("quant_research"),
        "Portfolio Optimizer": payload.get("portfolio_optimizer"),
        "Strategy Lab": payload.get("strategy_lab"),
        "AI Committee": payload.get("ai_investment_committee"),
        "Enterprise Reporting": payload.get("enterprise_reporting"),
        "Alpha": first_value(payload, ["alpha_research", "alpha_model"], None),
        "Signal Validation": first_value(payload, ["signal_validation", "validation"], None),
        "Regime": first_value(payload, ["regime", "market_regime", "macro_regime"], None),
    }
    rows = []
    count = 0
    for name, section in model_sections.items():
        ok = False
        status = "MISSING"
        if isinstance(section, dict):
            status = str(section.get("status") or section.get("state") or "READY").upper()
            ok = status not in {"ERROR", "FAILED", "UNAVAILABLE", "MISSING"}
        elif isinstance(section, str):
            status = section
            ok = bool(section)
        elif section is not None:
            status = "READY"
            ok = True
        if ok:
            count += 1
        rows.append({"Model": name, "Status": status, "Active": ok})
    return count, rows


def extract_committee_votes(payload: Dict[str, Any], opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = collect_rows(payload, ("votes", "committee_votes", "members", "committee"))
    clean = []
    for row in rows:
        member = str(row.get("member") or row.get("model") or row.get("engine") or row.get("name") or "").strip()
        if not member:
            continue
        clean.append(
            {
                "Model": member,
                "Vote": str(row.get("vote") or row.get("decision") or row.get("signal") or "HOLD").upper(),
                "Confidence": safe_float(row.get("confidence") or row.get("score")),
                "Reason": row.get("reason") or row.get("rationale") or "",
            }
        )
    if clean:
        return clean

    top = opportunities[0] if opportunities else {}
    top_signal = top.get("signal", "HOLD")
    top_conf = safe_float(top.get("confidence"))
    model_names = ["Alpha Model", "Signal Validation", "Macro Regime", "Currency Strength", "Sentiment", "Risk", "Execution"]
    for index, name in enumerate(model_names):
        confidence = max(0, top_conf - index * 3)
        vote = top_signal if confidence >= 65 else "HOLD"
        clean.append({"Model": name, "Vote": vote, "Confidence": round(confidence, 2), "Reason": "Derived from normalized executive payload."})
    return clean


def normalize_executive_ai_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    opportunities = extract_opportunities(payload)
    top = opportunities[0] if opportunities else {}

    confidence = max(safe_float(top.get("confidence")), safe_float(first_value(payload, ["ai_confidence", "overall_confidence", "confidence", "confidence_score"], 0)))
    alpha_score = max(safe_float(top.get("alpha_score")), safe_float(first_value(payload, ["alpha_score", "composite_score", "score"], 0)))
    validation_score = max(safe_float(top.get("validation_score")), safe_float(first_value(payload, ["validation_score", "quality_score"], 0)))
    rr = safe_float(top.get("risk_reward"))
    signal_success = validation_success(opportunities)
    model_count, model_rows = active_models(payload)
    grade = institutional_grade(confidence, validation_score, alpha_score, rr)
    regime = extract_regime(payload)
    drivers = extract_market_drivers(payload)
    committee_votes = extract_committee_votes(payload, opportunities)

    decision = top.get("signal") or "WATCH"
    top_pair = top.get("pair") or "N/A"
    status = top.get("status") or ("READY" if opportunities else "NO SIGNALS")

    return {
        "status": payload.get("status", "READY"),
        "generated_at": payload.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "recommendation": {
            "pair": top_pair,
            "signal": decision,
            "confidence": round(confidence, 2),
            "validation_score": round(validation_score, 2),
            "alpha_score": round(alpha_score, 2),
            "risk_reward": round(rr, 2),
            "expected_return": top.get("expected_return", "N/A"),
            "grade": grade,
            "status": status,
            "strategy": top.get("strategy", "Institutional"),
            "rationale": top.get("rationale", ""),
        },
        "summary": {
            "ai_confidence": round(confidence, 2),
            "alpha_score": round(alpha_score, 2),
            "institutional_grade": grade,
            "active_models": model_count,
            "signals": len(opportunities),
            "signal_success": round(signal_success, 2),
            "top_pair": top_pair,
        },
        "regime": regime,
        "opportunities": opportunities,
        "market_drivers": drivers,
        "committee_votes": committee_votes,
        "model_health": model_rows,
        "raw_payload": payload,
    }
