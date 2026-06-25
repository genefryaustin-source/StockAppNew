from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from modules.forex.forex_portfolio_engine import ForexPortfolioEngine, get_forex_portfolio_engine
    from modules.forex.forex_trading_engine import ForexTradingEngine, get_forex_trading_engine
except Exception:
    from forex_portfolio_engine import ForexPortfolioEngine, get_forex_portfolio_engine
    from forex_trading_engine import ForexTradingEngine, get_forex_trading_engine


@dataclass
class ForexPerformanceSummary:
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    account_id: Optional[str]
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float
    total_realized_pnl: float
    total_unrealized_pnl: float
    avg_trade_pnl: float
    best_trade: float
    worst_trade: float
    profit_factor: float
    equity: float
    return_pct: float
    asof: datetime
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["asof"] = self.asof.isoformat()
        return data


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except Exception:
        return default


def _json(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return {"value": str(value)}


class ForexPerformanceEngine:
    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        db: Any = None,
        forex_portfolio_engine: Optional[ForexPortfolioEngine] = None,
        forex_trading_engine: Optional[ForexTradingEngine] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id
        self.db = db
        self.forex_portfolio_engine = forex_portfolio_engine or get_forex_portfolio_engine(
            tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id, db=db
        )
        self.forex_trading_engine = forex_trading_engine or get_forex_trading_engine(
            tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id, db=db,
            forex_portfolio_engine=self.forex_portfolio_engine
        )

    def ensure_tables(self) -> None:
        if self.db is None:
            return
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS forex_performance_snapshots (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                account_id VARCHAR(80),
                trade_count INTEGER,
                win_count INTEGER,
                loss_count INTEGER,
                win_rate DOUBLE PRECISION,
                total_realized_pnl DOUBLE PRECISION,
                total_unrealized_pnl DOUBLE PRECISION,
                avg_trade_pnl DOUBLE PRECISION,
                best_trade DOUBLE PRECISION,
                worst_trade DOUBLE PRECISION,
                profit_factor DOUBLE PRECISION,
                equity DOUBLE PRECISION,
                return_pct DOUBLE PRECISION,
                payload JSONB,
                asof TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        if hasattr(self.db, "commit"):
            self.db.commit()

    def calculate_performance(self, *, account_id: Optional[str] = None, persist: bool = True) -> ForexPerformanceSummary:
        trades = self.forex_trading_engine.list_trades(account_id=account_id, status="ALL", limit=1000)
        pnl_values = [_safe_float(getattr(t, "realized_pnl", 0.0)) for t in trades]
        wins = [p for p in pnl_values if p > 0]
        losses = [p for p in pnl_values if p < 0]

        account = None
        if account_id:
            account = self.forex_portfolio_engine.get_account(account_id=account_id)

        snapshot = None
        if account_id:
            snapshot = self.forex_portfolio_engine.get_snapshot(account_id=account_id, persist=False, refresh=True)

        total_realized = sum(pnl_values)
        total_unrealized = _safe_float(snapshot.total_unrealized_pnl if snapshot else 0.0)
        equity = _safe_float(snapshot.equity if snapshot else (account.equity if account else 0.0))
        starting_cash = max(_safe_float(account.cash_balance if account else equity), 1.0)
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        summary = ForexPerformanceSummary(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            account_id=account_id,
            trade_count=len(trades),
            win_count=len(wins),
            loss_count=len(losses),
            win_rate=round((len(wins) / len(trades)) * 100.0, 2) if trades else 0.0,
            total_realized_pnl=round(total_realized, 2),
            total_unrealized_pnl=round(total_unrealized, 2),
            avg_trade_pnl=round(total_realized / len(trades), 2) if trades else 0.0,
            best_trade=round(max(pnl_values), 2) if pnl_values else 0.0,
            worst_trade=round(min(pnl_values), 2) if pnl_values else 0.0,
            profit_factor=round(gross_profit / gross_loss, 2) if gross_loss else (round(gross_profit, 2) if gross_profit else 0.0),
            equity=round(equity, 2),
            return_pct=round(((equity - starting_cash) / starting_cash) * 100.0, 2) if starting_cash else 0.0,
            asof=_utc_now(),
            raw={"trades": [t.to_dict() for t in trades[:100]]},
        )
        if persist:
            self.save_snapshot(summary)
        return summary

    def save_snapshot(self, summary: ForexPerformanceSummary) -> None:
        if self.db is None:
            return
        self.ensure_tables()
        self.db.execute("""
            INSERT INTO forex_performance_snapshots (
                tenant_id, user_id, portfolio_id, account_id, trade_count, win_count, loss_count,
                win_rate, total_realized_pnl, total_unrealized_pnl, avg_trade_pnl, best_trade,
                worst_trade, profit_factor, equity, return_pct, payload, asof
            )
            VALUES (
                :tenant_id, :user_id, :portfolio_id, :account_id, :trade_count, :win_count, :loss_count,
                :win_rate, :total_realized_pnl, :total_unrealized_pnl, :avg_trade_pnl, :best_trade,
                :worst_trade, :profit_factor, :equity, :return_pct, :payload, :asof
            )
        """, {**summary.to_dict(), "payload": _json(summary.to_dict()), "asof": _naive(summary.asof)})
        if hasattr(self.db, "commit"):
            self.db.commit()

    def load_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        self.ensure_tables()
        rows = self.db.execute("""
            SELECT * FROM forex_performance_snapshots
            WHERE tenant_id = :tenant_id
            ORDER BY asof DESC
            LIMIT :limit
        """, {"tenant_id": self.tenant_id, "limit": int(limit)}).fetchall()
        return [
            {
                "account_id": getattr(row, "account_id", None),
                "trade_count": getattr(row, "trade_count", None),
                "win_rate": getattr(row, "win_rate", None),
                "total_realized_pnl": getattr(row, "total_realized_pnl", None),
                "total_unrealized_pnl": getattr(row, "total_unrealized_pnl", None),
                "profit_factor": getattr(row, "profit_factor", None),
                "equity": getattr(row, "equity", None),
                "return_pct": getattr(row, "return_pct", None),
                "asof": str(getattr(row, "asof", "")),
            }
            for row in rows
        ]


def get_forex_performance_engine(**kwargs: Any) -> ForexPerformanceEngine:
    return ForexPerformanceEngine(**kwargs)
