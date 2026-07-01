
"""
modules/forex/ui/forex_ai_consensus_engine.py

Sprint 25 Phase 2
Institutional AI Consensus Engine.

Purpose
-------
Converts the AI/Quant payload into a model-by-model institutional consensus:
- model votes
- model confidence
- agreement score
- weighted AI confidence
- final executive decision
- attribution matrix

This module is intentionally UI-safe and does not import Streamlit.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace("%", "").replace(",", "").replace("$", "").strip()
            if value in {"", "-", "—", "None", "nan"}:
                return default
        return float(value)
    except Exception:
        return default


def normalize_pair(pair: Any, default: str = "N/A") -> str:
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
            value = payload.get(key)
            if value not in (None, ""):
                return value
        for node in walk(payload):
            if not isinstance(node, dict):
                continue
            for key in keys:
                value = node.get(key)
                if value not in (None, ""):
                    return value
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
                for name, detail in value.items():
                    if isinstance(detail, dict):
                        row = dict(detail)
                        row.setdefault("pair", name)
                        rows.append(row)
    return rows


def normalize_signal(value: Any) -> str:
    signal = str(value or "HOLD").upper()
    if signal in {"STRONG_BUY", "BUY", "LONG", "BULLISH", "APPROVE", "APPROVED"}:
        return "BUY"
    if signal in {"STRONG_SELL", "SELL", "SHORT", "BEARISH", "REDUCE", "REJECT", "REJECTED"}:
        return "SELL"
    if signal in {"WATCH", "REVIEW", "UNDER REVIEW", "PENDING"}:
        return "WATCH"
    return "HOLD"


def row_score(row: Dict[str, Any]) -> float:
    keys = [
        "confidence",
        "confidence_score",
        "ai_confidence",
        "validation_score",
        "composite_score",
        "alpha_score",
        "score",
        "quality_score",
        "conviction",
        "conviction_score",
        "macro_score",
        "sentiment_score",
        "technical_score",
    ]
    return max([safe_float(row.get(k)) for k in keys] + [0.0])


def extract_top_row(payload: Dict[str, Any]) -> Dict[str, Any]:
    rows = collect_rows(
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
    clean = []
    seen = set()
    for index, row in enumerate(rows):
        pair = normalize_pair(row.get("pair") or row.get("symbol") or row.get("currency_pair") or f"FX-{index+1}")
        signal = normalize_signal(row.get("signal") or row.get("recommendation") or row.get("action") or row.get("side"))
        key = (pair, signal)
        if key in seen:
            continue
        seen.add(key)
        item = dict(row)
        item["pair"] = pair
        item["signal"] = signal
        item["score"] = row_score(row)
        item["risk_reward"] = safe_float(row.get("risk_reward") or row.get("rr"))
        clean.append(item)
    clean.sort(key=lambda r: (safe_float(r.get("score")), safe_float(r.get("risk_reward"))), reverse=True)
    return clean[0] if clean else {}


MODEL_CONFIG = [
    {
        "name": "Alpha Model",
        "weight": 0.20,
        "section_keys": ["alpha_research", "alpha_model"],
        "score_keys": ["alpha_score", "composite_score", "score", "confidence"],
    },
    {
        "name": "Signal Validation",
        "weight": 0.20,
        "section_keys": ["signal_validation", "validation"],
        "score_keys": ["validation_score", "quality_score", "confidence", "success_rate"],
    },
    {
        "name": "Macro Regime",
        "weight": 0.15,
        "section_keys": ["regime", "market_regime", "macro_regime"],
        "score_keys": ["macro_score", "regime_score", "confidence", "score"],
    },
    {
        "name": "Currency Strength",
        "weight": 0.12,
        "section_keys": ["currency_strength", "strength"],
        "score_keys": ["strength_score", "score", "confidence"],
    },
    {
        "name": "Sentiment",
        "weight": 0.10,
        "section_keys": ["sentiment", "market_sentiment"],
        "score_keys": ["sentiment_score", "confidence", "score"],
    },
    {
        "name": "Risk",
        "weight": 0.10,
        "section_keys": ["risk", "risk_engine", "portfolio_risk"],
        "score_keys": ["risk_score", "quality_score", "confidence", "score"],
    },
    {
        "name": "Portfolio Optimizer",
        "weight": 0.08,
        "section_keys": ["portfolio_optimizer", "optimizer"],
        "score_keys": ["optimization_score", "confidence", "score", "sharpe"],
    },
    {
        "name": "Execution",
        "weight": 0.05,
        "section_keys": ["execution", "execution_algorithms", "execution_center"],
        "score_keys": ["execution_score", "confidence", "fill_rate", "score"],
    },
]


def get_section(payload: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        value = payload.get(key) if isinstance(payload, dict) else None
        if value not in (None, {}, []):
            return value
    for node in walk(payload):
        if not isinstance(node, dict):
            continue
        for key in keys:
            value = node.get(key)
            if value not in (None, {}, []):
                return value
    return None


def infer_model_vote(
    model_name: str,
    section: Any,
    top_signal: str,
    top_pair: str,
    score_keys: List[str],
) -> Dict[str, Any]:
    if section is None:
        return {
            "Model": model_name,
            "Vote": "MISSING",
            "Pair": top_pair,
            "Confidence": 0.0,
            "Agreement": False,
            "Status": "MISSING",
            "Reason": "No payload section found.",
        }

    vote = None
    pair = top_pair
    confidence = 0.0
    reason = ""

    if isinstance(section, str):
        vote = normalize_signal(section)
        confidence = 60.0 if vote in {"BUY", "SELL", "WATCH"} else 0.0
        reason = section

    elif isinstance(section, dict):
        pair = normalize_pair(
            section.get("pair")
            or section.get("symbol")
            or section.get("top_pair")
            or section.get("currency_pair")
            or top_pair
        )
        vote = normalize_signal(
            section.get("vote")
            or section.get("signal")
            or section.get("recommendation")
            or section.get("decision")
            or section.get("status")
            or top_signal
        )
        confidence = max([safe_float(section.get(k)) for k in score_keys] + [row_score(section)])
        reason = str(section.get("reason") or section.get("rationale") or section.get("summary") or "")

        rows = collect_rows(section, ("signals", "recommendations", "ideas", "rows", "rankings", "validated_signals"))
        if rows:
            rows.sort(key=row_score, reverse=True)
            best = rows[0]
            pair = normalize_pair(best.get("pair") or best.get("symbol") or pair)
            vote = normalize_signal(best.get("signal") or best.get("recommendation") or vote)
            confidence = max(confidence, row_score(best))
            reason = reason or str(best.get("rationale") or best.get("reason") or "")

    elif isinstance(section, list):
        rows = [x for x in section if isinstance(x, dict)]
        if rows:
            rows.sort(key=row_score, reverse=True)
            best = rows[0]
            pair = normalize_pair(best.get("pair") or best.get("symbol") or top_pair)
            vote = normalize_signal(best.get("signal") or best.get("recommendation") or top_signal)
            confidence = row_score(best)
            reason = str(best.get("rationale") or best.get("reason") or "")

    vote = vote or "HOLD"
    agreement = vote == top_signal if vote in {"BUY", "SELL", "WATCH"} else False
    status = "READY" if confidence > 0 else "MISSING"

    return {
        "Model": model_name,
        "Vote": vote,
        "Pair": pair,
        "Confidence": round(confidence, 2),
        "Agreement": agreement,
        "Status": status,
        "Reason": reason,
    }


def build_consensus(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    top = extract_top_row(payload)

    top_pair = normalize_pair(
        top.get("pair")
        or first_value(payload, ["top_pair", "pair", "symbol"], "N/A"),
        default="N/A",
    )
    top_signal = normalize_signal(
        top.get("signal")
        or top.get("recommendation")
        or first_value(payload, ["signal", "recommendation", "decision"], "WATCH")
    )

    votes: List[Dict[str, Any]] = []
    weighted_total = 0.0
    weight_used = 0.0

    for config in MODEL_CONFIG:
        section = get_section(payload, config["section_keys"])
        vote = infer_model_vote(
            config["name"],
            section,
            top_signal,
            top_pair,
            config["score_keys"],
        )
        vote["Weight"] = config["weight"]
        votes.append(vote)
        if vote["Status"] != "MISSING":
            weighted_total += safe_float(vote["Confidence"]) * config["weight"]
            weight_used += config["weight"]

    weighted_confidence = weighted_total / weight_used if weight_used > 0 else 0.0
    active_votes = [v for v in votes if v["Status"] != "MISSING"]
    agreement_votes = [v for v in active_votes if v["Agreement"]]
    agreement_score = len(agreement_votes) / len(active_votes) * 100 if active_votes else 0.0

    buy_count = len([v for v in active_votes if v["Vote"] == "BUY"])
    sell_count = len([v for v in active_votes if v["Vote"] == "SELL"])
    watch_count = len([v for v in active_votes if v["Vote"] == "WATCH"])
    hold_count = len(active_votes) - buy_count - sell_count - watch_count

    if buy_count > sell_count and buy_count >= watch_count:
        decision = "BUY"
    elif sell_count > buy_count and sell_count >= watch_count:
        decision = "SELL"
    elif watch_count:
        decision = "WATCH"
    else:
        decision = "HOLD"

    if weighted_confidence >= 88 and agreement_score >= 70:
        status = "APPROVED"
    elif weighted_confidence >= 75:
        status = "PAPER VERIFIED"
    elif weighted_confidence >= 60:
        status = "UNDER REVIEW"
    else:
        status = "WATCH"

    attribution = []
    for vote in votes:
        contribution = safe_float(vote.get("Confidence")) * safe_float(vote.get("Weight"))
        attribution.append(
            {
                "Model": vote["Model"],
                "Vote": vote["Vote"],
                "Confidence": vote["Confidence"],
                "Weight": vote["Weight"],
                "Contribution": round(contribution, 2),
                "Agreement": vote["Agreement"],
                "Status": vote["Status"],
            }
        )

    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "top_pair": top_pair,
        "top_signal": top_signal,
        "executive_decision": decision,
        "weighted_confidence": round(weighted_confidence, 2),
        "agreement_score": round(agreement_score, 2),
        "active_models": len(active_votes),
        "total_models": len(votes),
        "vote_counts": {
            "BUY": buy_count,
            "SELL": sell_count,
            "WATCH": watch_count,
            "HOLD": hold_count,
        },
        "votes": votes,
        "attribution": attribution,
    }


def consensus_summary_text(consensus: Dict[str, Any]) -> str:
    counts = consensus.get("vote_counts", {})
    return (
        f"Consensus engine reports **{consensus.get('active_models', 0)} active models** "
        f"out of **{consensus.get('total_models', 0)}**. Final decision is "
        f"**{consensus.get('executive_decision', 'WATCH')} {consensus.get('top_pair', 'N/A')}** "
        f"with weighted confidence **{safe_float(consensus.get('weighted_confidence')):.0f}%** "
        f"and model agreement **{safe_float(consensus.get('agreement_score')):.0f}%**. "
        f"Vote split: BUY **{counts.get('BUY', 0)}**, SELL **{counts.get('SELL', 0)}**, "
        f"WATCH **{counts.get('WATCH', 0)}**, HOLD **{counts.get('HOLD', 0)}**."
    )
