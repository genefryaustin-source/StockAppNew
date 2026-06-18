"""
Sprint 4 Phase 2 — Institutional Flow Regime Engine.
"""
from __future__ import annotations

from typing import Any

from modules.options.options_flow_classifier import classify_flow, summarize_flow_classification
from modules.options.options_flow_confidence_engine import score_flow_confidence, summarize_flow_confidence
from modules.options.options_flow_cluster_engine import cluster_flow, summarize_flow_clusters
from modules.options.options_flow_accumulation_engine import detect_accumulation, summarize_accumulation


def build_flow_regime_report(flow_data: Any, min_volume: int = 100) -> dict[str, Any]:
    classification = classify_flow(flow_data, min_volume=min_volume)
    confidence = score_flow_confidence(classification)
    clusters = cluster_flow(classification)
    accumulation = detect_accumulation(classification)

    if not classification.get("available"):
        regime = "UNAVAILABLE"
        bias = "UNKNOWN"
        score = 0
    else:
        bias = accumulation.get("bias", "NEUTRAL") if accumulation.get("available") else "NEUTRAL"
        conf = confidence.get("confidence_score", 0) if confidence.get("available") else 0
        acc = accumulation.get("accumulation_score", 50) if accumulation.get("available") else 50
        score = round((float(conf) * 0.55) + (abs(float(acc) - 50) * 2 * 0.45), 2)

        if score >= 75 and bias == "BULLISH":
            regime = "INSTITUTIONAL_BULLISH_ACCUMULATION"
        elif score >= 75 and bias == "BEARISH":
            regime = "INSTITUTIONAL_BEARISH_DISTRIBUTION"
        elif score >= 55:
            regime = f"{bias}_FLOW"
        else:
            regime = "NOISY_OR_MIXED_FLOW"

    return {
        "available": classification.get("available", False),
        "regime": regime,
        "bias": bias,
        "regime_score": score,
        "classification": classification,
        "confidence": confidence,
        "clusters": clusters,
        "accumulation": accumulation,
        "summary": [
            summarize_flow_classification(classification),
            summarize_flow_confidence(confidence),
            summarize_flow_clusters(clusters),
            summarize_accumulation(accumulation),
        ],
    }


def summarize_flow_regime(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return "Flow regime unavailable."
    return f"Flow regime: {report.get('regime')} with score {report.get('regime_score')}/100."
