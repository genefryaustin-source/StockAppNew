"""
modules/forex/forex_portfolio_manager.py

Forex Portfolio Manager

Connects Forex analytics to portfolio-style position tracking, mark-to-market,
risk exposure, and paper-trading-ready order/position summaries.

Position data (load_positions and everything downstream of it --
mark_positions, portfolio_summary, currency_exposure, risk_metrics) is
sourced from modules.forex.forex_portfolio_engine.ForexPortfolioEngine,
the same canonical engine ForexTerminalExecutionService writes to on
every real fill and the external REST API reads from. This used to run
its own separate raw SQL against a forex_positions schema this class's
own (permanently-disabled) ensure_tables() never actually created --
which meant it was reading ForexPortfolioEngine's table by accident,
then a downstream method read the result assuming a column name
("avg_price") that column never had, so avg_price/unrealized_pnl/
market_value silently computed to 0.0 for every real position on every
dashboard using this class. Fixed by sourcing directly from the engine
with the field names it actually has.

This module is intentionally database-tolerant:
- If a SQLAlchemy db/session is supplied, it can read/write Forex positions.
- If no db is supplied, it operates from in-memory/demo inputs.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from modules.forex.forex_portfolio_cache import (
    get_forex_portfolio_cache,
)
try:
    from sqlalchemy import text
except Exception:
    text = None

try:
    from modules.forex.forex_price_service import get_forex_price_service
except Exception:
    get_forex_price_service = None

try:
    from modules.forex.forex_alpha_model import get_forex_alpha_model
except Exception:
    get_forex_alpha_model = None
from modules.forex.forex_portfolio_crud_engine import (
    get_forex_portfolio_crud_engine,
)

DEFAULT_ACCOUNT_CURRENCY = "USD"
DEFAULT_STARTING_CASH = 100000.0

logger = logging.getLogger(__name__)
_INITIALIZED = False

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return default
        return out
    except Exception:
        return default


def normalize_pair(pair: str) -> str:
    text = str(pair or "").upper().replace("-", "/").replace("_", "/").replace(" ", "")
    if "/" in text:
        left, right = text.split("/", 1)
        return f"{left[:3]}/{right[:3]}"
    if len(text) >= 6:
        return f"{text[:3]}/{text[3:6]}"
    return text


def split_pair(pair: str) -> Tuple[str, str]:
    pair = normalize_pair(pair)
    if "/" in pair:
        left, right = pair.split("/", 1)
        return left[:3], right[:3]
    if len(pair) >= 6:
        return pair[:3], pair[3:6]
    return pair[:3], ""


@dataclass
class ForexPosition:
    pair: str
    side: str
    units: float
    avg_price: float
    current_price: float
    notional: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    base_currency: str
    quote_currency: str
    provider: Optional[str]
    opened_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ForexPortfolioManager:

    def __init__(
            self,
            db=None,
            tenant_id=None,
            user_id=None,
            portfolio_id=None,
            account_currency: str = DEFAULT_ACCOUNT_CURRENCY,
            starting_cash: float = DEFAULT_STARTING_CASH,
    ):
        self.db = db
        # forex_portfolio_crud_engine.py filters every query with raw SQL
        # like "WHERE tenant_id=:tenant AND user_id=:user". In SQL, `col =
        # NULL` never matches (even a NULL-valued column), so tenant_id=None
        # / user_id=None silently returned zero rows from list_portfolios()
        # forever, even immediately after create_portfolio() had just
        # inserted a row with those same NULL values - the portfolio
        # dashboard's "no active portfolio" empty state was permanent for
        # any caller that didn't explicitly pass a tenant_id/user_id, which
        # is the common case (most dashboards call
        # get_forex_portfolio_manager(db=db) with neither). Normalizing to
        # a stable default string here, once, means every query this
        # manager issues is internally consistent.
        self.tenant_id = str(tenant_id) if tenant_id is not None else "default"
        self.user_id = str(user_id) if user_id is not None else "default"
        self.portfolio_id = portfolio_id

        self.portfolio_engine = get_forex_portfolio_crud_engine(
            db=db,
        )
        self.account_currency = str(account_currency or DEFAULT_ACCOUNT_CURRENCY).upper()
        self.starting_cash = float(starting_cash or DEFAULT_STARTING_CASH)
        self.price_service = get_forex_price_service() if get_forex_price_service else None
        self.alpha_model = get_forex_alpha_model() if get_forex_alpha_model else None
        self._tables_ready = True
        self.cache = get_forex_portfolio_cache()
    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def ensure_tables(self) -> None:

        global _INITIALIZED

        if _INITIALIZED:
            return

        if self._tables_ready:
            return

        if self.db is None or text is None:
            return

        try:
            self.db.execute(text("""
                CREATE TABLE IF NOT EXISTS forex_positions (
                    id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(100),
                    portfolio_id VARCHAR(100),
                    user_id VARCHAR(100),
                    pair VARCHAR(20) NOT NULL,
                    side VARCHAR(20) NOT NULL,
                    units DOUBLE PRECISION NOT NULL,
                    avg_price DOUBLE PRECISION NOT NULL,
                    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(50) DEFAULT 'OPEN'
                )
            """))

            self.db.execute(text("""
                CREATE TABLE IF NOT EXISTS forex_orders (
                    id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(100),
                    portfolio_id VARCHAR(100),
                    user_id VARCHAR(100),
                    pair VARCHAR(20) NOT NULL,
                    side VARCHAR(20) NOT NULL,
                    order_type VARCHAR(30) DEFAULT 'market',
                    units DOUBLE PRECISION NOT NULL,
                    requested_price DOUBLE PRECISION,
                    filled_price DOUBLE PRECISION,
                    status VARCHAR(50) DEFAULT 'paper_filled',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    filled_at TIMESTAMP
                )
            """))

            self.db.commit()

            self._tables_ready = True
            _INITIALIZED = True


        except Exception as exc:
            print("=" * 80)
            print("PortfolioManager.ensure_tables FAILED")
            print(exc)

            import traceback
            traceback.print_exc()

            if self.db is not None:
                self.db.rollback()

            raise

    def load_positions(
            self,
            portfolio_id: Optional[str] = None,
            user_id: Optional[str] = None,
            tenant_id: Optional[str] = None,
            force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Open forex positions, sourced from ForexPortfolioEngine --
        the same canonical engine ForexTerminalExecutionService writes
        to on every real fill, and what the external REST API
        (GET /api/v1/forex/positions) reads. force_refresh is accepted
        for backward compatibility with existing callers but has no
        effect: this always reads live, there's no cache to bypass
        anymore (see class docstring).

        Previously this ran its own raw "SELECT * FROM forex_positions"
        against a schema this class's own (dead -- see ensure_tables)
        table definition didn't actually match, then a downstream
        method (mark_positions) read the result assuming a column name
        ("avg_price") that was never actually present -- avg_price,
        unrealized_pnl, and market_value silently computed as 0.0 for
        every real position on every dashboard that called this.
        """
        if self.db is None:
            return []

        try:
            from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine

            engine = get_forex_portfolio_engine(
                tenant_id=tenant_id or self.tenant_id,
                user_id=user_id or self.user_id,
                portfolio_id=portfolio_id or self.portfolio_id,
                db=self.db,
            )

            positions = engine.list_positions(status="OPEN")

        except Exception:
            logger.exception("Failed to load forex positions.")
            try:
                self.db.rollback()
            except Exception:
                pass
            return []

        return [
            {
                "id": p.id,
                "tenant_id": p.tenant_id,
                "user_id": p.user_id,
                "portfolio_id": p.portfolio_id,
                "account_id": p.account_id,
                "pair": p.pair,
                "side": p.side,
                "units": p.units,
                # "avg_price" (not avg_entry_price) is deliberate --
                # every downstream method in this class (mark_positions,
                # portfolio_summary, currency_exposure, risk_metrics)
                # was written against this key name; renaming here
                # keeps every one of those working unchanged while
                # fixing the actual bug (the *source* they were being
                # fed from, not the field name itself).
                "avg_price": p.avg_entry_price,
                "current_price": p.current_price,
                "notional_value": p.notional_value,
                "market_value": p.market_value,
                "unrealized_pnl": p.unrealized_pnl,
                "realized_pnl": p.realized_pnl,
                "stop_price": p.stop_price,
                "target_price": p.target_price,
                "leverage": p.leverage,
                "status": p.status,
                "base_currency": p.base_currency,
                "quote_currency": p.quote_currency,
                "opened_at": p.opened_at,
                "updated_at": p.updated_at,
            }
            for p in positions
        ]

    def save_position(
        self,
        pair: str,
        side: str,
        units: float,
        avg_price: float,
        portfolio_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self.db is None or text is None:
            return {
                "status": "unavailable",
                "message": "Database is not available.",
            }

        #self.ensure_tables()

        pair = normalize_pair(pair)
        side = str(side or "").upper()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        self.db.execute(text("""
            INSERT INTO forex_positions (
                tenant_id,
                portfolio_id,
                user_id,
                pair,
                side,
                units,
                avg_price,
                opened_at,
                updated_at,
                status
            )
            VALUES (
                :tenant_id,
                :portfolio_id,
                :user_id,
                :pair,
                :side,
                :units,
                :avg_price,
                :opened_at,
                :updated_at,
                'OPEN'
            )
        """), {
            "tenant_id": tenant_id,
            "portfolio_id": portfolio_id,
            "user_id": user_id,
            "pair": pair,
            "side": side,
            "units": float(units),
            "avg_price": float(avg_price),
            "opened_at": now,
            "updated_at": now,
        })

        try:

            # multiple related INSERT/UPDATE/DELETE statements

            self.db.commit()
            self.cache.invalidate_portfolio(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
            )

        except Exception:

            if self.db is not None:
                self.db.rollback()

            raise

        return {
            "status": "saved",
            "pair": pair,
            "side": side,
            "units": float(units),
            "avg_price": float(avg_price),
        }

    # ------------------------------------------------------------------
    # Mark-to-market
    # ------------------------------------------------------------------

    def mark_positions(
        self,
        positions: Optional[List[Dict[str, Any]]] = None,
        portfolio_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        positions = positions if positions is not None else self.load_positions(
            portfolio_id=portfolio_id,
            user_id=user_id,
            tenant_id=tenant_id,
            force_refresh=force_refresh,
        )

        pairs = [normalize_pair(p.get("pair")) for p in positions if p.get("pair")]
        quotes = {}

        if self.price_service and pairs:
            try:
                quotes = self.price_service.get_quotes(
                    list(dict.fromkeys(pairs)),
                    force_refresh=force_refresh,
                )
            except Exception:
                quotes = {}

        marked = []

        for position in positions:
            pair = normalize_pair(position.get("pair"))
            base, quote_ccy = split_pair(pair)
            side = str(position.get("side") or "LONG").upper()
            units = safe_float(position.get("units"))
            avg_price = safe_float(position.get("avg_price"))

            quote = quotes.get(pair, {})
            current = safe_float(quote.get("mid") or quote.get("last"), avg_price)

            signed_units = units if side in ("LONG", "BUY") else -abs(units)
            notional = abs(units) * current
            market_value = signed_units * current
            pnl = self._calculate_pnl(side, units, avg_price, current)
            pnl_pct = (pnl / max(abs(units * avg_price), 1e-9)) * 100.0

            marked.append(
                ForexPosition(
                    pair=pair,
                    side=side,
                    units=units,
                    avg_price=round(avg_price, 6),
                    current_price=round(current, 6),
                    notional=round(notional, 2),
                    market_value=round(market_value, 2),
                    unrealized_pnl=round(pnl, 2),
                    unrealized_pnl_pct=round(pnl_pct, 4),
                    base_currency=base,
                    quote_currency=quote_ccy,
                    provider=quote.get("provider"),
                    opened_at=str(position.get("opened_at")) if position.get("opened_at") else None,
                    updated_at=utc_now_iso(),
                ).to_dict()
            )

        return marked

    def portfolio_summary(
        self,
        positions: Optional[List[Dict[str, Any]]] = None,
        portfolio_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        # force_refresh accepted for backward compatibility; no effect
        # -- this always reads live from ForexPortfolioEngine now (see
        # class docstring), so there's no cache to bypass.
        try:
            if positions is None:

                marked = self.mark_positions(
                    portfolio_id=portfolio_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    force_refresh=force_refresh,
                )

            else:

                marked = positions

        except Exception as exc:
            print("=" * 80)
            print("PORTFOLIO SUMMARY FAILED")
            print(type(exc))
            print(exc)

            import traceback
            traceback.print_exc()

            if self.db is not None:

                try:
                    self.db.rollback()
                    print("ROLLBACK COMPLETED")
                except Exception as rb:
                    print("ROLLBACK FAILED:", rb)

            raise

        total_notional = sum(safe_float(p.get("notional")) for p in marked)
        total_pnl = sum(safe_float(p.get("unrealized_pnl")) for p in marked)
        winners = len([p for p in marked if safe_float(p.get("unrealized_pnl")) > 0])
        losers = len([p for p in marked if safe_float(p.get("unrealized_pnl")) < 0])

        exposure = self.currency_exposure(marked)

        summary = {
            "generated_at": utc_now_iso(),
            "account_currency": self.account_currency,
            "positions": marked,
            "summary": {
                "open_positions": len(marked),
                "total_notional": round(total_notional, 2),
                "unrealized_pnl": round(total_pnl, 2),
                "winners": winners,
                "losers": losers,
                "win_rate": round(
                    winners / max(len(marked), 1) * 100.0,
                    2,
                ),
                "gross_exposure": round(
                    sum(
                        abs(safe_float(p.get("market_value")))
                        for p in marked
                    ),
                    2,
                ),
            },
            "currency_exposure": exposure,
            "risk": self.risk_metrics(marked),
        }

        return summary

    def currency_exposure(self, marked_positions: List[Dict[str, Any]]) -> Dict[str, float]:
        exposure: Dict[str, float] = {}

        for pos in marked_positions:
            base = pos.get("base_currency")
            quote = pos.get("quote_currency")
            side = str(pos.get("side") or "LONG").upper()
            notional = safe_float(pos.get("notional"))

            base_sign = 1.0 if side in ("LONG", "BUY") else -1.0
            quote_sign = -base_sign

            exposure[base] = exposure.get(base, 0.0) + notional * base_sign
            exposure[quote] = exposure.get(quote, 0.0) + notional * quote_sign

        return {k: round(v, 2) for k, v in sorted(exposure.items())}

    def risk_metrics(self, marked_positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        notionals = [abs(safe_float(p.get("notional"))) for p in marked_positions]
        pnls = [safe_float(p.get("unrealized_pnl")) for p in marked_positions]

        total_notional = sum(notionals)
        largest_position = max(notionals) if notionals else 0.0
        concentration = largest_position / max(total_notional, 1.0) * 100.0

        return {
            "total_notional": round(total_notional, 2),
            "largest_position": round(largest_position, 2),
            "concentration_pct": round(concentration, 2),
            "portfolio_pnl": round(sum(pnls), 2),
            "risk_state": "ELEVATED" if concentration >= 40 else "NORMAL",
        }

    # ------------------------------------------------------------------
    # Paper trading helpers
    # ------------------------------------------------------------------

    def submit_paper_order(
        self,
        pair: str,
        side: str,
        units: float,
        portfolio_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        pair = normalize_pair(pair)
        side = str(side or "").upper()

        quote = {}
        if self.price_service:
            quote = self.price_service.get_quote(pair, force_refresh=False)

        price = safe_float(quote.get("mid") or quote.get("last"))
        if price <= 0:
            return {
                "status": "rejected",
                "pair": pair,
                "reason": "No valid market price.",
                "quote": quote,
            }

        if self.db is not None and text is not None:
            #self.ensure_tables()
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            self.db.execute(text("""
                INSERT INTO forex_orders (
                    tenant_id,
                    portfolio_id,
                    user_id,
                    pair,
                    side,
                    order_type,
                    units,
                    requested_price,
                    filled_price,
                    status,
                    created_at,
                    filled_at
                )
                VALUES (
                    :tenant_id,
                    :portfolio_id,
                    :user_id,
                    :pair,
                    :side,
                    'market',
                    :units,
                    :requested_price,
                    :filled_price,
                    'paper_filled',
                    :created_at,
                    :filled_at
                )
            """), {
                "tenant_id": tenant_id,
                "portfolio_id": portfolio_id,
                "user_id": user_id,
                "pair": pair,
                "side": side,
                "units": float(units),
                "requested_price": price,
                "filled_price": price,
                "created_at": now,
                "filled_at": now,
            })

            self.save_position(
                pair=pair,
                side="LONG" if side == "BUY" else "SHORT",
                units=abs(float(units)),
                avg_price=price,
                portfolio_id=portfolio_id,
                user_id=user_id,
                tenant_id=tenant_id,
            )

        return {
            "status": "paper_filled",
            "pair": pair,
            "side": side,
            "units": float(units),
            "filled_price": price,
            "provider": quote.get("provider"),
            "filled_at": utc_now_iso(),
        }

    def recommended_orders(
        self,
        limit: int = 5,
        min_alpha_score: float = 68.0,
    ) -> List[Dict[str, Any]]:
        if self.alpha_model is None:
            return []

        rows = self.alpha_model.get_top_opportunities(
            limit=limit,
            min_alpha_score=min_alpha_score,
            force_refresh=False,
        )

        orders = []
        for row in rows:
            recommendation = str(row.get("recommendation") or "")
            if "BUY" in recommendation:
                side = "BUY"
            elif "SELL" in recommendation:
                side = "SELL"
            else:
                continue

            orders.append({
                "pair": row.get("pair"),
                "side": side,
                "entry_price": row.get("entry_price"),
                "stop_price": row.get("stop_price"),
                "target_price": row.get("target_price"),
                "risk_reward": row.get("risk_reward"),
                "suggested_notional": row.get("suggested_notional"),
                "alpha_score": row.get("alpha_score"),
                "confidence_score": row.get("confidence_score"),
                "rationale": row.get("rationale"),
            })

        return orders

    def _calculate_pnl(self, side: str, units: float, avg_price: float, current_price: float) -> float:
        side = str(side or "LONG").upper()
        if side in ("SHORT", "SELL"):
            return (avg_price - current_price) * abs(units)
        return (current_price - avg_price) * abs(units)

    # ------------------------------------------------------------------
    # Portfolio CRUD
    # ------------------------------------------------------------------

    def portfolio_list(self):

        return self.portfolio_engine.list_portfolios(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

    def active_portfolio(self):

        portfolio = self.portfolio_engine.get_default_portfolio(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

        if portfolio is None:

            portfolios = self.portfolio_list()

            if portfolios:
                portfolio = portfolios[0]

        if portfolio:
            self.portfolio_id = portfolio["id"]

        return portfolio

    def create_portfolio(self, **kwargs):

        return self.portfolio_engine.create_portfolio(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            **kwargs,
        )

    def update_portfolio(self, **kwargs):

        return self.portfolio_engine.update_portfolio(
            **kwargs,
        )

    def delete_portfolio(self, portfolio_id):

        return self.portfolio_engine.delete_portfolio(
            portfolio_id,
        )

    def archive_portfolio(self, portfolio_id):

        return self.portfolio_engine.archive_portfolio(
            portfolio_id,
        )

    def restore_portfolio(self, portfolio_id):

        return self.portfolio_engine.restore_portfolio(
            portfolio_id,
        )

    def set_default_portfolio(self, portfolio_id):
        self.portfolio_engine.set_default_portfolio(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=portfolio_id,
        )

        self.portfolio_id = portfolio_id

        return portfolio_id

    # ============================================================
    # Portfolio CRUD Wrappers
    # ============================================================

    def portfolio_statistics(self):

        return self.portfolio_engine.portfolio_statistics(

            tenant_id=self.tenant_id,

            user_id=self.user_id,

        )

    def portfolio_list(self):

        return self.portfolio_engine.list_portfolios(

            tenant_id=self.tenant_id,

            user_id=self.user_id,

        )

    def active_portfolio(self):

        portfolio = self.portfolio_engine.get_default_portfolio(

            tenant_id=self.tenant_id,

            user_id=self.user_id,

        )

        if portfolio is None:

            portfolios = self.portfolio_list()

            if portfolios:
                portfolio = portfolios[0]

        if portfolio:
            self.portfolio_id = portfolio["id"]

        return portfolio

    def create_portfolio(self, **kwargs):

        return self.portfolio_engine.create_portfolio(

            tenant_id=self.tenant_id,

            user_id=self.user_id,

            **kwargs,

        )

    def update_portfolio(self, **kwargs):

        return self.portfolio_engine.update_portfolio(

            **kwargs,

        )

    def delete_portfolio(self, portfolio_id):

        return self.portfolio_engine.delete_portfolio(

            portfolio_id,

        )

    def archive_portfolio(self, portfolio_id):

        return self.portfolio_engine.archive_portfolio(

            portfolio_id,

        )

    def restore_portfolio(self, portfolio_id):

        return self.portfolio_engine.restore_portfolio(

            portfolio_id,

        )

    def set_default_portfolio(self, portfolio_id):

        self.portfolio_engine.set_default_portfolio(

            tenant_id=self.tenant_id,

            user_id=self.user_id,

            portfolio_id=portfolio_id,

        )

        self.portfolio_id = portfolio_id

        return portfolio_id

# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_MANAGER = None

def get_forex_portfolio_manager(
        db=None,
        tenant_id=None,
        user_id=None,
        portfolio_id=None,
):
    global _MANAGER

    # Normalize the same way ForexPortfolioManager.__init__ does before
    # comparing against the cached instance - otherwise a None argument
    # here would never equal the cached manager's normalized "default"
    # attribute, defeating the singleton cache on every single call.
    normalized_tenant_id = str(tenant_id) if tenant_id is not None else "default"
    normalized_user_id = str(user_id) if user_id is not None else "default"

    # Comparing db session objects by identity (db is not db) meant
    # every distinct session instance -- even one pointed at the exact
    # same database -- looked "different" and triggered a full
    # ForexPortfolioManager rebuild. Confirmed directly: this was the
    # SAME bug as the one already fixed in
    # get_forex_portfolio_crud_engine(), one layer further out --
    # fixing the inner crud engine alone wasn't enough, since THIS
    # factory rebuilds the whole manager (re-running its entire
    # __init__, not just the crud-engine lookup) on every single
    # Streamlit rerun for the same reason. Comparing the underlying
    # engine (db.bind) instead of the session object fixes this the
    # same way: different sessions against the SAME database correctly
    # reuse the cached manager, while a genuinely different database
    # still correctly triggers a rebuild.
    current_bind = getattr(db, "bind", None) if db is not None else None
    cached_bind = getattr(_MANAGER.db, "bind", None) if _MANAGER is not None and _MANAGER.db is not None else None

    if (
            _MANAGER is None
            or (db is not None and current_bind is not cached_bind)
            or _MANAGER.tenant_id != normalized_tenant_id
            or _MANAGER.user_id != normalized_user_id
            or _MANAGER.portfolio_id != portfolio_id
    ):
        _MANAGER = ForexPortfolioManager(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

    return _MANAGER