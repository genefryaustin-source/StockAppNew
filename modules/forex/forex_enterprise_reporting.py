"""
modules/forex/forex_enterprise_reporting.py

Phase 14G - Enterprise reporting.

Each of the five reports (Daily Desk, Weekly FX, Risk, Execution Quality, AI
Decision) is now built from a real engine already used elsewhere in this
codebase, instead of the previous `_report(title)` stub that returned only
`{"title": ..., "summary": f"{title} generated for institutional Forex
terminal.", "status": "READY"}` regardless of any actual account/market
state.

Sources:
- Daily Desk Report      -> forex_portfolio_engine.get_terminal_snapshot()
                            (live account/portfolio/orders)
- Weekly FX Report       -> forex_quant_research_engine.research_dashboard()
                            (live cross-sectional quant scan, already
                            computed once per report_pack() call and reused)
- Risk Report            -> forex_institutional_risk_manager.assess_snapshot()
                            + the live VaR/expected-shortfall figures already
                            embedded in the terminal snapshot
- Execution Quality Report -> forex_execution_quality_engine.analyze() over
                            the account's real filled orders / execution
                            history
- AI Decision Report     -> forex_ai_investment_committee.review()

Every report honestly reports NO_DATA / ERROR when its underlying source
has nothing yet, rather than falling back to templated text.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _as_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        try:
            return value.to_dict()
        except Exception:
            return {}
    return {}


class ForexEnterpriseReporting:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def report_pack(
        self,
        snapshot: Optional[Dict[str, Any]] = None,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        from modules.forex.forex_quant_research_engine import get_forex_quant_research_engine
        from modules.forex.forex_portfolio_optimizer_v2 import get_forex_portfolio_optimizer_v2
        from modules.forex.forex_strategy_lab_v2 import get_forex_strategy_lab_v2

        quant_research = get_forex_quant_research_engine(db=self.db).research_dashboard(snapshot=snapshot)
        portfolio_optimizer = get_forex_portfolio_optimizer_v2(db=self.db).optimize(snapshot=snapshot)
        strategy_lab = get_forex_strategy_lab_v2(db=self.db).run_lab()

        terminal = self._load_terminal_snapshot(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            account_id=account_id,
        )

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "daily_desk_report": self._daily_desk_report(terminal),
            "weekly_fx_report": self._weekly_fx_report(quant_research),
            "risk_report": self._risk_report(terminal),
            "execution_quality_report": self._execution_quality_report(terminal),
            "ai_decision_report": self._ai_decision_report(snapshot),
            "quant_research": quant_research,
            "portfolio_optimizer": portfolio_optimizer,
            "strategy_lab": strategy_lab,
        }

    # ------------------------------------------------------------------
    # Shared live data load
    # ------------------------------------------------------------------

    def _load_terminal_snapshot(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
            engine = get_forex_portfolio_engine(
                db=self.db,
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
            )
            raw = engine.get_terminal_snapshot(
                portfolio_id=portfolio_id,
                account_id=account_id,
                refresh=False,
                persist=False,
                include_orders=True,
                include_history=True,
            )
            return _as_dict(raw)
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Daily Desk Report -- live account/portfolio/orders
    # ------------------------------------------------------------------

    def _daily_desk_report(self, terminal: Dict[str, Any]) -> Dict[str, Any]:
        if not terminal:
            return {
                "title": "Daily Desk Report",
                "status": "NO_DATA",
                "summary": "No live portfolio/terminal data is available yet.",
            }

        account = terminal.get("account", {}) or {}
        portfolio = terminal.get("portfolio", {}) or {}
        performance = terminal.get("performance", {}) or {}
        positions = terminal.get("positions", []) or []
        open_orders = terminal.get("open_orders", []) or []
        filled_orders = terminal.get("filled_orders", []) or []

        equity = account.get("equity", portfolio.get("total_market_value"))

        # daily_pnl may be a scalar (already-aggregated figure) or a history
        # list of {"date": ..., "pnl": ...} rows -- normalize to a scalar
        # the same way forex_trading_desk_dashboard.py does.
        daily_pnl = performance.get("daily_pnl", 0.0)
        if isinstance(daily_pnl, list):
            if daily_pnl and isinstance(daily_pnl[-1], dict):
                daily_pnl = daily_pnl[-1].get("pnl", 0.0)
            else:
                daily_pnl = 0.0

        return {
            "title": "Daily Desk Report",
            "status": "READY",
            "as_of": terminal.get("generated_at") or datetime.now(timezone.utc).isoformat(),
            "equity": equity,
            "cash_balance": account.get("cash_balance"),
            "daily_pnl": daily_pnl,
            "unrealized_pnl": portfolio.get("total_unrealized_pnl"),
            "realized_pnl": portfolio.get("total_realized_pnl"),
            "open_positions": len(positions),
            "open_orders": len(open_orders),
            "filled_orders": len(filled_orders),
            "summary": (
                f"{len(positions)} open position(s), {len(open_orders)} open order(s), "
                f"{len(filled_orders)} filled order(s); daily P&L "
                f"{daily_pnl if daily_pnl is not None else 'n/a'}."
            ),
        }

    # ------------------------------------------------------------------
    # Weekly FX Report -- live cross-sectional quant research
    # ------------------------------------------------------------------

    def _weekly_fx_report(self, quant_research: Dict[str, Any]) -> Dict[str, Any]:
        snap = quant_research.get("snapshot") if isinstance(quant_research, dict) else None
        data_status = quant_research.get("data_status") if isinstance(quant_research, dict) else None

        if not snap or data_status != "LIVE_INPUT_ANALYZED":
            return {
                "title": "Weekly FX Report",
                "status": "NO_DATA",
                "summary": "No live quant research data was available for this period.",
            }

        return {
            "title": "Weekly FX Report",
            "status": "READY",
            "universe_size": snap.get("universe_size"),
            "analyzed_pairs": snap.get("analyzed_pairs"),
            "bullish_count": snap.get("bullish_count"),
            "bearish_count": snap.get("bearish_count"),
            "neutral_count": snap.get("neutral_count"),
            "avg_quant_score": snap.get("avg_quant_score"),
            "strongest_pair": snap.get("strongest_pair"),
            "weakest_pair": snap.get("weakest_pair"),
            "risk_regime": snap.get("risk_regime"),
            "summary": snap.get("research_summary"),
        }

    # ------------------------------------------------------------------
    # Risk Report -- live risk assessment + embedded VaR/ES
    # ------------------------------------------------------------------

    def _risk_report(self, terminal: Dict[str, Any]) -> Dict[str, Any]:
        if not terminal:
            return {
                "title": "Risk Report",
                "status": "NO_DATA",
                "summary": "No live portfolio/terminal data is available yet.",
            }

        try:
            from modules.forex.forex_institutional_risk_manager import get_forex_institutional_risk_manager
            assessment = get_forex_institutional_risk_manager(db=self.db).assess_snapshot(terminal)
        except Exception as exc:
            return {"title": "Risk Report", "status": "ERROR", "error": str(exc)}

        portfolio = terminal.get("portfolio", {}) or {}
        institutional_risk = portfolio.get("institutional_risk", {}) or {}
        parametric_var = institutional_risk.get("parametric_var", {}) or {}
        expected_shortfall = institutional_risk.get("expected_shortfall", {}) or {}

        warnings = assessment.get("warnings") or []
        summary = (
            warnings[0]
            if warnings
            else f"Risk score {assessment.get('risk_score')} ({assessment.get('risk_severity')}); no active warnings."
        )

        return {
            "title": "Risk Report",
            "status": "READY",
            "risk_score": assessment.get("risk_score"),
            "risk_severity": assessment.get("risk_severity"),
            "margin_utilization_pct": assessment.get("margin_utilization_pct"),
            "gross_exposure_pct": assessment.get("gross_exposure_pct"),
            "daily_var": parametric_var.get("daily_var"),
            "expected_shortfall": expected_shortfall.get("expected_shortfall"),
            "largest_currency_exposure": assessment.get("largest_currency_exposure"),
            "largest_pair_exposure": assessment.get("largest_pair_exposure"),
            "warnings": warnings,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # Execution Quality Report -- live TCA over real fills
    # ------------------------------------------------------------------

    def _execution_quality_report(self, terminal: Dict[str, Any]) -> Dict[str, Any]:
        filled_orders = (terminal or {}).get("filled_orders", []) or []
        execution_history = (terminal or {}).get("execution_history", []) or []

        if not filled_orders and not execution_history:
            return {
                "title": "Execution Quality Report",
                "status": "NO_DATA",
                "summary": "No executions have been recorded yet.",
            }

        try:
            from modules.forex.forex_execution_quality_engine import get_forex_execution_quality_engine
            result = get_forex_execution_quality_engine().analyze(
                filled_orders=filled_orders,
                execution_history=execution_history,
            )
        except Exception as exc:
            return {"title": "Execution Quality Report", "status": "ERROR", "error": str(exc)}

        result = dict(result) if isinstance(result, dict) else {}
        result["title"] = "Execution Quality Report"
        result.setdefault("status", "READY")
        result.setdefault(
            "summary",
            f"{result.get('execution_count', 0)} execution(s) analyzed, grade "
            f"{result.get('execution_grade', 'N/A')}.",
        )
        return result

    # ------------------------------------------------------------------
    # AI Decision Report -- live investment-committee decision
    # ------------------------------------------------------------------

    def _ai_decision_report(self, snapshot: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            from modules.forex.forex_ai_investment_committee import get_forex_ai_investment_committee
            committee = get_forex_ai_investment_committee(db=self.db).review(snapshot=snapshot)
        except Exception as exc:
            return {"title": "AI Decision Report", "status": "ERROR", "error": str(exc)}

        approved = committee.get("approved_ideas", []) or []
        return {
            "title": "AI Decision Report",
            "status": "READY",
            "decision": committee.get("decision"),
            "approved_ideas": approved,
            "committee_notes": committee.get("committee_notes", []),
            "summary": (
                f"Committee decision: {committee.get('decision')}. "
                f"{len(approved)} idea(s) approved for paper trading."
            ),
        }


_REPORTS = None


def get_forex_enterprise_reporting(db: Optional[Any] = None) -> ForexEnterpriseReporting:
    global _REPORTS
    if _REPORTS is None or (db is not None and _REPORTS.db is None):
        _REPORTS = ForexEnterpriseReporting(db=db)
    return _REPORTS