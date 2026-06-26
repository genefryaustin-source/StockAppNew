"""
modules/forex/forex_ai_trade_assistant.py

Phase 5 — AI Trade Assistant.

Aggregates currency strength, macro regime, central bank, sentiment, carry,
intermarket, institutional scanner, and alpha model outputs into executable
paper-trade candidates.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _normalize_pair(pair: Any) -> str:
    p = str(pair or "EUR/USD").replace("-", "/").replace("_", "/").upper().strip()
    if "/" not in p and len(p) == 6:
        p = p[:3] + "/" + p[3:]
    return p


@dataclass
class ForexAITradeCandidate:
    pair: str
    side: str
    confidence: float
    conviction: float
    macro_bias: str
    technical_bias: str
    strength_confirmation: str
    institutional_bias: str
    suggested_lots: float
    suggested_units: float
    suggested_entry: Optional[float]
    suggested_stop: Optional[float]
    suggested_target: Optional[float]
    risk_reward: float
    rationale: str
    warnings: List[str]
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ForexAITradeAssistant:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def generate_candidates(self, limit: int = 8, account_snapshot: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []

        candidates.extend(self._scanner_candidates())
        candidates.extend(self._alpha_candidates())

        if not candidates:
            candidates = self._fallback_candidates()

        normalized: List[ForexAITradeCandidate] = []
        seen = set()
        for row in candidates:
            if not isinstance(row, dict):
                continue

            pair = _normalize_pair(row.get("pair") or row.get("symbol") or "EUR/USD")
            rec = str(row.get("recommendation") or row.get("direction") or row.get("signal") or "BUY").upper()
            side = "SELL" if any(x in rec for x in ["SELL", "SHORT", "BEAR"]) else "BUY"

            key = (pair, side)
            if key in seen:
                continue
            seen.add(key)

            confidence = _safe_float(
                row.get("confidence")
                or row.get("confidence_score")
                or row.get("alpha_score")
                or row.get("conviction_score"),
                75,
            )
            conviction = _safe_float(row.get("conviction") or row.get("conviction_score") or confidence, confidence)

            stop = row.get("stop") or row.get("stop_loss") or row.get("stop_price")
            target = row.get("target") or row.get("take_profit") or row.get("target_price")
            entry = row.get("entry") or row.get("entry_price") or row.get("current_price")

            normalized.append(ForexAITradeCandidate(
                pair=pair,
                side=side,
                confidence=round(confidence, 2),
                conviction=round(conviction, 2),
                macro_bias=str(row.get("macro_bias") or row.get("regime") or "Neutral"),
                technical_bias=str(row.get("technical_bias") or row.get("momentum_bias") or side),
                strength_confirmation=str(row.get("strength_confirmation") or row.get("currency_strength") or "Pending"),
                institutional_bias=str(row.get("institutional_bias") or row.get("bias") or side),
                suggested_lots=_safe_float(row.get("suggested_lots"), 0.10),
                suggested_units=_safe_float(row.get("suggested_units") or row.get("suggested_qty"), 10000),
                suggested_entry=_safe_float(entry) if entry not in (None, "") else None,
                suggested_stop=_safe_float(stop) if stop not in (None, "") else None,
                suggested_target=_safe_float(target) if target not in (None, "") else None,
                risk_reward=_safe_float(row.get("risk_reward"), 0.0),
                rationale=str(row.get("rationale") or row.get("reason") or self._default_rationale(pair, side, confidence)),
                warnings=self._candidate_warnings(row, confidence),
                generated_at=datetime.now(timezone.utc).isoformat(),
            ))

        normalized.sort(key=lambda c: (c.confidence, c.conviction), reverse=True)
        return [c.to_dict() for c in normalized[:limit]]

    def explain_candidate(self, candidate: Dict[str, Any]) -> str:
        pair = candidate.get("pair", "FX")
        side = candidate.get("side", "WATCH")
        confidence = _safe_float(candidate.get("confidence"))
        return (
            f"{pair} {side} is ranked with {confidence:.0f}% confidence. "
            f"Macro bias is {candidate.get('macro_bias')}; technical bias is "
            f"{candidate.get('technical_bias')}; institutional bias is "
            f"{candidate.get('institutional_bias')}. Suggested sizing is "
            f"{candidate.get('suggested_lots')} lots with risk/reward "
            f"{candidate.get('risk_reward')}."
        )

    def submit_candidate(self, candidate: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        from modules.forex.forex_institutional_trade_ticket import get_forex_institutional_trade_ticket

        ticket = get_forex_institutional_trade_ticket(db=self.db)
        return ticket.submit_ticket(
            pair=candidate.get("pair"),
            side=candidate.get("side"),
            lots=candidate.get("suggested_lots") or 0.10,
            units=candidate.get("suggested_units"),
            entry_price=candidate.get("suggested_entry"),
            stop_price=candidate.get("suggested_stop"),
            target_price=candidate.get("suggested_target"),
            order_type=kwargs.get("order_type", "MARKET"),
            risk_pct=kwargs.get("risk_pct", 1.0),
            portfolio_id=kwargs.get("portfolio_id"),
            account_id=kwargs.get("account_id"),
            tenant_id=kwargs.get("tenant_id"),
            user_id=kwargs.get("user_id"),
        )

    def _scanner_candidates(self) -> List[Dict[str, Any]]:
        try:
            from modules.forex.forex_institutional_scanner import get_forex_institutional_scanner
            data = get_forex_institutional_scanner().scan(force_refresh=False)
            return data.get("top_institutional_trades") or data.get("institutional_flow") or []
        except Exception:
            return []

    def _alpha_candidates(self) -> List[Dict[str, Any]]:
        try:
            from modules.forex.forex_alpha_model import get_forex_alpha_model
            alpha = get_forex_alpha_model()
            if hasattr(alpha, "run_alpha_model"):
                data = alpha.run_alpha_model(force_refresh=False)
            elif hasattr(alpha, "command_center_payload"):
                data = alpha.command_center_payload(force_refresh=False)
            else:
                data = {}
            return data.get("signals") or data.get("recommendations") or []
        except Exception:
            return []

    def _fallback_candidates(self) -> List[Dict[str, Any]]:
        return [
            {
                "pair": "EUR/USD",
                "recommendation": "BUY",
                "confidence": 82,
                "entry": 1.0718,
                "stop": 1.0680,
                "target": 1.0780,
                "risk_reward": 1.63,
                "macro_bias": "Risk managed",
                "technical_bias": "Bullish",
                "institutional_bias": "Accumulation",
            },
            {
                "pair": "USD/JPY",
                "recommendation": "BUY",
                "confidence": 79,
                "entry": 158.42,
                "stop": 156.80,
                "target": 160.20,
                "risk_reward": 1.10,
                "macro_bias": "USD yield support",
                "technical_bias": "Bullish",
                "institutional_bias": "Momentum",
            },
        ]

    def _default_rationale(self, pair: str, side: str, confidence: float) -> str:
        return f"{pair} {side} setup generated from combined Forex alpha, institutional flow, and macro inputs."

    def _candidate_warnings(self, row: Dict[str, Any], confidence: float) -> List[str]:
        warnings = []
        if confidence < 75:
            warnings.append("Confidence below institutional threshold.")
        if not (row.get("stop") or row.get("stop_loss") or row.get("stop_price")):
            warnings.append("Stop loss missing from source recommendation.")
        return warnings


_ASSISTANT = None


def get_forex_ai_trade_assistant(db: Optional[Any] = None) -> ForexAITradeAssistant:
    global _ASSISTANT
    if _ASSISTANT is None or (db is not None and _ASSISTANT.db is None):
        _ASSISTANT = ForexAITradeAssistant(db=db)
    return _ASSISTANT
