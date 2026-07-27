"""
modules/hf/research_committee_v2.py

HF-2 committee upgrade that converts multi-agent signals into an investment
committee packet and voting summary.
"""
from __future__ import annotations
from typing import Any


def build_committee_packet(report: dict[str, Any]) -> dict[str, Any]:
    ticker = report.get("ticker", "")
    signals = list(report.get("signals") or [])
    consensus = dict(report.get("consensus") or {})

    buys = [s for s in signals if str(s.get("rating")) in {"Buy", "Strong Buy"}]
    sells = [s for s in signals if str(s.get("rating")) in {"Sell", "Strong Sell", "Reduce"}]
    holds = [s for s in signals if str(s.get("rating")) == "Hold"]

    decision = _decision_from_consensus(consensus)
    return {
        "ticker": ticker,
        "decision": decision,
        "consensus_rating": consensus.get("rating", "Hold"),
        "consensus_score": consensus.get("score", 50.0),
        "confidence": consensus.get("confidence", 0.0),
        "agreement": consensus.get("agreement", 0.0),
        "buy_votes": len(buys),
        "hold_votes": len(holds),
        "sell_votes": len(sells),
        "bull_case": _summarize_points(signals, "positives"),
        "bear_case": _summarize_points(signals, "risks"),
        "required_actions": _required_actions(consensus, sells),
    }


def _decision_from_consensus(consensus: dict[str, Any]) -> str:
    score = float(consensus.get("score", 50) or 50)
    confidence = float(consensus.get("confidence", 0) or 0)
    disagreement = float(consensus.get("disagreement", 100) or 100)
    if score >= 75 and confidence >= 60 and disagreement < 65:
        return "Approve for Portfolio Candidate List"
    if score >= 60:
        return "Approve for Watchlist / Further Diligence"
    if score <= 35:
        return "Reject / Avoid"
    return "Hold for More Evidence"


def _summarize_points(signals: list[dict[str, Any]], key: str) -> list[str]:
    seen = set()
    out = []
    for sig in signals:
        for item in list(sig.get(key) or []):
            if item not in seen:
                seen.add(item)
                out.append(item)
            if len(out) >= 8:
                return out
    return out


def _required_actions(consensus: dict[str, Any], negative_votes: list[dict[str, Any]]) -> list[str]:
    actions = []
    if float(consensus.get("confidence", 0) or 0) < 55:
        actions.append("Increase data coverage before final approval")
    if float(consensus.get("disagreement", 0) or 0) > 60:
        actions.append("Escalate to investment council due to analyst disagreement")
    if negative_votes:
        actions.append("Review negative analyst votes before sizing")
    return actions or ["No blocking committee actions"]

def build_research_committee(ticker: str, db=None):
    return [
        {
            "analyst": "Fundamental Analyst",
            "rating": "Buy",
            "score": 75,
            "commentary": f"{ticker} shows solid fundamentals."
        },
        {
            "analyst": "Valuation Analyst",
            "rating": "Hold",
            "score": 65,
            "commentary": f"{ticker} appears fairly valued."
        },
        {
            "analyst": "Risk Analyst",
            "rating": "Buy",
            "score": 70,
            "commentary": f"{ticker} risk profile is acceptable."
        }
    ]