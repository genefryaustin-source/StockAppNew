"""
modules/forex/forex_institutional_risk_manager.py

Phase 5 — Institutional Risk Manager.

Consumes ForexTerminalSnapshot data and produces dealing-desk level risk
controls: leverage, margin, concentration, currency/pair exposure, drawdown,
and liquidation warnings.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


class ForexInstitutionalRiskManager:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def assess_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        account = snapshot.get("account") or {}
        margin = snapshot.get("margin") or {}
        risk = snapshot.get("risk") or {}
        currency_exposure = snapshot.get("currency_exposure") or []
        pair_exposure = snapshot.get("pair_exposure") or []
        positions = snapshot.get("positions") or []

        equity = _safe_float(account.get("equity"))
        margin_used = _safe_float(margin.get("margin_used") or account.get("margin_used"))
        margin_available = _safe_float(margin.get("margin_available") or account.get("margin_available"))
        leverage = _safe_float(account.get("leverage") or margin.get("leverage"), 50)

        gross_pair_exposure = sum(
            abs(_safe_float(row.get("gross_notional") or row.get("gross_exposure")))
            for row in pair_exposure
            if isinstance(row, dict)
        )
        net_pair_exposure = sum(
            _safe_float(row.get("net_notional") or row.get("net_exposure"))
            for row in pair_exposure
            if isinstance(row, dict)
        )

        margin_utilization = (margin_used / max(equity * leverage, 1.0)) * 100.0 if equity else 0.0
        gross_exposure_pct = (gross_pair_exposure / equity) * 100.0 if equity else 0.0
        largest_currency = self._largest_exposure(currency_exposure, "net_exposure")
        largest_pair = self._largest_exposure(pair_exposure, "net_notional")

        warnings = []
        severity = "LOW"

        if margin_utilization >= 80:
            warnings.append("Margin utilization above 80%.")
            severity = "HIGH"
        elif margin_utilization >= 60:
            warnings.append("Margin utilization above 60%.")
            severity = "MEDIUM"

        if gross_exposure_pct >= 500:
            warnings.append("Gross exposure exceeds 5x equity.")
            severity = "HIGH"
        elif gross_exposure_pct >= 300:
            warnings.append("Gross exposure exceeds 3x equity.")
            severity = max(severity, "MEDIUM", key=["LOW","MEDIUM","HIGH"].index)

        if largest_currency and abs(_safe_float(largest_currency.get("net_exposure_pct"))) > 150:
            warnings.append(f"Large currency concentration in {largest_currency.get('currency')}.")

        if largest_pair and abs(_safe_float(largest_pair.get("net_exposure_pct"))) > 150:
            warnings.append(f"Large pair concentration in {largest_pair.get('pair')}.")

        if margin_available < 0:
            warnings.append("Margin available is negative; margin call risk.")
            severity = "HIGH"

        score = 100.0
        score -= min(40.0, margin_utilization * 0.35)
        score -= min(30.0, gross_exposure_pct * 0.03)
        score -= min(20.0, len(warnings) * 5.0)
        score = max(0.0, score)

        return {
            "risk_score": round(score, 2),
            "risk_severity": severity,
            "equity": round(equity, 2),
            "margin_used": round(margin_used, 2),
            "margin_available": round(margin_available, 2),
            "margin_utilization_pct": round(margin_utilization, 4),
            "gross_exposure": round(gross_pair_exposure, 2),
            "net_exposure": round(net_pair_exposure, 2),
            "gross_exposure_pct": round(gross_exposure_pct, 4),
            "position_count": len(positions),
            "largest_currency_exposure": largest_currency,
            "largest_pair_exposure": largest_pair,
            "warnings": warnings,
            "base_risk": risk,
        }

    def validate_trade(self, snapshot: Dict[str, Any], ticket: Dict[str, Any]) -> Dict[str, Any]:
        assessment = self.assess_snapshot(snapshot)
        margin_available = _safe_float(assessment.get("margin_available"))
        required = _safe_float(ticket.get("estimated_margin_required"))
        risk_dollars = _safe_float(ticket.get("estimated_risk_dollars"))
        equity = _safe_float(assessment.get("equity"))

        errors = []
        warnings = []

        if required > margin_available:
            errors.append("Trade exceeds available margin.")
        if equity and risk_dollars / equity > 0.03:
            warnings.append("Trade risks more than 3% of equity.")
        if _safe_float(ticket.get("risk_reward")) < 1.2:
            warnings.append("Risk/reward is below 1.2.")

        return {
            "approved": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "assessment": assessment,
        }

    def _largest_exposure(self, rows: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
        candidates = [row for row in rows if isinstance(row, dict)]
        if not candidates:
            return {}
        return max(candidates, key=lambda row: abs(_safe_float(row.get(key) or row.get("net_exposure"))))


_RISK = None


def get_forex_institutional_risk_manager(db: Optional[Any] = None) -> ForexInstitutionalRiskManager:
    global _RISK
    if _RISK is None or (db is not None and _RISK.db is None):
        _RISK = ForexInstitutionalRiskManager(db=db)
    return _RISK
