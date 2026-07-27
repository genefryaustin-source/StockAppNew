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
        # Disable alpha expansion in AI Command Center until router quote latency is capped.
        # candidates.extend(self._alpha_candidates())

        # No hardcoded fallback: when the institutional scanner has nothing
        # live to report, this honestly returns an empty candidate list
        # rather than the fixed EUR/USD / USD/JPY pair that used to be
        # shown here regardless of real market conditions.

        # Real macro regime and currency strength, fetched once per call.
        # Previously macro_bias defaulted to a fixed "Neutral" and
        # strength_confirmation to a fixed "Pending" for every single
        # candidate, because the scanner's rows never carried those fields
        # at all -- every row displayed the same two placeholder values
        # regardless of actual conditions. These are now derived from the
        # real macro regime engine and real per-currency strength scores.
        macro_bias_label = self._macro_bias()
        strength_rows = self._strength_rows()

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
                0.0,
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
                macro_bias=str(row.get("macro_bias") or row.get("regime") or macro_bias_label),
                technical_bias=str(row.get("technical_bias") or row.get("momentum_bias") or self._technical_bias(pair, side)),
                strength_confirmation=str(row.get("strength_confirmation") or row.get("currency_strength") or self._confirm_strength(pair, side, strength_rows)),
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

    def _macro_bias(self) -> str:
        """
        Real current macro regime (via forex_macro_regime_engine), mapped
        to a short display label. Returns "Unknown" rather than a fixed
        "Neutral" when the engine has nothing to report.
        """
        try:
            from modules.forex.forex_macro_regime_engine import get_forex_macro_regime_engine
            data = get_forex_macro_regime_engine().analyze()
            regime = str(
                (data.get("macro_regime") or data.get("market_regime") or data.get("regime") or "")
                if isinstance(data, dict) else ""
            ).upper()
        except Exception:
            regime = ""
        if "OFF" in regime:
            return "Risk-Off"
        if "ON" in regime:
            return "Risk-On"
        if regime:
            return regime.replace("_", "-").title()
        return "Unknown"

    def _strength_rows(self) -> Dict[str, float]:
        """
        Real per-currency strength scores (via forex_currency_strength_engine),
        used to genuinely confirm or contradict a candidate's directional
        bias instead of always reporting "Pending".
        """
        try:
            from modules.forex.forex_currency_strength_engine import get_forex_currency_strength_engine
            engine = get_forex_currency_strength_engine()
            if hasattr(engine, "scan_currencies"):
                data = engine.scan_currencies()
            elif hasattr(engine, "command_center_payload"):
                data = engine.command_center_payload()
            elif hasattr(engine, "analyze"):
                data = engine.analyze()
            else:
                data = {}
        except Exception:
            return {}

        rows: Dict[str, float] = {}
        candidates = None
        if isinstance(data, dict):
            candidates = data.get("currency_strength") or data.get("strength") or data.get("rankings") or data.get("currencies") or data.get("scores")
        if isinstance(candidates, dict):
            for ccy, item in candidates.items():
                score = item.get("strength_score") or item.get("score") if isinstance(item, dict) else item
                if score is not None:
                    rows[str(ccy).upper()] = _safe_float(score)
        elif isinstance(candidates, list):
            for item in candidates:
                if isinstance(item, dict):
                    ccy = item.get("currency") or item.get("code") or item.get("symbol")
                    score = item.get("strength_score") or item.get("score")
                    if ccy and score is not None:
                        rows[str(ccy).upper()] = _safe_float(score)
        return rows

    def _technical_bias(self, pair: str, side: str) -> str:
        """
        Real per-pair technical signal from forex_currency_strength_engine's
        get_pair_bias() (a genuine base-vs-quote strength differential and
        signal, not something invented here). Previously this field always
        defaulted to whatever the trade's own side was (BUY row ->
        "technical_bias": "BUY"), which looked like an independent
        technical read but was actually just a mirror of the side column.
        Falls back to "Unavailable" -- not a fabricated bias -- when the
        engine can't produce a real reading for this pair.
        """
        try:
            from modules.forex.forex_currency_strength_engine import get_forex_currency_strength_engine
            row = get_forex_currency_strength_engine().get_pair_bias(pair)
        except Exception:
            return "Unavailable"
        if not isinstance(row, dict) or row.get("error"):
            return "Unavailable"
        signal = row.get("signal")
        if not signal:
            return "Unavailable"
        signal = str(signal).upper()
        if any(x in signal for x in ("BUY", "LONG", "BULL")):
            return "Bullish"
        if any(x in signal for x in ("SELL", "SHORT", "BEAR")):
            return "Bearish"
        return "Neutral"

    def _confirm_strength(self, pair: str, side: str, strength_rows: Dict[str, float]) -> str:
        """
        Compares the pair's base vs quote currency strength scores against
        the trade direction. "Confirmed" when real currency strength agrees
        with the side, "Diverging" when it disagrees, "Unavailable" when no
        real strength data could be fetched -- never the previous fixed
        "Pending" shown for every candidate regardless of data.
        """
        if not strength_rows or "/" not in pair:
            return "Unavailable"
        base, quote = pair.split("/", 1)
        base_score = strength_rows.get(base)
        quote_score = strength_rows.get(quote)
        if base_score is None or quote_score is None:
            return "Unavailable"
        base_stronger = base_score > quote_score
        if side == "BUY":
            return "Confirmed" if base_stronger else "Diverging"
        return "Confirmed" if not base_stronger else "Diverging"

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