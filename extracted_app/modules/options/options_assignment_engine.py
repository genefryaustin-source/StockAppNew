"""
Sprint 8 Phase 4 — Assignment & Expiration Intelligence Engine.

Operational assignment / expiration risk layer:
- Short call / short put assignment detection
- Expiration-window risk detection
- Pin risk proxy
- Early exercise risk proxy
- Dividend assignment risk proxy
- ITM/OTM risk classification
- Expiration action queue

This module does not place trades. It generates assignment and expiration
risk diagnostics for dashboards and future command-center consumers.
"""
from __future__ import annotations

from typing import Any
import pandas as pd

from modules.options.options_portfolio_risk_engine import normalize_risk_positions


DEFAULT_ASSIGNMENT_POLICY = {
    "expiration_warning_dte": 7,
    "critical_expiration_dte": 2,
    "assignment_risk_dte": 5,
    "high_delta_threshold": 0.70,
    "very_high_delta_threshold": 0.85,
    "pin_risk_pct": 1.0,
    "itm_buffer_pct": 0.0,
    "dividend_warning_dte": 10,
}


def _empty(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_str(value: Any, default: str = "") -> str:
    try:
        if value is None:
            return default
        return str(value)
    except Exception:
        return default


def normalize_assignment_positions(positions: Any) -> pd.DataFrame:
    df = normalize_risk_positions(positions)
    if df.empty:
        return df

    df = df.copy()

    defaults = {
        "underlying": "",
        "option_symbol": "",
        "option_type": "",
        "type": "",
        "strategy": "Unclassified",
        "expiry": "",
        "dte": 0,
        "strike": 0,
        "underlying_price": 0,
        "last_underlying_price": 0,
        "spot": 0,
        "qty": 0,
        "delta": 0,
        "gamma": 0,
        "theta": 0,
        "market_value": 0,
        "unrealized_pnl": 0,
        "ex_dividend_date": "",
        "dividend_amount": 0,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    numeric_cols = [
        "dte",
        "strike",
        "underlying_price",
        "last_underlying_price",
        "spot",
        "qty",
        "delta",
        "gamma",
        "theta",
        "market_value",
        "unrealized_pnl",
        "dividend_amount",
        "notional_proxy",
        "net_delta",
        "net_gamma",
        "net_theta",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["option_type"] = (
        df["option_type"]
        .fillna("")
        .astype(str)
        .replace("", pd.NA)
        .fillna(df["type"].fillna("").astype(str))
        .fillna("")
        .astype(str)
        .str.lower()
    )

    df["strategy"] = df["strategy"].fillna("Unclassified").replace("", "Unclassified").astype(str)

    df["underlying_price"] = (
        df["underlying_price"]
        .where(df["underlying_price"] > 0, df["last_underlying_price"])
        .where(lambda s: s > 0, df["spot"])
    )

    return df


def classify_moneyness(row: pd.Series, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_ASSIGNMENT_POLICY

    opt_type = _safe_str(row.get("option_type")).lower()
    strike = _num(row.get("strike"), 0)
    spot = _num(row.get("underlying_price"), 0)

    if strike <= 0 or spot <= 0 or opt_type not in {"call", "put"}:
        return {
            "Moneyness": "UNKNOWN",
            "Moneyness %": 0.0,
            "ITM": False,
            "Distance To Strike %": 0.0,
        }

    distance_pct = (spot - strike) / strike * 100

    if opt_type == "call":
        itm = spot > strike * (1 + policy.get("itm_buffer_pct", 0) / 100)
        money_pct = distance_pct
    else:
        itm = spot < strike * (1 - policy.get("itm_buffer_pct", 0) / 100)
        money_pct = -distance_pct

    if itm and money_pct >= 5:
        moneyness = "DEEP_ITM"
    elif itm:
        moneyness = "ITM"
    elif abs(distance_pct) <= policy["pin_risk_pct"]:
        moneyness = "ATM_PIN_ZONE"
    else:
        moneyness = "OTM"

    return {
        "Moneyness": moneyness,
        "Moneyness %": round(money_pct, 2),
        "ITM": bool(itm),
        "Distance To Strike %": round(distance_pct, 2),
    }


def score_assignment_risk(row: pd.Series, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_ASSIGNMENT_POLICY

    qty = _num(row.get("qty"), 0)
    dte = _num(row.get("dte"), 0)
    delta = abs(_num(row.get("delta"), 0))
    opt_type = _safe_str(row.get("option_type")).lower()
    dividend = _num(row.get("dividend_amount"), 0)

    money = classify_moneyness(row, policy)

    score = 0.0
    flags = []

    is_short = qty < 0
    is_option = opt_type in {"call", "put"}

    if not is_option:
        return {
            "Assignment Risk Score": 0.0,
            "Assignment Risk": "NONE",
            "Assignment Flags": "Not an option position.",
            **money,
        }

    if is_short:
        score += 20
        flags.append("Short option position.")

    if is_short and money["ITM"]:
        score += 30
        flags.append("Short option is ITM.")

    if is_short and money["Moneyness"] == "DEEP_ITM":
        score += 20
        flags.append("Short option is deep ITM.")

    if is_short and 0 <= dte <= policy["assignment_risk_dte"]:
        score += 25
        flags.append("Within assignment-risk DTE window.")

    if is_short and delta >= policy["very_high_delta_threshold"]:
        score += 20
        flags.append("Very high delta assignment proxy.")
    elif is_short and delta >= policy["high_delta_threshold"]:
        score += 12
        flags.append("High delta assignment proxy.")

    if is_short and opt_type == "call" and dividend > 0 and 0 <= dte <= policy["dividend_warning_dte"]:
        score += 20
        flags.append("Dividend early-exercise risk proxy.")

    if money["Moneyness"] == "ATM_PIN_ZONE" and 0 <= dte <= policy["expiration_warning_dte"]:
        score += 15
        flags.append("Pin-risk zone near expiration.")

    score = round(max(0, min(100, score)), 2)

    if score >= 80:
        level = "CRITICAL"
    elif score >= 60:
        level = "HIGH"
    elif score >= 35:
        level = "MEDIUM"
    elif score > 0:
        level = "LOW"
    else:
        level = "NONE"

    return {
        "Assignment Risk Score": score,
        "Assignment Risk": level,
        "Assignment Flags": "; ".join(flags) if flags else "No assignment risk flags.",
        **money,
    }


def score_expiration_risk(row: pd.Series, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_ASSIGNMENT_POLICY

    dte = _num(row.get("dte"), 0)
    gamma = abs(_num(row.get("gamma"), 0))
    theta = _num(row.get("theta"), 0)
    money = classify_moneyness(row, policy)

    score = 0.0
    flags = []

    if 0 <= dte <= policy["critical_expiration_dte"]:
        score += 40
        flags.append("Critical expiration window.")
    elif 0 <= dte <= policy["expiration_warning_dte"]:
        score += 25
        flags.append("Expiration warning window.")

    if money["Moneyness"] == "ATM_PIN_ZONE":
        score += 25
        flags.append("Pin-risk zone.")

    if money["ITM"]:
        score += 20
        flags.append("Position is ITM into expiration window.")

    if gamma > 0.05 and 0 <= dte <= policy["expiration_warning_dte"]:
        score += 15
        flags.append("Gamma risk near expiration.")

    if theta < -25 and 0 <= dte <= policy["expiration_warning_dte"]:
        score += 10
        flags.append("Theta decay pressure.")

    score = round(max(0, min(100, score)), 2)

    if score >= 80:
        level = "CRITICAL"
    elif score >= 60:
        level = "HIGH"
    elif score >= 35:
        level = "MEDIUM"
    elif score > 0:
        level = "LOW"
    else:
        level = "NONE"

    return {
        "Expiration Risk Score": score,
        "Expiration Risk": level,
        "Expiration Flags": "; ".join(flags) if flags else "No expiration risk flags.",
    }


def recommend_assignment_action(assignment: dict[str, Any], expiration: dict[str, Any], row: pd.Series) -> str:
    assignment_level = assignment.get("Assignment Risk", "NONE")
    expiration_level = expiration.get("Expiration Risk", "NONE")
    money = assignment.get("Moneyness", "UNKNOWN")
    qty = _num(row.get("qty"), 0)

    if assignment_level == "CRITICAL":
        return "Close / Roll Immediately"

    if expiration_level == "CRITICAL" and qty < 0:
        return "Close / Roll"

    if assignment_level == "HIGH":
        return "Roll / Close"

    if expiration_level == "HIGH":
        return "Review Expiration Plan"

    if money == "ATM_PIN_ZONE":
        return "Monitor Pin Risk"

    if assignment_level == "MEDIUM" or expiration_level == "MEDIUM":
        return "Monitor / Prepare Roll"

    return "Hold"


def analyze_assignment_expiration_risk(
    positions: Any,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_ASSIGNMENT_POLICY
    df = normalize_assignment_positions(positions)

    if df.empty:
        return {"available": False, "reason": "No positions available.", "positions": df}

    rows = []
    for _, row in df.iterrows():
        assignment = score_assignment_risk(row, policy)
        expiration = score_expiration_risk(row, policy)
        action = recommend_assignment_action(assignment, expiration, row)

        rows.append({
            **assignment,
            **expiration,
            "Recommended Action": action,
        })

    scored = pd.DataFrame(rows)
    enriched = pd.concat([df.reset_index(drop=True), scored.reset_index(drop=True)], axis=1)

    queue = enriched[
        (enriched["Assignment Risk"].isin(["CRITICAL", "HIGH", "MEDIUM"]))
        | (enriched["Expiration Risk"].isin(["CRITICAL", "HIGH", "MEDIUM"]))
        | (enriched["Recommended Action"] != "Hold")
    ].copy()

    priority = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NONE": 4}
    if not queue.empty:
        queue["_assignment_priority"] = queue["Assignment Risk"].map(priority).fillna(9)
        queue["_expiration_priority"] = queue["Expiration Risk"].map(priority).fillna(9)
        queue = queue.sort_values(
            ["_assignment_priority", "_expiration_priority", "Assignment Risk Score", "Expiration Risk Score"],
            ascending=[True, True, False, False],
        ).drop(columns=["_assignment_priority", "_expiration_priority"]).reset_index(drop=True)

    summary = {
        "position_count": int(len(enriched)),
        "assignment_alert_count": int(len(queue)),
        "critical_assignment_count": int((enriched["Assignment Risk"] == "CRITICAL").sum()),
        "high_assignment_count": int((enriched["Assignment Risk"] == "HIGH").sum()),
        "critical_expiration_count": int((enriched["Expiration Risk"] == "CRITICAL").sum()),
        "high_expiration_count": int((enriched["Expiration Risk"] == "HIGH").sum()),
        "pin_risk_count": int((enriched["Moneyness"] == "ATM_PIN_ZONE").sum()),
        "itm_short_count": int(((enriched["ITM"] == True) & (enriched["qty"] < 0)).sum()),
        "avg_assignment_score": round(float(enriched["Assignment Risk Score"].mean()), 2),
        "avg_expiration_score": round(float(enriched["Expiration Risk Score"].mean()), 2),
    }

    return {
        "available": True,
        "positions": enriched,
        "alert_queue": queue,
        "summary": summary,
        "policy": policy,
    }


def build_assignment_by_underlying(report: dict[str, Any]) -> dict[str, Any]:
    if not report.get("available"):
        return report

    df = report.get("positions")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return _empty("No assignment positions available.")

    table = (
        df.groupby("underlying", as_index=False)
        .agg(
            positions=("underlying", "size"),
            avg_assignment_score=("Assignment Risk Score", "mean"),
            avg_expiration_score=("Expiration Risk Score", "mean"),
            critical_assignment=("Assignment Risk", lambda s: int((s == "CRITICAL").sum())),
            high_assignment=("Assignment Risk", lambda s: int((s == "HIGH").sum())),
            critical_expiration=("Expiration Risk", lambda s: int((s == "CRITICAL").sum())),
            high_expiration=("Expiration Risk", lambda s: int((s == "HIGH").sum())),
            pin_risk=("Moneyness", lambda s: int((s == "ATM_PIN_ZONE").sum())),
        )
        .sort_values(["critical_assignment", "critical_expiration", "avg_assignment_score"], ascending=False)
        .reset_index(drop=True)
    )

    for col in ["avg_assignment_score", "avg_expiration_score"]:
        table[col] = pd.to_numeric(table[col], errors="coerce").fillna(0).round(2)

    return {"available": True, "by_underlying": table}


def build_assignment_expiration_report(
    positions: Any,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = analyze_assignment_expiration_risk(positions, policy=policy)
    if not base.get("available"):
        return base

    by_underlying = build_assignment_by_underlying(base)

    return {
        **base,
        "by_underlying": by_underlying,
    }


def summarize_assignment_expiration(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Assignment intelligence unavailable: {report.get('reason', 'unknown reason')}"

    s = report.get("summary", {})
    return (
        f"Assignment & Expiration Intelligence found {s.get('assignment_alert_count')} alerts "
        f"across {s.get('position_count')} positions. "
        f"{s.get('critical_assignment_count')} critical assignment risks, "
        f"{s.get('critical_expiration_count')} critical expiration risks, "
        f"{s.get('pin_risk_count')} pin-risk positions, and "
        f"{s.get('itm_short_count')} ITM short positions were detected."
    )
