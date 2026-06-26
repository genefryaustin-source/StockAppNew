"""
modules/forex/forex_ai_command_center.py

Institutional AI command center for FX.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexAICommandCenter:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def briefing(self, **kwargs) -> Dict[str, Any]:
        from modules.forex.forex_ai_trade_assistant import get_forex_ai_trade_assistant

        assistant = get_forex_ai_trade_assistant(db=self.db)
        candidates = assistant.generate_candidates(limit=5)
        top = candidates[0] if candidates else {}

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "headline": self._headline(top),
            "top_candidate": top,
            "candidates": candidates,
            "briefing": [
                "Macro, strength, alpha, and institutional-flow inputs have been consolidated.",
                f"Top setup: {top.get('pair', 'N/A')} {top.get('side', 'WATCH')} at {top.get('confidence', 0)}% confidence.",
                "Use paper execution until live broker routing has been validated.",
            ],
        }

    def _headline(self, candidate: Dict[str, Any]) -> str:
        if not candidate:
            return "No active AI trade candidate."
        return f"{candidate.get('pair')} {candidate.get('side')} ranked highest by AI command center."


_CENTER = None


def get_forex_ai_command_center(db: Optional[Any] = None) -> ForexAICommandCenter:
    global _CENTER
    if _CENTER is None or (db is not None and _CENTER.db is None):
        _CENTER = ForexAICommandCenter(db=db)
    return _CENTER
