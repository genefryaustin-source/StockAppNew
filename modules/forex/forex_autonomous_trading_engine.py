"""
modules/forex/forex_autonomous_trading_engine.py

Phase 5 — Autonomous Trading Engine.

Uses the AI Trade Assistant and institutional risk manager to generate, rank,
validate, and optionally submit paper trades.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


class ForexAutonomousTradingEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def scan(self, limit: int = 10) -> Dict[str, Any]:
        from modules.forex.forex_ai_trade_assistant import get_forex_ai_trade_assistant
        assistant = get_forex_ai_trade_assistant(db=self.db)
        candidates = assistant.generate_candidates(limit=limit)
        return {
            "status": "READY",
            "mode": "SCAN_ONLY",
            "candidate_count": len(candidates),
            "candidates": candidates,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def run_cycle(
        self,
        *,
        dry_run: bool = True,
        max_trades: int = 1,
        min_confidence: float = 80.0,
        max_risk_pct: float = 1.0,
        portfolio_id: Optional[str] = None,
        account_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        from modules.forex.forex_ai_trade_assistant import get_forex_ai_trade_assistant
        from modules.forex.forex_institutional_risk_manager import get_forex_institutional_risk_manager
        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
        from modules.forex.forex_institutional_trade_ticket import get_forex_institutional_trade_ticket

        engine = get_forex_portfolio_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=self.db,
        )
        snapshot_obj = engine.get_terminal_snapshot(
            account_id=account_id,
            portfolio_id=portfolio_id,
            refresh=True,
            persist=True,
            include_orders=True,
            include_history=True,
        )
        snapshot = snapshot_obj.to_dict() if hasattr(snapshot_obj, "to_dict") else snapshot_obj

        assistant = get_forex_ai_trade_assistant(db=self.db)
        risk = get_forex_institutional_risk_manager(db=self.db)
        ticket_service = get_forex_institutional_trade_ticket(db=self.db)

        candidates = assistant.generate_candidates(limit=10, account_snapshot=snapshot.get("account"))
        accepted = []
        rejected = []
        executions = []

        for candidate in candidates:
            if len(accepted) >= max_trades:
                break

            if _safe_float(candidate.get("confidence")) < min_confidence:
                rejected.append({"candidate": candidate, "reason": "confidence_below_threshold"})
                continue

            quote = ticket_service.quote_ticket(
                pair=candidate.get("pair"),
                side=candidate.get("side"),
                lots=candidate.get("suggested_lots") or 0.10,
                units=candidate.get("suggested_units"),
                entry_price=candidate.get("suggested_entry"),
                stop_price=candidate.get("suggested_stop"),
                target_price=candidate.get("suggested_target"),
                order_type="MARKET",
                risk_pct=max_risk_pct,
                account_snapshot=snapshot.get("account"),
            )
            validation = risk.validate_trade(snapshot, quote.to_dict())

            if not validation.get("approved"):
                rejected.append({"candidate": candidate, "ticket": quote.to_dict(), "reason": "risk_rejected", "validation": validation})
                continue

            accepted.append({"candidate": candidate, "ticket": quote.to_dict(), "validation": validation})

            if not dry_run:
                execution = ticket_service.submit_ticket(
                    pair=candidate.get("pair"),
                    side=candidate.get("side"),
                    lots=candidate.get("suggested_lots") or 0.10,
                    units=candidate.get("suggested_units"),
                    entry_price=candidate.get("suggested_entry"),
                    stop_price=candidate.get("suggested_stop"),
                    target_price=candidate.get("suggested_target"),
                    order_type="MARKET",
                    risk_pct=max_risk_pct,
                    portfolio_id=portfolio_id,
                    account_id=account_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
                executions.append(execution)

        return {
            "status": "COMPLETED",
            "dry_run": dry_run,
            "min_confidence": min_confidence,
            "max_trades": max_trades,
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "execution_count": len(executions),
            "accepted": accepted,
            "rejected": rejected,
            "executions": executions,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_AUTO = None


def get_forex_autonomous_trading_engine(db: Optional[Any] = None) -> ForexAutonomousTradingEngine:
    global _AUTO
    if _AUTO is None or (db is not None and _AUTO.db is None):
        _AUTO = ForexAutonomousTradingEngine(db=db)
    return _AUTO
