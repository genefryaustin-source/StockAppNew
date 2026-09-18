"""
api/services/portfolio_full_export_api_service.py

Backs GET /api/v1/tenant/portfolio/full -- one call that returns
everything available for a tenant (and, for an admin caller, every user
in that tenant) across every asset class: stocks, options, crypto,
tokenized real-world assets, and forex.

Distinct from api.services.executive_mobile_dashboard_api_service, which
returns tenant-wide *counts and rollups* for a UI dashboard. This
endpoint is a data export: full raw positions, full snapshot/equity
history, and full order history, not a summarized view.

Reuses rather than reimplements:
  - modules.risk_layer.positions.get_positions_df() -- already unifies
    equities/options/crypto/tokenized-RWA (via PortfolioPosition) with
    forex (via its own table) into one cross-asset positions frame, with
    every currency-conversion and duplicate-snapshot fix already applied.
  - modules.risk_layer.positions.get_returns_df() -- the same
    dedup-and-align equity/drawdown history.
  - api.services.options_orders_api_service.OptionsOrdersAPIService --
    options order history (options orders live in their own table, not
    TradeOrder).
  - modules.forex.forex_portfolio_engine.get_forex_portfolio_engine --
    forex order history (forex orders also live in their own table).
  - TradeOrder directly for stocks/crypto/tokenized-RWA order history --
    per orders_api_service.py and crypto_orders_api_service.py, every
    broker (paper, Alpaca, Tradier, IBKR, ccxt, Ondo, Securitize, the
    custom tokenized-asset adapter) submits through the same canonical
    stock trading service and lands in the same TradeOrder table,
    distinguished only by symbol shape (a "/" marks a crypto pair).

Every section is independently wrapped -- one section failing reports
{"available": False, "reason": ...} in its place rather than failing the
whole response, matching every other composite service in this API.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from models.trading import Portfolio, PortfolioSnapshot, TradeOrder
from modules.db.models import Tenant, User

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class PortfolioFullExportAPIService:
    """
    Composite export service: tenant info, tenant users, every portfolio,
    unified cross-asset positions, equity/drawdown history, full snapshot
    history, and order history (stocks/crypto/tokenized-RWA + options +
    forex) for a tenant.
    """

    def __init__(self, db):
        self.db = db

    def get_full_export(
        self,
        *,
        tenant_id: str,
        include_all_users: bool = True,
        snapshot_limit_per_portfolio: int = 500,
        order_limit_per_portfolio: int = 500,
    ) -> dict[str, Any]:
        _safe_rollback(self.db)

        result: dict[str, Any] = {
            "tenant": self._section("tenant", lambda: self._tenant_info(tenant_id)),
            "users": self._section("users", lambda: self._tenant_users(tenant_id))
                     if include_all_users else {"available": False, "reason": "include_all_users=false"},
        }

        portfolios = (
            self.db.query(Portfolio)
            .filter(Portfolio.tenant_id == tenant_id)
            .order_by(Portfolio.created_at.asc())
            .all()
        )
        portfolio_ids = [p.id for p in portfolios]

        result["portfolios"] = self._section("portfolios", lambda: [
            {
                "id": p.id, "name": p.name, "description": getattr(p, "description", None),
                "base_currency": p.base_currency, "starting_cash": p.starting_cash,
                "is_active": p.is_active, "created_at": _iso(p.created_at),
            }
            for p in portfolios
        ])

        result["positions"] = self._section("positions", lambda: self._unified_positions(tenant_id))
        result["equity_curve"] = self._section("equity_curve", lambda: self._equity_curve(tenant_id))
        result["snapshot_history"] = self._section(
            "snapshot_history",
            lambda: self._snapshot_history(portfolio_ids, snapshot_limit_per_portfolio),
        )
        result["orders"] = {
            "stocks_crypto_tokenized_rwa": self._section(
                "orders.stocks_crypto_tokenized_rwa",
                lambda: self._trade_orders(portfolio_ids, order_limit_per_portfolio),
            ),
            "options": self._section("orders.options", lambda: self._options_orders(tenant_id, order_limit_per_portfolio)),
            "forex": self._section("orders.forex", lambda: self._forex_orders(tenant_id, order_limit_per_portfolio)),
        }

        return result

    # ------------------------------------------------------------
    # Section helpers -- each independently wrapped
    # ------------------------------------------------------------

    def _section(self, name: str, fn):
        try:
            return fn()
        except Exception as e:
            logger.exception("Full export section '%s' failed for this request.", name)
            _safe_rollback(self.db)
            return {"available": False, "reason": f"{name} unavailable: {e}"}

    def _tenant_info(self, tenant_id: str) -> dict:
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return {"id": tenant_id, "found": False}
        return {
            "id": tenant.id, "name": getattr(tenant, "name", None),
            "is_active": getattr(tenant, "is_active", None),
            "created_at": _iso(getattr(tenant, "created_at", None)),
            "found": True,
        }

    def _tenant_users(self, tenant_id: str) -> list[dict]:
        users = self.db.query(User).filter(User.tenant_id == tenant_id).all()
        return [
            {"id": u.id, "email": u.email, "role": u.role, "is_active": u.is_active,
             "created_at": _iso(u.created_at)}
            for u in users
        ]

    def _unified_positions(self, tenant_id: str) -> dict:
        from modules.risk_layer.positions import get_positions_df
        df = get_positions_df(self.db, tenant_id=tenant_id)
        positions = df.to_dict(orient="records") if df is not None and not df.empty else []
        by_class: dict[str, list] = {}
        for p in positions:
            by_class.setdefault(p.get("Asset Class", "unknown"), []).append(p)
        return {"count": len(positions), "positions": positions, "by_asset_class": by_class}

    def _equity_curve(self, tenant_id: str) -> list[dict]:
        from modules.risk_layer.positions import get_returns_df
        df = get_returns_df(self.db, tenant_id=tenant_id)
        if df is None or df.empty:
            return []
        out = df.copy()
        out["as_of"] = out["as_of"].astype(str)
        return out.to_dict(orient="records")

    def _snapshot_history(self, portfolio_ids: list[str], limit_per_portfolio: int) -> list[dict]:
        if not portfolio_ids:
            return []
        rows = (
            self.db.query(PortfolioSnapshot)
            .filter(PortfolioSnapshot.portfolio_id.in_(portfolio_ids))
            .order_by(PortfolioSnapshot.portfolio_id.asc(), PortfolioSnapshot.as_of.asc())
            .all()
        )
        by_portfolio: dict[str, list] = {}
        for r in rows:
            by_portfolio.setdefault(r.portfolio_id, []).append(r)
        out = []
        for portfolio_id, snaps in by_portfolio.items():
            for s in snaps[-limit_per_portfolio:]:
                out.append({
                    "portfolio_id": portfolio_id, "as_of": _iso(s.as_of),
                    "cash": s.cash, "market_value": s.market_value, "equity": s.equity,
                    "realized_pnl": s.realized_pnl, "unrealized_pnl": s.unrealized_pnl, "net_pnl": s.net_pnl,
                })
        return out

    def _trade_orders(self, portfolio_ids: list[str], limit_per_portfolio: int) -> list[dict]:
        if not portfolio_ids:
            return []
        rows = (
            self.db.query(TradeOrder)
            .filter(TradeOrder.portfolio_id.in_(portfolio_ids))
            .order_by(TradeOrder.portfolio_id.asc(), TradeOrder.created_at.desc())
            .all()
        )
        by_portfolio: dict[str, list] = {}
        for r in rows:
            by_portfolio.setdefault(r.portfolio_id, []).append(r)
        out = []
        for portfolio_id, orders in by_portfolio.items():
            for o in orders[:limit_per_portfolio]:
                out.append({
                    "portfolio_id": portfolio_id, "order_id": o.id, "user_id": o.user_id,
                    "broker": o.broker, "symbol": o.symbol, "side": o.side,
                    "order_type": o.order_type, "tif": o.tif, "qty": o.qty,
                    "limit_price": o.limit_price, "stop_price": o.stop_price, "status": o.status,
                    "avg_fill_price": o.avg_fill_price, "filled_qty": o.filled_qty,
                    "created_at": _iso(o.created_at), "filled_at": _iso(o.filled_at),
                    "canceled_at": _iso(o.canceled_at),
                    "asset_class": "crypto" if "/" in (o.symbol or "") else "equity_or_rwa",
                })
        return out

    def _options_orders(self, tenant_id: str, limit: int) -> dict:
        from api.services.options_orders_api_service import OptionsOrdersAPIService
        return OptionsOrdersAPIService(self.db).get_order_history(tenant_id=tenant_id, limit=limit)

    def _forex_orders(self, tenant_id: str, limit: int) -> list[dict]:
        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
        engine = get_forex_portfolio_engine(tenant_id=tenant_id, db=self.db)
        return engine.load_execution_history(limit=limit)


def _iso(value):
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else value
