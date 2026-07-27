"""
modules/crypto/crypto_investigation_ai_engine.py

Sprint CR-5: Autonomous Investigation Engine -- AI summarization and
recommendation.

Reuses this app's existing, established Anthropic integration
(modules/crypto/crypto_ai.py's _claude() wrapper and
_extract_json_payload() helper) rather than building new LLM plumbing
-- same tenant-scoped API key system already used throughout CR-1
through CR-4.

IMPORTANT, by design: recommended_actions are advisory only, for a
human analyst to review and decide on -- never auto-executed. This
mirrors the same caution already applied to the Forex terminal's
autonomous trading cycle (the AI picks; a human -- or a separate,
explicit action -- still has to act). An LLM narrative and
risk_level here are a starting point for investigation, not a
compliance determination.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

VALID_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

SYSTEM_PROMPT = """You are an investigative assistant helping a human financial-crime \
analyst review a cryptocurrency wallet. You are given real, already-verified evidence \
gathered from sanctions lists, malicious-address databases, and internally-tracked \
threat actor/campaign/fraud-cluster associations -- not raw, unverified claims.

Your job is to write a short, factual summary of what the evidence shows, and suggest \
a risk_level and a short list of recommended_actions for the human analyst to consider. \
You are NOT making a final determination -- your output is a starting point for a human \
review, not a decision. Do not invent evidence beyond what's provided. If the evidence \
is thin or inconclusive, say so plainly rather than overstating confidence.

Respond with ONLY a JSON object, no other text, in exactly this shape:
{
  "summary": "<2-4 sentence factual summary of what the evidence shows>",
  "risk_level": "<LOW | MEDIUM | HIGH | CRITICAL>",
  "recommended_actions": ["<short, specific action a human analyst could take>", ...],
  "confidence_note": "<one sentence on how strong or thin the underlying evidence is>"
}"""


def _build_evidence_prompt(evidence: Dict[str, Any]) -> str:
    import json

    return (
        f"Wallet address: {evidence['address']}\n"
        f"Chain: {evidence['chain']}\n\n"
        f"Risk assessment (from sanctions + malicious-address checks):\n"
        f"{json.dumps(evidence['risk_assessment'], indent=2, default=str)}\n\n"
        f"Existing risk flags on this address:\n"
        f"{json.dumps(evidence['existing_flags'], indent=2, default=str)}\n\n"
        f"Known threat-intelligence associations (actors/campaigns/clusters):\n"
        f"{json.dumps(evidence['entity_associations'], indent=2, default=str)}"
    )


def run_ai_investigation(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """
    Takes an evidence snapshot (from crypto_investigation_evidence_
    gatherer.gather_evidence()) and produces an AI narrative summary
    and advisory recommendations. Returns status="unavailable" (not
    "error") if no Anthropic key is configured -- the existing
    _claude() wrapper already reports this honestly
    ("ANTHROPIC_API_KEY not found"), matching the same
    ok/unavailable/error distinction already used for CR-4's DefiLlama
    integration.
    """
    from modules.crypto.crypto_ai import _claude, _extract_json_payload

    prompt = _build_evidence_prompt(evidence)

    raw = _claude(prompt, system=SYSTEM_PROMPT, max_tokens=600)

    if raw.startswith("⚠️") or raw.startswith("AI unavailable"):
        return {"status": "unavailable", "message": raw}

    try:
        parsed = _extract_json_payload(raw)
    except Exception as exc:
        return {"status": "error", "message": f"Could not parse AI response: {exc}", "raw": raw}

    if not isinstance(parsed, dict):
        return {"status": "error", "message": f"Unexpected AI response shape: {type(parsed)}", "raw": raw}

    risk_level = str(parsed.get("risk_level", "")).upper()
    if risk_level not in VALID_RISK_LEVELS:
        risk_level = "MEDIUM"  # a safe, non-alarmist, non-dismissive default if the model returns something unexpected

    recommended_actions = parsed.get("recommended_actions")
    if not isinstance(recommended_actions, list):
        recommended_actions = []

    return {
        "status": "ok",
        "summary": str(parsed.get("summary", "")).strip(),
        "risk_level": risk_level,
        "recommended_actions": [str(a) for a in recommended_actions],
        "confidence_note": str(parsed.get("confidence_note", "")).strip(),
    }


def investigate_wallet(*, db, address: str, chain: str, tenant_id: str, requested_by: str = None) -> Dict[str, Any]:
    """
    The single entry point tying evidence gathering, AI analysis, and
    persistence together -- what the UI calls for a full "Investigate"
    action.
    """
    from modules.crypto.crypto_investigation_evidence_gatherer import gather_evidence
    from modules.crypto.crypto_ai_investigation_repository import get_crypto_ai_investigation_repository

    evidence = gather_evidence(db=db, address=address, chain=chain, tenant_id=tenant_id)
    ai_result = run_ai_investigation(evidence)

    repo = get_crypto_ai_investigation_repository(db=db)

    if ai_result["status"] != "ok":
        investigation_id = repo.save_investigation(
            tenant_id=tenant_id, address=address, chain=chain, status=ai_result["status"].upper(),
            risk_level=None, summary=ai_result.get("message"), recommended_actions=None,
            evidence_snapshot=evidence, requested_by=requested_by,
        )
        return {"status": ai_result["status"], "message": ai_result.get("message"), "investigation_id": investigation_id, "evidence": evidence}

    investigation_id = repo.save_investigation(
        tenant_id=tenant_id, address=address, chain=chain, status="COMPLETE",
        risk_level=ai_result["risk_level"], summary=ai_result["summary"],
        recommended_actions=ai_result["recommended_actions"], evidence_snapshot=evidence,
        requested_by=requested_by,
    )

    return {
        "status": "ok",
        "investigation_id": investigation_id,
        "summary": ai_result["summary"],
        "risk_level": ai_result["risk_level"],
        "recommended_actions": ai_result["recommended_actions"],
        "confidence_note": ai_result["confidence_note"],
        "evidence": evidence,
    }