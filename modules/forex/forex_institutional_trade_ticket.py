"""
modules/forex/forex_institutional_trade_ticket.py

Phase 5 — Institutional Trade Ticket.

A production-oriented paper-trading ticket that sits on top of the Phase 4
validation/execution layer. It calculates lot/unit sizing, margin estimate,
pip value, stop distance, risk dollars, and risk/reward before routing orders.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Tuple


MAJOR_PAIRS = {
    "EUR/USD": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "GBP/USD": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "AUD/USD": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "NZD/USD": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "USD/CAD": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "USD/CHF": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "USD/JPY": {"pip_size": 0.01, "pip_value_per_standard_lot": 9.0},
    "EUR/JPY": {"pip_size": 0.01, "pip_value_per_standard_lot": 9.0},
    "GBP/JPY": {"pip_size": 0.01, "pip_value_per_standard_lot": 9.0},
    "CHF/JPY": {"pip_size": 0.01, "pip_value_per_standard_lot": 9.0},
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            cleaned = value.replace("$", "").replace(",", "").replace("%", "").strip()
            if cleaned in {"", "-", "—"}:
                return default
            return float(cleaned)
        return float(value)
    except Exception:
        return default


def normalize_pair(pair: Any) -> str:
    value = str(pair or "EUR/USD").replace("-", "/").replace("_", "/").upper().strip()
    if "/" not in value and len(value) == 6:
        value = value[:3] + "/" + value[3:]
    return value


def normalize_side(side: Any) -> str:
    value = str(side or "BUY").upper().strip()
    if value in {"LONG", "BUY", "B"}:
        return "BUY"
    if value in {"SHORT", "SELL", "S"}:
        return "SELL"
    return "BUY"


@dataclass
class ForexTradeTicketQuote:
    pair: str
    side: str
    order_type: str
    lots: float
    units: float
    entry_price: float
    stop_price: Optional[float]
    target_price: Optional[float]
    pip_size: float
    pip_value: float
    stop_distance_pips: float
    target_distance_pips: float
    estimated_risk_dollars: float
    estimated_reward_dollars: float
    risk_reward: float
    notional_value: float
    estimated_margin_required: float
    margin_available: float
    margin_ok: bool
    risk_pct_of_equity: float
    warnings: list

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ForexInstitutionalTradeTicket:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def quote_ticket(
        self,
        *,
        pair: str,
        side: str,
        lots: Optional[float] = None,
        units: Optional[float] = None,
        order_type: str = "MARKET",
        entry_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        target_price: Optional[float] = None,
        risk_pct: Optional[float] = None,
        account_snapshot: Optional[Dict[str, Any]] = None,
        leverage: Optional[float] = None,
    ) -> ForexTradeTicketQuote:
        pair_norm = normalize_pair(pair)
        side_norm = normalize_side(side)
        order_type_norm = str(order_type or "MARKET").upper()

        pair_meta = MAJOR_PAIRS.get(pair_norm, {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0})
        pip_size = _safe_float(pair_meta["pip_size"], 0.0001)

        account_snapshot = account_snapshot or self._default_account_snapshot()
        equity = _safe_float(account_snapshot.get("equity") or account_snapshot.get("cash_balance"), 0)
        margin_available = _safe_float(account_snapshot.get("margin_available") or account_snapshot.get("equity"), equity)
        lev = _safe_float(leverage or account_snapshot.get("leverage"), 50.0)

        resolved_lots = _safe_float(lots)
        resolved_units = _safe_float(units)

        if resolved_units > 0 and resolved_lots <= 0:
            resolved_lots = resolved_units / 100000.0
        elif resolved_lots > 0 and resolved_units <= 0:
            resolved_units = resolved_lots * 100000.0
        elif resolved_lots <= 0 and resolved_units <= 0:
            resolved_lots = 1.0
            resolved_units = 100000.0

        price = _safe_float(entry_price, self._last_price(pair_norm))
        stop = _safe_float(stop_price) if stop_price not in (None, "") else None
        target = _safe_float(target_price) if target_price not in (None, "") else None

        pip_value = _safe_float(pair_meta["pip_value_per_standard_lot"], 10.0) * resolved_lots

        stop_pips = 0.0
        target_pips = 0.0

        if stop:
            stop_pips = abs(price - stop) / pip_size
        if target:
            target_pips = abs(target - price) / pip_size

        risk_dollars = stop_pips * pip_value
        reward_dollars = target_pips * pip_value
        rr = reward_dollars / risk_dollars if risk_dollars > 0 else 0.0

        notional = resolved_units * price
        margin_required = abs(notional) / max(lev, 1.0)

        warnings = []
        if stop is None:
            warnings.append("No stop loss provided.")
        if target is None:
            warnings.append("No take profit provided.")
        if margin_required > margin_available:
            warnings.append("Estimated margin exceeds margin available.")
        if risk_pct and equity and risk_dollars > equity * (_safe_float(risk_pct) / 100.0):
            warnings.append("Estimated risk exceeds selected account risk percentage.")

        return ForexTradeTicketQuote(
            pair=pair_norm,
            side=side_norm,
            order_type=order_type_norm,
            lots=round(resolved_lots, 4),
            units=round(resolved_units, 2),
            entry_price=price,
            stop_price=stop,
            target_price=target,
            pip_size=pip_size,
            pip_value=round(pip_value, 4),
            stop_distance_pips=round(stop_pips, 2),
            target_distance_pips=round(target_pips, 2),
            estimated_risk_dollars=round(risk_dollars, 2),
            estimated_reward_dollars=round(reward_dollars, 2),
            risk_reward=round(rr, 4),
            notional_value=round(notional, 2),
            estimated_margin_required=round(margin_required, 2),
            margin_available=round(margin_available, 2),
            margin_ok=margin_required <= margin_available,
            risk_pct_of_equity=round((risk_dollars / equity) * 100.0, 4) if equity else 0.0,
            warnings=warnings,
        )

    def submit_ticket(self, **kwargs) -> Dict[str, Any]:
        quote = self.quote_ticket(**kwargs)
        if not quote.margin_ok:
            return {
                "status": "REJECTED",
                "message": "Insufficient margin for ticket.",
                "ticket": quote.to_dict(),
            }

        from modules.forex.forex_terminal_execution_service import get_forex_terminal_execution_service

        result = get_forex_terminal_execution_service(db=self.db).submit_order(
            pair=quote.pair,
            side=quote.side,
            lots=quote.lots,
            units=quote.units,
            order_type=quote.order_type,
            limit_price=quote.entry_price if quote.order_type == "LIMIT" else None,
            stop_price=quote.stop_price,
            target_price=quote.target_price,
            broker="paper",
            risk_pct=kwargs.get("risk_pct"),
            portfolio_id=kwargs.get("portfolio_id"),
            account_id=kwargs.get("account_id"),
            tenant_id=kwargs.get("tenant_id"),
            user_id=kwargs.get("user_id"),
        )
        result["ticket"] = quote.to_dict()
        return result

    def _default_account_snapshot(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
            engine = get_forex_portfolio_engine(db=self.db)
            account = engine.get_or_create_account()
            return account.to_dict() if hasattr(account, "to_dict") else {}
        except Exception:
            return {"equity": 100000.0, "margin_available": 100000.0, "leverage": 50.0}

    def _last_price(self, pair: str) -> float:
        defaults = {
            "EUR/USD": 1.0718,
            "GBP/USD": 1.2645,
            "AUD/USD": 0.6641,
            "NZD/USD": 0.6120,
            "USD/JPY": 158.42,
            "USD/CHF": 0.8912,
            "USD/CAD": 1.3710,
            "EUR/JPY": 169.72,
            "EUR/GBP": 0.8475,
            "GBP/JPY": 200.28,
            "CHF/JPY": 177.75,
            "AUD/JPY": 105.18,
        }
        return defaults.get(pair, 1.0)


_TICKET = None


def get_forex_institutional_trade_ticket(db: Optional[Any] = None) -> ForexInstitutionalTradeTicket:
    global _TICKET
    if _TICKET is None or (db is not None and _TICKET.db is None):
        _TICKET = ForexInstitutionalTradeTicket(db=db)
    return _TICKET
