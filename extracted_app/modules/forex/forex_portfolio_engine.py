# modules/forex/forex_portfolio_engine.py

from __future__ import annotations

try:
    # Only available (and only needed) when actually running against
    # Postgres. Importing this unconditionally made the whole module -
    # and therefore the whole trading desk - fail to import on any
    # environment that doesn't have psycopg2 installed, including a
    # plain SQLite/local setup.
    from psycopg2.extras import Json as _PgJson
except Exception:
    _PgJson = None
import json
import math
import logging
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import text
from modules.forex.forex_common import (
        normalize_pair, split_pair
    )
try:
    from modules.forex.forex_service import (
        ForexService,
        get_forex_service,
    )

except Exception as e:
    print("FOREX SERVICE IMPORT FAILED")
    print(e)
    raise

try:
    from modules.forex.forex_ai import (
        ForexAIEngine,
        get_forex_ai_engine,
    )
except Exception as e:
    print("FOREX AI IMPORT FAILED")
    print(e)
    raise


logger = logging.getLogger(__name__)
#
# Sprint 26
# Prevent repeated DDL execution.
#
_INITIALIZED = False

DEFAULT_ACCOUNT_CURRENCY = "USD"
DEFAULT_STARTING_CASH = 100000.0
DEFAULT_MAX_PAIR_EXPOSURE_PCT = 0.15
DEFAULT_MAX_TOTAL_EXPOSURE_PCT = 0.75
DEFAULT_MAX_RISK_PER_TRADE_PCT = 0.02


@dataclass
class ForexPortfolioAccount:
    id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    account_name: str
    account_currency: str
    cash_balance: float
    realized_pnl: float
    unrealized_pnl: float
    equity: float
    margin_used: float
    margin_available: float
    leverage: float
    status: str
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data


@dataclass
class ForexPosition:
    id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    account_id: str
    pair: str
    base_currency: str
    quote_currency: str
    side: str
    units: float
    avg_entry_price: float
    current_price: float
    notional_value: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    stop_price: Optional[float]
    target_price: Optional[float]
    margin_required: float
    leverage: float
    status: str
    opened_at: datetime
    updated_at: datetime
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["opened_at"] = self.opened_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data


@dataclass
class ForexPortfolioSnapshot:
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    account_id: str
    account_currency: str
    cash_balance: float
    equity: float
    total_notional: float
    total_market_value: float
    total_unrealized_pnl: float
    total_realized_pnl: float
    margin_used: float
    margin_available: float
    exposure_pct: float
    position_count: int
    long_count: int
    short_count: int
    risk_score: float
    warnings: str
    asof: datetime
    positions: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["asof"] = self.asof.isoformat()
        return data


@dataclass
class ForexPortfolioRiskResult:
    account_id: str
    equity: float
    total_notional: float
    exposure_pct: float
    margin_used: float
    margin_available: float
    largest_position_pct: float
    concentration_score: float
    leverage_score: float
    liquidity_score: float
    pnl_score: float
    risk_score: float
    warnings: str
    asof: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["asof"] = self.asof.isoformat()
        return data


@dataclass
class ForexTerminalSnapshot:
    """
    Unified institutional terminal snapshot.

    This is the single source-of-truth payload for the Forex terminal UI.
    It intentionally combines account, portfolio, positions, orders,
    executions, exposure, risk, and performance into one stable structure.
    """

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    account_id: str
    generated_at: datetime
    account: Dict[str, Any]
    portfolio: Dict[str, Any]
    positions: List[Dict[str, Any]]
    open_orders: List[Dict[str, Any]]
    filled_orders: List[Dict[str, Any]]
    execution_history: List[Dict[str, Any]]
    cash_ledger: List[Dict[str, Any]]
    currency_exposure: List[Dict[str, Any]]
    pair_exposure: List[Dict[str, Any]]
    risk: Dict[str, Any]
    performance: Dict[str, Any]
    margin: Dict[str, Any]
    system: Dict[str, Any]
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["generated_at"] = self.generated_at.isoformat()
        return data


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _naive_utc_now() -> datetime:
    return _utc_now().replace(tzinfo=None)


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


def _round(value: Any, places: int = 6) -> float:
    return round(_safe_float(value), places)


def _coerce_datetime(value: Any) -> datetime:
    """
    Normalize a value read back from the DB into an aware UTC datetime.

    Postgres (via psycopg2) auto-converts TIMESTAMP columns into Python
    datetime objects, but SQLite (via sqlite3/SQLAlchemy) returns them as
    plain ISO-format strings for ad-hoc `text()` queries like the ones this
    module uses. Code that assumed every row always yields a real datetime
    (e.g. `created_at.tzinfo`) crashed with
    "'str' object has no attribute 'tzinfo'" as soon as it ran against
    SQLite.
    """
    if value is None:
        return _utc_now()
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text_value = value.strip()
        if not text_value:
            return _utc_now()
        try:
            return datetime.fromisoformat(text_value.replace("Z", "+00:00"))
        except Exception:
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(text_value, fmt)
                except Exception:
                    continue
            return _utc_now()
    return _utc_now()


def _dialect_name(db: Any) -> str:
    """Best-effort detection of the SQLAlchemy dialect (postgresql/sqlite/...)."""
    try:
        bind = getattr(db, "bind", None)
        if bind is None and hasattr(db, "get_bind"):
            bind = db.get_bind()
        if bind is not None:
            return bind.dialect.name
    except Exception:
        pass
    try:
        return db.dialect.name
    except Exception:
        pass
    return "unknown"



def _json_payload(value):
    if value is None:
        return None

    # A plain JSON string is portable: SQLite stores it as TEXT, and
    # Postgres has a registered implicit assignment cast from text to
    # json/jsonb, so this works for INSERT/UPDATE against either
    # database without needing the psycopg2-specific Json() wrapper.
    return json.dumps(value, default=str)


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return getattr(row, key)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Liquidity estimate for calculate_risk().
#
# This used to call self.forex_ai_engine.generate_signal(pair, save=False)
# once per open position purely to read one field (liquidity_score) off the
# result, discarding the rest. generate_signal() runs the full 28-pair
# alpha-model pipeline (live quote waterfall across every configured pair) --
# real console timing showed this costing anywhere from ~10s to ~37s per
# render depending on provider health, and it was called twice per snapshot
# (once directly, once again inside get_snapshot()), so N open positions
# meant 2N full alpha-model runs on every single terminal render.
#
# A TTL cache was added first, but that only relocated the problem: whenever
# a render took longer than the TTL (which kept happening, partly *because*
# of this same expensive call), the cache had already expired by the next
# render, so it was a cache miss again on every single click regardless of
# the TTL value.
#
# The real fix is that this call was never the right tool for the job --
# alpha score measures trade opportunity, not market liquidity. Liquidity in
# FX is a function of which currencies are involved: USD, EUR, GBP, and JPY
# are the four most-traded currencies globally per the BIS Triennial Central
# Bank Survey, and pairs combining more of them trade on deeper,
# tighter-spread markets. That's stable market structure, not something
# that needs a live model re-run per click.
_MAJOR_FX_CURRENCIES = {"USD", "EUR", "GBP", "JPY"}


class ForexPortfolioEngine:
    """
    Tenant-safe Forex portfolio/account engine.

    Responsibilities:
    - Forex account creation/loading.
    - Forex position tracking.
    - Cash/equity/margin calculations.
    - Exposure/risk snapshots.
    - Neon Postgres persistence.

    Architecture:
    - No global runtime state.
    - All tenant/user/portfolio/db context is explicitly passed.
    - Streamlit compatible.
    """

    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        db: Any = None,
        forex_service: Optional[ForexService] = None,
        forex_ai_engine: Optional[ForexAIEngine] = None,
        account_currency: str = DEFAULT_ACCOUNT_CURRENCY,
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id
        self.db = db
        self.db_engine = None
        from modules.forex.forex_db_session_manager import ForexDBSessionManager

        #self.db_engine = ForexDBSessionManager(db)
        self.account_currency = str(account_currency or DEFAULT_ACCOUNT_CURRENCY).upper()

        self.forex_service = forex_service or get_forex_service(
            tenant_id=tenant_id,
            user_id=user_id,
            db=db,
        )
        self.forex_ai_engine = forex_ai_engine or get_forex_ai_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            db=db,
            forex_service=self.forex_service,
        )
        #
        # NOT "already bootstrapped" -- this used to be hardcoded True
        # here, unconditionally, on every instantiation, with a comment
        # claiming "Portfolio persistence is initialized during Forex
        # bootstrap." That bootstrap step isn't guaranteed to have run
        # (it didn't, in testing, and there's no enforcement that it
        # runs before a ForexPortfolioEngine is ever constructed in a
        # fresh deployment either). With this hardcoded True,
        # ensure_tables()'s own guard (`if self._tables_ready: return`)
        # always took the early-return path and never once ran its
        # CREATE TABLE statements -- so forex_accounts/forex_positions/
        # forex_cash_ledger/forex_portfolio_snapshots could be
        # permanently missing. The failure was silent and easy to miss
        # downstream: create_account() builds a valid-looking
        # ForexPortfolioAccount object in memory regardless of whether
        # _persist_account() actually succeeded (it only logs a
        # warning on failure, never raises or signals the caller), so
        # order submission would validate successfully against an
        # account that was never actually saved, then fail later with
        # a confusing "Forex account not found" once something tried
        # to re-fetch it from the table that was never created.
        #
        # This class's raw-SQL ensure_tables() is the legacy path --
        # forex is mid-migration onto modules.execution's shared
        # ExecutionAccountRepository/ExecutionPositionRepository, which
        # define their own ensure_tables() for the same table names.
        # That migration isn't finished: those newer repositories
        # create forex_accounts with a genuinely different, incompatible
        # column set (base_currency/cash/used_margin/free_margin, no
        # leverage) than this class's own queries expect
        # (account_currency/cash_balance/margin_used/margin_available/
        # leverage). open_position() and friends below still use this
        # class's own legacy schema, so this fix (and callers relying on
        # this class's own ensure_tables()) is correct for what actually
        # runs today -- switching to the newer repositories' table
        # creation here would create the wrong schema and break this
        # class's own queries.
        self._tables_ready = False

    def _notional_in_account_currency(
        self,
        units: float,
        price: float,
        base_currency: str,
        quote_currency: str,
    ) -> float:
        """
        `units` is always denominated in the pair's BASE currency (e.g. 10,000
        units of USD/JPY means $10,000 notional, same as 10,000 units of
        EUR/USD meaning €10,000 notional). `units * price` only lands in the
        account currency when the QUOTE currency matches the account
        currency (true for EUR/USD, GBP/USD when the account is USD) --
        for pairs where the account currency is the BASE instead (USD/JPY,
        USD/CHF, USD/CAD when the account is USD), that formula returns a
        quote-currency amount (e.g. JPY), not USD, inflating the value by
        roughly the exchange rate (~158x for USD/JPY). This normalizes to a
        single account-currency notional regardless of quote direction.
        """
        base = (base_currency or "").upper()
        quote = (quote_currency or "").upper()
        acct = self.account_currency

        if quote == acct:
            return units * price
        if base == acct:
            return units
        # Cross pair not involving the account currency directly (e.g. a USD
        # account trading EUR/GBP) -- best-effort fallback, since a true
        # conversion needs a third exchange rate we don't have here.
        return units * price

    def _db(self):
        """
        Safe DB accessor.
        Keeps backward compatibility while we migrate.
        """
        return self.db
    # ==========================================================
    # Database Helpers
    # ==========================================================

    def _execute(self, stmt, params=None):
        if self.db_engine is not None:
            return self.db_engine.execute(stmt, params)
        return self.db.execute(stmt, params or {})

    def _fetchone(self, stmt, params=None):
        if self.db_engine is not None:
            return self.db_engine.fetchone(stmt, params)
        return self.db.execute(stmt, params or {}).fetchone()

    def _fetchall(self, stmt, params=None):
        if self.db_engine is not None:
            return self.db_engine.fetchall(stmt, params)
        return self.db.execute(stmt, params or {}).fetchall()

    def ensure_tables(self) -> None:

        global _INITIALIZED

        if _INITIALIZED:
            return

        if self._tables_ready:
            return

        if self.db is None:
            return

        dialect = _dialect_name(self.db)
        serial_pk = (
            "id INTEGER PRIMARY KEY AUTOINCREMENT"
            if dialect == "sqlite"
            else "id SERIAL PRIMARY KEY"
        )

        self.db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS forex_accounts (
                id VARCHAR(64) PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                account_name VARCHAR(160),
                account_currency VARCHAR(3) DEFAULT 'USD',
                cash_balance DOUBLE PRECISION DEFAULT 0,
                realized_pnl DOUBLE PRECISION DEFAULT 0,
                unrealized_pnl DOUBLE PRECISION DEFAULT 0,
                equity DOUBLE PRECISION DEFAULT 0,
                margin_used DOUBLE PRECISION DEFAULT 0,
                margin_available DOUBLE PRECISION DEFAULT 0,
                leverage DOUBLE PRECISION DEFAULT 1,
                status VARCHAR(40) DEFAULT 'ACTIVE',
                raw_payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))

        self.db.execute(text(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_accounts_tenant_portfolio
            ON forex_accounts (tenant_id, portfolio_id)
            """
        ))

        self.db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS forex_positions (
                id VARCHAR(64) PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                account_id VARCHAR(64),
                pair VARCHAR(20) NOT NULL,
                base_currency VARCHAR(3),
                quote_currency VARCHAR(3),
                side VARCHAR(10) NOT NULL,
                units DOUBLE PRECISION NOT NULL,
                avg_entry_price DOUBLE PRECISION NOT NULL,
                current_price DOUBLE PRECISION,
                notional_value DOUBLE PRECISION,
                market_value DOUBLE PRECISION,
                unrealized_pnl DOUBLE PRECISION DEFAULT 0,
                realized_pnl DOUBLE PRECISION DEFAULT 0,
                stop_price DOUBLE PRECISION,
                target_price DOUBLE PRECISION,
                margin_required DOUBLE PRECISION DEFAULT 0,
                leverage DOUBLE PRECISION DEFAULT 1,
                status VARCHAR(40) DEFAULT 'OPEN',
                raw_payload JSONB,
                opened_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))

        self.db.execute(text(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_positions_tenant_account_pair
            ON forex_positions (tenant_id, account_id, pair)
            """
        ))

        self.db.execute(text(
            f"""
            CREATE TABLE IF NOT EXISTS forex_cash_ledger (
                {serial_pk},
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                account_id VARCHAR(64),
                event_type VARCHAR(80),
                amount DOUBLE PRECISION,
                currency VARCHAR(3),
                balance_after DOUBLE PRECISION,
                notes TEXT,
                raw_payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))

        self.db.execute(text(
            f"""
            CREATE TABLE IF NOT EXISTS forex_portfolio_snapshots (
                {serial_pk},
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                account_id VARCHAR(64),
                account_currency VARCHAR(3),
                cash_balance DOUBLE PRECISION,
                equity DOUBLE PRECISION,
                total_notional DOUBLE PRECISION,
                total_market_value DOUBLE PRECISION,
                total_unrealized_pnl DOUBLE PRECISION,
                total_realized_pnl DOUBLE PRECISION,
                margin_used DOUBLE PRECISION,
                margin_available DOUBLE PRECISION,
                exposure_pct DOUBLE PRECISION,
                position_count INTEGER,
                long_count INTEGER,
                short_count INTEGER,
                risk_score DOUBLE PRECISION,
                warnings TEXT,
                payload JSONB,
                asof TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))

        if hasattr(self.db, "commit"):
            self.db.commit()
            self._tables_ready = True
            _INITIALIZED = True

    def create_account(
        self,
        *,
        account_name: str = "Forex Paper Account",
        account_currency: Optional[str] = None,
        starting_cash: float = DEFAULT_STARTING_CASH,
        leverage: float = 10.0,
        portfolio_id: Optional[str] = None,
    ) -> ForexPortfolioAccount:
        account_id = str(uuid.uuid4())
        now = _utc_now()
        currency = str(account_currency or self.account_currency).upper()
        cash = _safe_float(starting_cash, DEFAULT_STARTING_CASH)
        account_portfolio_id = portfolio_id or self.portfolio_id
        margin_available = cash * _safe_float(leverage, 1.0)

        account = ForexPortfolioAccount(
            id=account_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=account_portfolio_id,
            account_name=account_name,
            account_currency=currency,
            cash_balance=cash,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            equity=cash,
            margin_used=0.0,
            margin_available=margin_available,
            leverage=_safe_float(leverage, 1.0),
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )

        self._persist_account(account)
        self._record_cash_event(
            account_id=account.id,
            event_type="ACCOUNT_CREATED",
            amount=cash,
            currency=currency,
            balance_after=cash,
            notes="Forex account created.",
        )
        #
        # Create the initial portfolio snapshot
        #
        try:
            self.get_snapshot(
                account_id=account.id,
                persist=True,
                refresh=False,  # No positions yet; avoid unnecessary refresh
            )
        except Exception as exc:
            logger.exception(
                "Failed to create initial Forex portfolio snapshot.",
                exc_info=exc,
            )

        return account


    def get_or_create_account(
        self,
        *,
        portfolio_id: Optional[str] = None,
        account_name: str = "Forex Paper Account",
        starting_cash: float = DEFAULT_STARTING_CASH,
        leverage: float = 10.0,
    ) -> ForexPortfolioAccount:
        existing = self.get_account(portfolio_id=portfolio_id or self.portfolio_id)
        if existing:
            return existing

        return self.create_account(
            account_name=account_name,
            starting_cash=starting_cash,
            leverage=leverage,
            portfolio_id=portfolio_id or self.portfolio_id,
        )

    def get_account(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> Optional[ForexPortfolioAccount]:
        if self.db is None:
            return None

        try:
            #self.ensure_tables()

            params: Dict[str, Any] = {
                "tenant_id": self.tenant_id,
            }
            where = "tenant_id = :tenant_id"

            # ---------------------------------------------------------
            # Lookup by account id
            # ---------------------------------------------------------

            if account_id:

                params = {
                    "account_id": account_id,
                }

                where = "id = :account_id"

            else:

                params = {
                    "tenant_id": self.tenant_id,
                }

                where = "tenant_id = :tenant_id"

                resolved_portfolio = portfolio_id or self.portfolio_id

                if resolved_portfolio is None:

                    where += " AND portfolio_id IS NULL"

                else:

                    where += " AND portfolio_id = :portfolio_id"

                    params["portfolio_id"] = resolved_portfolio
                    print("=" * 80)
                    print("ACCOUNT LOOKUP")
                    print("tenant    :", self.tenant_id)
                    print("portfolio :", portfolio_id or self.portfolio_id)
                    print("where     :", where)
                    print("params    :", params)
                    print("=" * 80)

            row = self.db.execute(text(
                f"""
                SELECT *
                FROM forex_accounts
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT 1
                """),
                params,
            ).fetchone()

            if not row:
                return None

            return self._account_from_row(row)

        except Exception as exc:
            logger.warning("Failed to get forex account: %s", exc)
            return None

    def deposit_cash(
        self,
        *,
        account_id: str,
        amount: float,
        currency: Optional[str] = None,
        notes: str = "Cash deposit.",
    ) -> Optional[ForexPortfolioAccount]:
        account = self.get_account(account_id=account_id)
        if not account:
            return None

        deposit_amount = _safe_float(amount)
        if deposit_amount <= 0:
            raise ValueError("Deposit amount must be positive.")

        account.cash_balance += deposit_amount
        account.equity += deposit_amount
        account.margin_available = max(0.0, account.equity * account.leverage - account.margin_used)
        account.updated_at = _utc_now()

        self._persist_account(account)
        self._record_cash_event(
            account_id=account.id,
            event_type="DEPOSIT",
            amount=deposit_amount,
            currency=currency or account.account_currency,
            balance_after=account.cash_balance,
            notes=notes,
        )
        return account

    def withdraw_cash(
        self,
        *,
        account_id: str,
        amount: float,
        currency: Optional[str] = None,
        notes: str = "Cash withdrawal.",
    ) -> Optional[ForexPortfolioAccount]:
        account = self.get_account(account_id=account_id)
        if not account:
            return None

        withdrawal_amount = _safe_float(amount)
        if withdrawal_amount <= 0:
            raise ValueError("Withdrawal amount must be positive.")
        if withdrawal_amount > account.cash_balance:
            raise ValueError("Withdrawal amount exceeds available cash.")

        account.cash_balance -= withdrawal_amount
        account.equity -= withdrawal_amount
        account.margin_available = max(0.0, account.equity * account.leverage - account.margin_used)
        account.updated_at = _utc_now()

        self._persist_account(account)
        self._record_cash_event(
            account_id=account.id,
            event_type="WITHDRAWAL",
            amount=-withdrawal_amount,
            currency=currency or account.account_currency,
            balance_after=account.cash_balance,
            notes=notes,
        )
        return account

    def open_position(
        self,
        *,
        account_id: str,
        pair: str,
        side: str,
        units: float,
        entry_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        target_price: Optional[float] = None,
        leverage: Optional[float] = None,
        raw: Optional[Dict[str, Any]] = None,
    ) -> ForexPosition:
        print("=" * 80)
        print("OPEN POSITION")
        print("tenant_id   :", self.tenant_id)
        print("user_id     :", self.user_id)
        print("portfolio_id:", self.portfolio_id)
        print("account_id  :", account_id)
        print("=" * 80)
        account = self.get_account(account_id=account_id)
        if not account:
            raise ValueError(f"Forex account not found: {account_id}")

        normalized_pair = normalize_pair(pair)
        base_currency, quote_currency = split_pair(normalized_pair)

        normalized_side = str(side or "").strip().upper()
        if normalized_side not in {"LONG", "SHORT", "BUY", "SELL"}:
            raise ValueError("Forex position side must be LONG/SHORT or BUY/SELL.")

        if normalized_side == "BUY":
            normalized_side = "LONG"
        if normalized_side == "SELL":
            normalized_side = "SHORT"

        position_units = _safe_float(units)
        if position_units <= 0:
            raise ValueError("Forex units must be positive.")

        quote = self.forex_service.get_quote(normalized_pair)

        print("=" * 80)
        print("FOREX QUOTE")
        print("pair :", normalized_pair)
        print("quote:", quote)

        if quote is not None:
            print("price :", getattr(quote, "price", None))
            print("bid   :", getattr(quote, "bid", None))
            print("ask   :", getattr(quote, "ask", None))

        print("=" * 80)
        quote_price = _safe_float(getattr(quote, "price", None))

        price = _safe_float(entry_price)

        if price <= 0:
            price = quote_price

        if price <= 0:
            raise ValueError(
                f"Unable to determine entry price for {normalized_pair}."
            )
        print("=" * 80)
        print("PRICE DEBUG")
        print("entry_price :", entry_price)
        print("quote.price :", quote.price)
        print("computed    :", price)
        print("type        :", type(price))
        print("=" * 80)
        if price <= 0:
            raise ValueError("Entry price must be positive.")

        effective_leverage = _safe_float(leverage, account.leverage)
        notional_value = self._notional_in_account_currency(position_units, price, base_currency, quote_currency)
        margin_required = notional_value / max(effective_leverage, 1.0)

        if margin_required > account.margin_available:
            raise ValueError("Insufficient margin available for forex position.")

        now = _utc_now()

        position = ForexPosition(
            id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=account.portfolio_id,
            account_id=account.id,
            pair=normalized_pair,
            base_currency=base_currency,
            quote_currency=quote_currency,
            side=normalized_side,
            units=position_units,
            avg_entry_price=price,
            current_price=quote.price,
            notional_value=notional_value,
            market_value=notional_value,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            stop_price=_safe_float(stop_price) if stop_price is not None else None,
            target_price=_safe_float(target_price) if target_price is not None else None,
            margin_required=margin_required,
            leverage=effective_leverage,
            status="OPEN",
            opened_at=now,
            updated_at=now,
            raw=raw,
        )

        self._persist_position(position)
        print("POSITION PERSISTED")
        self.recalculate_account(account.id)
        print("ACCOUNT RECALCULATED")
        print("RETURNING POSITION")
        return position

    def close_position(

            self,
            *,
            position_id: str,
            close_price: Optional[float] = None,
            close_units: Optional[float] = None,
            # Aliases for modules.execution.execution_position_pipeline.
            # ExecutionPositionPipeline.close(), which calls this with
            # quantity=/exit_price=/raw= -- added rather than renaming
            # close_units/close_price, since existing callers (e.g.
            # forex_trading_desk_dashboard.py) already use those names.
            quantity: Optional[float] = None,
            exit_price: Optional[float] = None,
            raw: Optional[Dict[str, Any]] = None,
            notes: str = "Position closed.",
    ) -> Optional[ForexPosition]:

        close_price = close_price if close_price is not None else exit_price
        close_units = close_units if close_units is not None else quantity

        # -----------------------------
        # SAFE ISOLATION START
        # -----------------------------
        print("=" * 80)
        print("ENTER close_position")
        print("position_id :", position_id)
        print("close_price :", close_price)
        print("close_units :", close_units)
        print("=" * 80)
        position = self.get_position(position_id=position_id)
        print("POSITION FOUND:", position is not None)

        if position:
            print("status :", position.status)
            print("units  :", position.units)
        if not position:
            return None

        if position.status != "OPEN":
            return position

        quote = self.forex_service.get_quote(position.pair)
        exit_price = _safe_float(close_price, quote.price)
        units_to_close = _safe_float(close_units, position.units)

        if units_to_close <= 0:
            raise ValueError("Close units must be positive.")
        if units_to_close > position.units:
            raise ValueError("Close units exceed open position units.")

        pnl = self._calculate_position_pnl(
            side=position.side,
            units=units_to_close,
            entry_price=position.avg_entry_price,
            current_price=exit_price,
            base_currency=position.base_currency,
            quote_currency=position.quote_currency,
        )

        # update position state
        position.realized_pnl += pnl
        position.units -= units_to_close
        position.current_price = exit_price
        position.updated_at = _utc_now()

        # fully close detection
        if position.units <= 1e-8:
            position.units = 0.0
            position.status = "CLOSED"
            position.unrealized_pnl = 0.0
            position.market_value = 0.0
            position.notional_value = 0.0
            position.margin_required = 0.0
        else:
            position.notional_value = self._notional_in_account_currency(
                position.units, exit_price, position.base_currency, position.quote_currency
            )
            position.market_value = position.notional_value
            position.unrealized_pnl = self._calculate_position_pnl(
                side=position.side,
                units=position.units,
                entry_price=position.avg_entry_price,
                current_price=exit_price,
                base_currency=position.base_currency,
                quote_currency=position.quote_currency,
            )
            position.margin_required = position.notional_value / max(position.leverage, 1.0)

        # -----------------------------
        # CRITICAL FIX: persist FIRST
        # -----------------------------
        print("Persisting updated position...")
        self._persist_position(position)
        print("Position persisted.")
        # account update MUST be isolated
        print("Looking up account:", position.account_id)
        account = self.get_account(account_id=position.account_id)
        print("ACCOUNT FOUND:", account is not None)
        if account:
            account.cash_balance += pnl
            account.realized_pnl += pnl
            account.updated_at = _utc_now()

            self._persist_account(account)

            self._record_cash_event(
                account_id=account.id,
                event_type="POSITION_CLOSED",
                amount=pnl,
                currency=account.account_currency,
                balance_after=account.cash_balance,
                notes=notes,
                raw={"position_id": position.id, "pair": position.pair},
            )

            # IMPORTANT: recalculation OUTSIDE DB transaction chain
            try:
                self.recalculate_account(account.id)
            except Exception as e:
                logger.warning("recalculate_account failed: %s", e)

        return position

    def modify_position(
        self,
        *,
        position_id: str,
        stop_price: Optional[float] = None,
        target_price: Optional[float] = None,
        raw: Optional[Dict[str, Any]] = None,
    ) -> Optional[ForexPosition]:
        """
        Update stop-loss/take-profit on an open position. Only touches
        the fields explicitly given (None means "leave unchanged", not
        "clear it" -- pass an explicit sentinel-free call site if a
        caller ever needs to actually clear one, this doesn't support
        that ambiguity today). Returns the updated ForexPosition, or
        None if the position doesn't exist or isn't open.

        New method -- modules.execution.execution_position_pipeline.
        ExecutionPositionPipeline.modify() calls
        self.portfolio_engine.modify_position(...), which didn't exist
        on this class before, so every stop/target update routed
        through ForexPositionManagementEngine (and scale_in/scale_out,
        which also go through this same pipeline path) failed with
        AttributeError.
        """
        position = self.get_position(position_id=position_id)

        if not position:
            logger.warning("modify_position: position not found | %s", position_id)
            return None

        if str(position.status).upper() != "OPEN":
            logger.warning(
                "modify_position: position not open | %s status=%s",
                position_id, position.status,
            )
            return None

        if stop_price is not None:
            position.stop_price = stop_price

        if target_price is not None:
            position.target_price = target_price

        position.updated_at = _utc_now()

        self._persist_position(position)

        return position

    def partial_close_position(
        self,
        *,
        position_id: str,
        quantity: float,
        exit_price: Optional[float] = None,
        raw: Optional[Dict[str, Any]] = None,
        notes: str = "Position partially closed.",
    ) -> Optional[ForexPosition]:
        """
        Closes part of an open position, leaving the remainder open.
        Thin wrapper around close_position(), which already supports a
        partial close_units < position.units -- this exists as a
        separate, explicitly-named method because
        ExecutionPositionPipeline.partial_close() calls
        self.portfolio_engine.partial_close_position(...) specifically
        (not close_position()), and that method didn't exist on this
        class before.
        """
        return self.close_position(
            position_id=position_id,
            close_units=quantity,
            close_price=exit_price,
            notes=notes,
        )

    def reverse_position(
        self,
        *,
        position_id: str,
        account_id: Optional[str] = None,
        leverage: Optional[float] = None,
        notes: str = "Position reversed.",
        raw: Optional[Dict[str, Any]] = None,
    ) -> Optional[ForexPosition]:
        """
        Close an open position and immediately open the opposite side.
        Returns the newly-opened (reversed) ForexPosition on success, or
        None if the position doesn't exist, isn't open, or reversal
        failed at any step -- callers that need the failure detail can
        call get_position() again or check logs; this keeps the return
        contract consistent with close_position() (an object or None,
        not a mixed status-dict-or-object).

        This method is intentionally portfolio/account logic, not UI logic.
        The dashboard should call this once, then refresh the terminal snapshot
        after the method returns.
        """
        position = self.get_position(position_id=position_id)

        if not position:
            logger.warning("reverse_position: position not found | %s", position_id)
            return None

        if str(position.status).upper() != "OPEN":
            logger.warning(
                "reverse_position: position not open | %s status=%s",
                position_id, position.status,
            )
            return None

        original_units = _safe_float(position.units)
        original_pair = position.pair
        original_side = str(position.side or "").upper()
        original_account_id = account_id or position.account_id
        original_leverage = _safe_float(leverage, position.leverage)

        reverse_side = "SHORT" if original_side in {"LONG", "BUY"} else "LONG"

        quote = self.forex_service.get_quote(original_pair)
        reverse_price = _safe_float(getattr(quote, "price", None), position.current_price)

        closed_position = self.close_position(
            position_id=position.id,
            close_units=original_units,
            close_price=reverse_price,
            notes=f"{notes} Close leg.",
        )

        if not closed_position:
            logger.error("reverse_position: failed to close original position | %s", position_id)
            return None

        try:
            new_position = self.open_position(
                account_id=original_account_id,
                pair=original_pair,
                side=reverse_side,
                units=original_units,
                entry_price=reverse_price,
                leverage=original_leverage,
                raw={
                    "source": "reverse_position",
                    "original_position_id": position.id,
                    "closed_position_id": closed_position.id,
                    "notes": notes,
                    **(raw or {}),
                },
            )

            self.recalculate_account(original_account_id)

            return new_position

        except Exception as exc:
            logger.exception(
                "reverse_position: original position closed but reverse open failed | %s: %s",
                position_id, exc,
            )
            return None

    def flatten_account(
        self,
        *,
        account_id: str,
        notes: str = "Flatten account.",
    ) -> Dict[str, Any]:
        """Close every open position for an account."""
        positions = self.list_positions(account_id=account_id, status="OPEN")

        closed: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        for position in positions:
            try:
                result = self.close_position(
                    position_id=position.id,
                    close_units=position.units,
                    close_price=position.current_price,
                    notes=notes,
                )
                if result:
                    closed.append(result.to_dict())
            except Exception as exc:
                logger.warning("Flatten account failed for %s: %s", position.id, exc)
                errors.append({
                    "position_id": position.id,
                    "pair": position.pair,
                    "error": str(exc),
                })

        self.recalculate_account(account_id)

        return {
            "status": "SUCCESS" if not errors else "PARTIAL_SUCCESS",
            "action": "FLATTEN_ACCOUNT",
            "account_id": account_id,
            "requested_count": len(positions),
            "closed_count": len(closed),
            "error_count": len(errors),
            "closed_positions": closed,
            "errors": errors,
            "refresh_required": True,
        }

    def flatten_pair(
        self,
        *,
        account_id: str,
        pair: str,
        notes: str = "Flatten pair.",
    ) -> Dict[str, Any]:
        """Close every open position for a specific pair in an account."""
        normalized_pair = normalize_pair(pair)
        positions = [
            position
            for position in self.list_positions(account_id=account_id, status="OPEN")
            if normalize_pair(position.pair) == normalized_pair
        ]

        closed: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        for position in positions:
            try:
                result = self.close_position(
                    position_id=position.id,
                    close_units=position.units,
                    close_price=position.current_price,
                    notes=notes,
                )
                if result:
                    closed.append(result.to_dict())
            except Exception as exc:
                logger.warning("Flatten pair failed for %s: %s", position.id, exc)
                errors.append({
                    "position_id": position.id,
                    "pair": position.pair,
                    "error": str(exc),
                })

        self.recalculate_account(account_id)

        return {
            "status": "SUCCESS" if not errors else "PARTIAL_SUCCESS",
            "action": "FLATTEN_PAIR",
            "account_id": account_id,
            "pair": normalized_pair,
            "requested_count": len(positions),
            "closed_count": len(closed),
            "error_count": len(errors),
            "closed_positions": closed,
            "errors": errors,
            "refresh_required": True,
        }

    def close_all_positions(
        self,
        *,
        account_id: str,
        notes: str = "Close all positions.",
    ) -> Dict[str, Any]:
        """Alias for flatten_account used by dashboards and command handlers."""
        return self.flatten_account(
            account_id=account_id,
            notes=notes,
        )

    def get_position(
        self,
        *,
        position_id: str,
    ) -> Optional[ForexPosition]:
        if self.db is None:
            return None

        try:
            #self.ensure_tables()

            row = self.db.execute(text(
                """
                SELECT *
                FROM forex_positions
                WHERE id = :position_id
                LIMIT 1
                """),
                {
                    "position_id": position_id,
                },
            ).fetchone()

            if not row:
                return None

            row_dict = dict(row._mapping)

            row_tenant = row_dict.get("tenant_id")
            if self.tenant_id is not None and row_tenant is not None and str(row_tenant) != str(self.tenant_id):
                return None

            return self._position_from_row(row)

        except Exception as exc:
            logger.warning("Failed to get forex position: %s", exc)
            self._rollback_quietly()
            return None

    def list_positions(
            self,
            *,
            account_id: Optional[str] = None,
            status: str = "OPEN",
    ) -> List[ForexPosition]:

        if self.db is None:
            return []

        try:
            #self.ensure_tables()

            params: Dict[str, Any] = {
                "tenant_id": self.tenant_id,
                "status": status,
            }

            where = "tenant_id = :tenant_id"

            if account_id:
                where += " AND account_id = :account_id"
                params["account_id"] = account_id

            if status and status.upper() != "ALL":
                where += " AND status = :status"

            rows = self.db.execute(
                text(
                    f"""
                    SELECT *
                    FROM forex_positions
                    WHERE {where}
                    ORDER BY
                        pair ASC,
                        opened_at ASC,
                        id ASC
                    """
                ),
                params,
            ).fetchall()

            return [
                self._position_from_row(row)
                for row in rows
            ]

        except Exception as exc:
            logger.warning(
                "Failed to list forex positions: %s",
                exc,
            )
            return []

    def refresh_positions(self, *, account_id: str) -> List[ForexPosition]:
        positions = self.list_positions(account_id=account_id, status="OPEN")
        refreshed: List[ForexPosition] = []

        if not positions:
            self.recalculate_account(account_id)
            return refreshed

        # ------------------------------------------------------------------
        # Batch, cache-aware quote fetch.
        #
        # This used to call self.forex_service.get_quote(position.pair)
        # once per position. ForexService.get_quote() tries
        # ForexQuoteAggregator first, which -- since the Phase 16A fix that
        # made it query real providers -- sequentially calls all five raw
        # FX provider modules (Polygon, Finnhub, AlphaVantage, TwelveData,
        # Yahoo) with no cache and no early exit on success, even when the
        # exact same pair's quote was already fetched and cached by the
        # provider router moments earlier in the same render. With N open
        # positions that meant up to 5*N sequential real network calls,
        # several of which hit a currently rate-limited or broken provider
        # (Polygon 429s, Finnhub JSONDecodeError) before falling through --
        # measured at ~4.9s for 3 positions, with each _persist_position()
        # commit inside the same loop adding further per-position DB
        # round trips on top of that.
        #
        # Fetching all position pairs in a single batched, cached, parallel
        # router call reuses whatever is already warm in the shared quote
        # cache and only makes real network calls for pairs that actually
        # need one, in parallel rather than serially. Positions are then
        # persisted with one commit for the whole batch instead of one
        # commit per position.
        from modules.forex.providers.forex_provider_router import (
            get_forex_quotes_from_router,
        )

        pairs = list(dict.fromkeys(position.pair for position in positions))
        try:
            quotes_by_pair = get_forex_quotes_from_router(pairs)
        except Exception as exc:
            logger.warning("Failed to batch-fetch forex quotes: %s", exc)
            quotes_by_pair = {}

        for position in positions:
            try:
                quote = quotes_by_pair.get(normalize_pair(position.pair)) or {}
                current_price = _safe_float(
                    quote.get("rate") or quote.get("mid") or quote.get("last")
                )

                if not current_price:
                    # No provider returned a usable rate for this pair right
                    # now -- keep the position's last known price rather
                    # than zeroing it out or fabricating one.
                    logger.warning(
                        "No usable live rate for %s; keeping last known price for position %s",
                        position.pair,
                        position.id,
                    )
                    refreshed.append(position)
                    continue

                position.current_price = current_price
                position.unrealized_pnl = self._calculate_position_pnl(
                    side=position.side,
                    units=position.units,
                    entry_price=position.avg_entry_price,
                    current_price=current_price,
                    base_currency=position.base_currency,
                    quote_currency=position.quote_currency,
                )
                position.notional_value = self._notional_in_account_currency(
                    position.units, current_price, position.base_currency, position.quote_currency
                )
                position.market_value = position.notional_value
                position.margin_required = position.notional_value / max(position.leverage, 1.0)
                position.updated_at = _utc_now()

                self._persist_position(position, commit=False)
                refreshed.append(position)

            except Exception as exc:
                logger.warning("Failed to refresh forex position %s: %s", position.id, exc)

        if self.db is not None and hasattr(self.db, "commit"):
            try:
                self.db.commit()
            except Exception as exc:
                logger.warning("Failed to commit refreshed forex positions: %s", exc)
                self._rollback_quietly()

        self.recalculate_account(account_id)
        return refreshed

    def recalculate_account(self, account_id: str) -> Optional[ForexPortfolioAccount]:
        account = self.get_account(account_id=account_id)
        if not account:
            return None

        positions = self.list_positions(account_id=account_id, status="OPEN")

        total_unrealized_pnl = sum(_safe_float(position.unrealized_pnl) for position in positions)
        total_margin = sum(_safe_float(position.margin_required) for position in positions)

        account.unrealized_pnl = total_unrealized_pnl
        account.equity = account.cash_balance + account.unrealized_pnl
        account.margin_used = total_margin
        account.margin_available = max(0.0, account.equity * account.leverage - account.margin_used)
        account.updated_at = _utc_now()

        self._persist_account(account)
        return account

    def get_snapshot(
        self,
        *,
        account_id: str,
        persist: bool = False,
        refresh: bool = True,
    ) -> Optional[ForexPortfolioSnapshot]:
        # ------------------------------------------------------------
        # Inner timing instrumentation.
        #
        # The outer get_terminal_snapshot() step timer showed this whole
        # method taking 12-24s while every other step (list_positions,
        # calculate_risk, build_var_summary, load_orders, ...) measured
        # in the tens/hundreds of ms -- meaning the cost is somewhere
        # INSIDE get_snapshot() itself, not in any already-instrumented
        # sibling step. Breaking this method's own body into marks lets
        # the next console capture point at the exact line instead of
        # guessing again.
        import time as _gs_time
        _gs_t0 = _gs_time.perf_counter()

        def _gs_mark(step_name: str, since: float) -> float:
            now = _gs_time.perf_counter()
            print(f"    [get_snapshot] {step_name}: {round((now - since) * 1000.0, 2)} ms")
            return now

        _gs_prev = _gs_t0

        if refresh:
            self.refresh_positions(account_id=account_id)
        _gs_prev = _gs_mark("inner_refresh_positions", _gs_prev)

        account = self.get_account(account_id=account_id)
        if not account:
            return None
        _gs_prev = _gs_mark("inner_get_account", _gs_prev)

        positions = self.list_positions(account_id=account_id, status="OPEN")
        position_rows = [position.to_dict() for position in positions]
        _gs_prev = _gs_mark("inner_list_positions", _gs_prev)

        total_notional = sum(_safe_float(position.notional_value) for position in positions)
        total_market_value = sum(_safe_float(position.market_value) for position in positions)
        total_unrealized_pnl = sum(_safe_float(position.unrealized_pnl) for position in positions)
        total_realized_pnl = _safe_float(account.realized_pnl)

        long_count = len([position for position in positions if position.side == "LONG"])
        short_count = len([position for position in positions if position.side == "SHORT"])

        exposure_pct = total_notional / account.equity if account.equity > 0 else 0.0

        risk = self.calculate_risk(
            account_id=account_id,
            account=account,
            positions=positions,
        )
        _gs_prev = _gs_mark("inner_calculate_risk", _gs_prev)

        print("ENTER get_snapshot")
        snapshot = ForexPortfolioSnapshot(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=account.portfolio_id,
            account_id=account.id,
            account_currency=account.account_currency,
            cash_balance=_round(account.cash_balance, 2),
            equity=_round(account.equity, 2),
            total_notional=_round(total_notional, 2),
            total_market_value=_round(total_market_value, 2),
            total_unrealized_pnl=_round(total_unrealized_pnl, 2),
            total_realized_pnl=_round(total_realized_pnl, 2),
            margin_used=_round(account.margin_used, 2),
            margin_available=_round(account.margin_available, 2),
            exposure_pct=_round(exposure_pct, 4),
            position_count=len(positions),
            long_count=long_count,
            short_count=short_count,
            risk_score=_round(risk.risk_score, 2),
            warnings=risk.warnings,
            asof=_utc_now(),
            positions=position_rows,
        )
        _gs_prev = _gs_mark("inner_build_dataclass", _gs_prev)
        print("ABOUT TO BUILD SNAPSHOT")
        if persist:
            self._persist_snapshot(snapshot)
        _gs_prev = _gs_mark("inner_persist_snapshot", _gs_prev)
        print("ENTER _persist_snapshot")
        print("PERSIST =", persist)
        print(f"    [get_snapshot] TOTAL: {round((_gs_time.perf_counter() - _gs_t0) * 1000.0, 2)} ms")
        return snapshot

    def _cached_liquidity_score(self, pair: str) -> float:
        """
        Liquidity estimate used by calculate_risk().

        This used to call forex_ai_engine.generate_signal(pair) -- the full
        28-pair alpha-model pipeline (live quote waterfall across every
        configured pair) -- purely to read one field off the result, then
        cache it with a TTL. That was architecturally backwards: alpha
        score measures trade opportunity, not market liquidity, so paying
        for a full alpha run was never actually necessary here. It also
        proved self-defeating twice over: whenever a render took longer
        than the cache TTL (which kept happening, since the expensive call
        was itself a big part of what made renders slow), the cache had
        already expired by the time the next render needed it, so every
        single click paid the full ~10-20s cost again.

        Liquidity in FX is driven by which currencies are involved, not by
        an alpha signal -- USD, EUR, GBP, and JPY are the four most-traded
        currencies globally (BIS Triennial Central Bank Survey), and pairs
        combining more of them trade on deeper, tighter-spread markets.
        That's a stable, well-established piece of market structure, not
        something that needs a live model re-run per click, so it's
        computed directly instead of cached/expired.
        """
        try:
            base, quote = split_pair(normalize_pair(pair))
        except Exception:
            return 70.0

        major_legs = sum(1 for c in (base, quote) if c in _MAJOR_FX_CURRENCIES)
        if major_legs >= 2:
            return 92.0
        if major_legs == 1:
            return 78.0
        return 60.0

    def calculate_risk(
        self,
        *,
        account_id: str,
        account: Optional[ForexPortfolioAccount] = None,
        positions: Optional[List[ForexPosition]] = None,
    ) -> ForexPortfolioRiskResult:
        account = account or self.get_account(account_id=account_id)

        if not account:
            raise ValueError(f"Forex account not found: {account_id}")

        positions = positions if positions is not None else self.list_positions(
            account_id=account_id,
            status="OPEN",
        )

        total_notional = sum(_safe_float(position.notional_value) for position in positions)
        exposure_pct = total_notional / account.equity if account.equity > 0 else 0.0

        largest_position_value = max(
            [_safe_float(position.notional_value) for position in positions] or [0.0]
        )
        largest_position_pct = (
            largest_position_value / total_notional if total_notional > 0 else 0.0
        )

        concentration_score = max(0.0, 100.0 - largest_position_pct * 100.0)
        leverage_used = total_notional / account.equity if account.equity > 0 else 0.0
        leverage_score = max(0.0, 100.0 - leverage_used * 8.0)

        liquidity_scores: List[float] = []
        for position in positions:
            liquidity_scores.append(self._cached_liquidity_score(position.pair))

        liquidity_score = (
            sum(liquidity_scores) / len(liquidity_scores) if liquidity_scores else 90.0
        )

        pnl_pct = account.unrealized_pnl / account.equity if account.equity else 0.0
        pnl_score = max(0.0, min(100.0, 70.0 + pnl_pct * 500.0))

        risk_score = (
            concentration_score * 0.25
            + leverage_score * 0.30
            + liquidity_score * 0.20
            + pnl_score * 0.25
        )

        warnings: List[str] = []

        if exposure_pct > DEFAULT_MAX_TOTAL_EXPOSURE_PCT:
            warnings.append("Total forex exposure exceeds preferred portfolio limit.")

        if largest_position_pct > DEFAULT_MAX_PAIR_EXPOSURE_PCT:
            warnings.append("Single pair concentration is elevated.")

        if account.margin_available <= 0:
            warnings.append("No margin available.")

        if account.unrealized_pnl < -(account.equity * 0.05):
            warnings.append("Unrealized drawdown exceeds 5% of equity.")

        return ForexPortfolioRiskResult(
            account_id=account.id,
            equity=_round(account.equity, 2),
            total_notional=_round(total_notional, 2),
            exposure_pct=_round(exposure_pct, 4),
            margin_used=_round(account.margin_used, 2),
            margin_available=_round(account.margin_available, 2),
            largest_position_pct=_round(largest_position_pct, 4),
            concentration_score=_round(concentration_score, 2),
            leverage_score=_round(leverage_score, 2),
            liquidity_score=_round(liquidity_score, 2),
            pnl_score=_round(pnl_score, 2),
            risk_score=_round(risk_score, 2),
            warnings=" ".join(warnings),
            asof=_utc_now(),
        )

    def _get_var_engine(self):
        """
        Returns a configured institutional Forex VaR engine.
        """

        from modules.forex.risk.forex_var_engine import (
            get_forex_var_engine,
        )

        return get_forex_var_engine(
            db=self.db,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
        )

    def _load_positions_into_var_engine(
            self,
            *,
            engine: Any,
            account: ForexPortfolioAccount,
            positions: List[ForexPosition],
    ) -> Any:
        """
        Replace the VaR engine's in-memory portfolio with the current live
        Forex account and open positions.

        This method does not query or persist data. It only maps the existing
        ForexPortfolioEngine models into the models required by ForexVaREngine.
        """

        from modules.forex.risk.forex_var_engine import (
            ForexRiskPosition,
            PositionDirection,
        )

        # ==========================================================
        # Reset the VaR engine's current live portfolio positions
        # ==========================================================

        portfolio = getattr(engine, "portfolio", None)

        if portfolio is None:
            raise RuntimeError(
                "Forex VaR engine does not have an initialized portfolio."
            )

        portfolio.positions.clear()

        # ==========================================================
        # Synchronize account-level values
        # ==========================================================

        portfolio.portfolio_id = (
                account.portfolio_id
                or self.portfolio_id
                or portfolio.portfolio_id
        )

        portfolio.tenant_id = self.tenant_id
        portfolio.user_id = self.user_id
        portfolio.account_currency = (
                account.account_currency
                or self.account_currency
        )

        portfolio.cash = _safe_float(account.cash_balance)
        portfolio.equity = _safe_float(account.equity)
        portfolio.buying_power = _safe_float(account.margin_available)
        portfolio.margin_used = _safe_float(account.margin_used)
        portfolio.margin_available = _safe_float(
            account.margin_available
        )

        # ==========================================================
        # Map live Forex positions into VaR risk positions
        # ==========================================================

        for position in positions or []:
            side = str(position.side or "").strip().upper()

            direction = (
                PositionDirection.SHORT
                if side in {"SHORT", "SELL"}
                else PositionDirection.LONG
            )

            symbol = normalize_pair(position.pair)

            risk_position = ForexRiskPosition(
                symbol=symbol,
                base_currency=str(
                    position.base_currency or ""
                ).upper(),
                quote_currency=str(
                    position.quote_currency or ""
                ).upper(),
                direction=direction,
                quantity=_safe_float(position.units),
                entry_price=_safe_float(
                    position.avg_entry_price
                ),
                current_price=_safe_float(
                    position.current_price
                ),
                market_value=abs(
                    _safe_float(position.market_value)
                ),
                notional_value=abs(
                    _safe_float(position.notional_value)
                ),
                unrealized_pnl=_safe_float(
                    position.unrealized_pnl
                ),
                realized_pnl=_safe_float(
                    position.realized_pnl
                ),
                leverage=_safe_float(
                    position.leverage,
                    account.leverage,
                ),
                metadata={
                    "position_id": position.id,
                    "account_id": position.account_id,
                    "portfolio_id": position.portfolio_id,
                    "status": position.status,
                    "margin_required": _safe_float(
                        position.margin_required
                    ),
                    "stop_price": position.stop_price,
                    "target_price": position.target_price,
                    "opened_at": (
                        position.opened_at.isoformat()
                        if isinstance(position.opened_at, datetime)
                        else str(position.opened_at or "")
                    ),
                },
            )

            engine.add_position(risk_position)

        # ==========================================================
        # Recalculate weights after all positions are loaded
        # ==========================================================

        portfolio.recalculate_weights()

        return engine

    def _build_var_summary(
            self,
            *,
            account: ForexPortfolioAccount,
            positions: List[ForexPosition],
    ) -> Dict[str, Any]:
        """
        Build the institutional risk packet used by the Trading Desk.

        Failures in the institutional VaR layer do not prevent the standard
        portfolio snapshot from rendering.
        """

        try:

            engine = self._get_var_engine()

            self._load_positions_into_var_engine(
                engine=engine,
                account=account,
                positions=positions,
            )

            portfolio_summary = engine.portfolio_summary()

            statistics_result = (
                engine.build_portfolio_statistics()
            )

            statistics = (
                statistics_result.to_dict()
                if hasattr(statistics_result, "to_dict")
                else dict(statistics_result or {})
            )

            parametric_result = (
                engine.calculate_parametric_var(
                    confidence=0.95,
                )
            )

            parametric_var = (
                parametric_result.to_dict()
                if hasattr(parametric_result, "to_dict")
                else dict(parametric_result or {})
            )

            expected_result = (
                engine.calculate_expected_shortfall(
                    confidence=0.95,
                )
            )

            expected_shortfall = (
                expected_result.to_dict()
                if hasattr(expected_result, "to_dict")
                else dict(expected_result or {})
            )

            result = {
                "status": "READY",
                "portfolio_summary": portfolio_summary,
                "statistics": statistics,
                "parametric_var": parametric_var,
                "expected_shortfall": expected_shortfall,

                #
                # Flatten the primary institutional risk metrics
                #
                "daily_var": _safe_float(
                    parametric_var.get("daily_var", 0.0)
                ),

                "daily_var_95": _safe_float(
                    parametric_var.get("daily_var", 0.0)
                ),

                "var_95": _safe_float(
                    parametric_var.get("daily_var", 0.0)
                ),

                "value_at_risk": _safe_float(
                    parametric_var.get("daily_var", 0.0)
                ),

                "expected_shortfall_value": _safe_float(
                    expected_shortfall.get(
                        "expected_shortfall",
                        0.0,
                    )
                ),

                "expected_shortfall_95": _safe_float(
                    expected_shortfall.get(
                        "expected_shortfall",
                        0.0,
                    )
                ),
                "gross_exposure": _safe_float(
                    portfolio_summary.get(
                        "gross_exposure",
                        0.0,
                    )
                ),
                "net_exposure": _safe_float(
                    portfolio_summary.get(
                        "net_exposure",
                        0.0,
                    )
                ),
                "directional": portfolio_summary.get(
                    "directional",
                    {},
                ),
                "currency_exposure": portfolio_summary.get(
                    "currency_exposure",
                    {},
                ),
                "effective_positions": _safe_float(
                    portfolio_summary.get(
                        "effective_positions",
                        0.0,
                    )
                ),
                "diversification_ratio": _safe_float(
                    portfolio_summary.get(
                        "diversification_ratio",
                        0.0,
                    )
                ),
                "generated_at": _utc_now().isoformat(),
            }

            print("=" * 80)
            print("INSTITUTIONAL VAR SUMMARY")
            print(
                "Positions :",
                len(positions or []),
            )
            print(
                "Gross     :",
                result["gross_exposure"],
            )
            print(
                "Net       :",
                result["net_exposure"],
            )
            print(
                "Directional:",
                result["directional"],
            )
            print(
                "Daily VaR :",
                parametric_var.get("daily_var", 0.0),
            )
            print(
                "Expected Shortfall:",
                expected_shortfall.get(
                    "expected_shortfall",
                    0.0,
                ),
            )
            print("=" * 80)

            return result

        except Exception as exc:

            logger.exception(
                "Failed to build institutional Forex VaR summary: %s",
                exc,
            )

            return {
                "status": "ERROR",
                "message": str(exc),
                "portfolio_summary": {},
                "statistics": {},
                "parametric_var": {},
                "expected_shortfall": {},
                "gross_exposure": 0.0,
                "net_exposure": 0.0,
                "directional": {
                    "long": 0.0,
                    "short": 0.0,
                    "net": 0.0,
                },
                "currency_exposure": {},
                "effective_positions": 0.0,
                "diversification_ratio": 0.0,
                "generated_at": _utc_now().isoformat(),
            }

    def _build_portfolio_allocation(
            self,
            *,
            account: ForexPortfolioAccount,
            positions: List[ForexPosition],
    ) -> List[Dict[str, Any]]:
        """
        Build portfolio allocation from live open positions.
        """

        total = sum(
            abs(_safe_float(p.market_value))
            for p in positions
        )

        allocation: List[Dict[str, Any]] = []

        if total <= 0:
            return allocation

        for position in positions:
            value = abs(
                _safe_float(position.market_value)
            )

            allocation.append({

                "pair": position.pair,

                "side": position.side,

                "units": position.units,

                "market_value": value,

                "notional": _safe_float(
                    position.notional_value
                ),

                "margin": _safe_float(
                    position.margin_required
                ),

                "weight": round(
                    value / total * 100.0,
                    2,
                ),

                "allocation_pct": round(
                    value / total * 100.0,
                    2,
                ),

                "unrealized_pnl": _safe_float(
                    position.unrealized_pnl
                ),

                "realized_pnl": _safe_float(
                    position.realized_pnl
                ),

                "entry_price": _safe_float(
                    position.avg_entry_price
                ),

                "current_price": _safe_float(
                    position.current_price
                ),

            })

        allocation.sort(
            key=lambda row: row["weight"],
            reverse=True,
        )

        return allocation

    def _build_performance_attribution(
            self,
            *,
            closed_positions: List[ForexPosition],
            execution_history: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Aggregate realized performance by currency pair.
        """

        attribution: Dict[str, Dict[str, Any]] = {}

        for position in closed_positions:

            pair = normalize_pair(position.pair)

            row = attribution.setdefault(
                pair,
                {
                    "pair": pair,
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "realized_pnl": 0.0,
                },
            )

            pnl = _safe_float(position.realized_pnl)

            row["trades"] += 1
            row["realized_pnl"] += pnl

            if pnl > 0:
                row["wins"] += 1
            elif pnl < 0:
                row["losses"] += 1

        results = []

        for row in attribution.values():
            trades = max(row["trades"], 1)

            row["win_rate"] = round(
                row["wins"] / trades * 100.0,
                2,
            )

            row["average_pnl"] = round(
                row["realized_pnl"] / trades,
                2,
            )

            results.append(row)

        results.sort(
            key=lambda r: r["realized_pnl"],
            reverse=True,
        )

        return results

    def position_size_from_risk(
        self,
        *,
        account_id: str,
        pair: str,
        entry_price: float,
        stop_price: float,
        risk_pct: float = DEFAULT_MAX_RISK_PER_TRADE_PCT,
    ) -> Dict[str, Any]:
        account = self.get_account(account_id=account_id)
        if not account:
            raise ValueError(f"Forex account not found: {account_id}")

        normalized_pair = normalize_pair(pair)
        entry = _safe_float(entry_price)
        stop = _safe_float(stop_price)

        if entry <= 0 or stop <= 0:
            raise ValueError("Entry and stop prices must be positive.")

        risk_per_unit = abs(entry - stop)
        if risk_per_unit <= 0:
            raise ValueError("Entry and stop prices cannot be the same.")

        max_risk_dollars = account.equity * _safe_float(risk_pct, DEFAULT_MAX_RISK_PER_TRADE_PCT)
        suggested_units = max_risk_dollars / risk_per_unit
        notional = suggested_units * entry

        max_notional = account.equity * account.leverage * DEFAULT_MAX_PAIR_EXPOSURE_PCT
        if notional > max_notional:
            suggested_units = max_notional / entry
            notional = max_notional

        margin_required = notional / max(account.leverage, 1.0)

        return {
            "account_id": account.id,
            "pair": normalized_pair,
            "entry_price": entry,
            "stop_price": stop,
            "risk_pct": _safe_float(risk_pct),
            "max_risk_dollars": _round(max_risk_dollars, 2),
            "suggested_units": _round(suggested_units, 2),
            "notional_value": _round(notional, 2),
            "margin_required": _round(margin_required, 2),
            "margin_available": _round(account.margin_available, 2),
            "is_affordable": margin_required <= account.margin_available,
        }

    def recommend_position_from_signal(
        self,
        *,
        account_id: str,
        pair: str,
        risk_pct: float = DEFAULT_MAX_RISK_PER_TRADE_PCT,
    ) -> Dict[str, Any]:
        signal = self.forex_ai_engine.generate_signal(pair, save=True)

        sizing = self.position_size_from_risk(
            account_id=account_id,
            pair=signal.pair,
            entry_price=signal.entry_price,
            stop_price=signal.stop_price,
            risk_pct=risk_pct,
        )

        side = "LONG"
        if signal.recommendation in {"SELL", "REDUCE"}:
            side = "SHORT"

        return {
            "signal": signal.to_dict(),
            "sizing": sizing,
            "recommended_side": side,
            "can_open_position": sizing.get("is_affordable", False)
            and signal.recommendation in {"STRONG_BUY", "BUY", "SELL"},
        }

    def _build_performance_history(
            self,
            *,
            account_id: str,
    ) -> Dict[str, Any]:
        """
        Build historical portfolio performance from persisted portfolio snapshots.

        Returns
        -------
        {
            "equity_curve": [
                {"date": "...", "equity": ...},
                ...
            ],
            "daily_pnl": [
                {"date": "...", "pnl": ...},
                ...
            ],
            "monthly_returns": [
                {"month": "2026-07", "return_pct": ...},
                ...
            ],
        }
        """

        if self.db is None:
            return {
                "equity_curve": [],
                "daily_pnl": [],
                "monthly_returns": [],
            }

        try:

            rows = self.db.execute(
                text(
                    """
                    SELECT
                        asof,
                        equity,
                        cash_balance,
                        total_realized_pnl,
                        total_unrealized_pnl
                    FROM forex_portfolio_snapshots
                    WHERE account_id = :account_id
                    ORDER BY asof ASC
                    """
                ),
                {
                    "account_id": account_id,
                },
            ).fetchall()

        except Exception as exc:

            logger.exception(
                "Failed loading portfolio performance history: %s",
                exc,
            )

            return {
                "equity_curve": [],
                "daily_pnl": [],
                "monthly_returns": [],
            }

        if not rows:
            return {
                "equity_curve": [],
                "daily_pnl": [],
                "monthly_returns": [],
            }

        # ==========================================================
        # Equity Curve
        # ==========================================================

        equity_curve: List[Dict[str, Any]] = []

        # ==========================================================
        # Daily P&L
        # ==========================================================

        daily_totals: Dict[str, float] = {}

        # ==========================================================
        # Monthly Returns
        # ==========================================================

        monthly_first: Dict[str, float] = {}
        monthly_last: Dict[str, float] = {}

        for row in rows:

            asof = _coerce_datetime(_row_get(row, "asof"))

            equity = _safe_float(
                _row_get(row, "equity")
            )

            realized = _safe_float(
                _row_get(row, "total_realized_pnl")
            )

            unrealized = _safe_float(
                _row_get(row, "total_unrealized_pnl")
            )

            total_pnl = realized + unrealized

            day_key = asof.strftime("%Y-%m-%d")

            month_key = asof.strftime("%Y-%m")

            # ----------------------------------------------------------
            # Equity Curve
            # ----------------------------------------------------------

            equity_curve.append(
                {
                    "date": asof,
                    "equity": equity,
                }
            )

            # ----------------------------------------------------------
            # Daily P&L
            #
            # Store the most recent P&L snapshot for each day.
            # ----------------------------------------------------------

            daily_totals[day_key] = total_pnl

            # ----------------------------------------------------------
            # Monthly Returns
            #
            # Capture the first and last equity value for each month.
            # ----------------------------------------------------------

            if month_key not in monthly_first:
                monthly_first[month_key] = equity

            monthly_last[month_key] = equity

        # ==========================================================
        # Build Daily P&L
        # ==========================================================

        daily_pnl = []

        for day in sorted(daily_totals.keys()):
            daily_pnl.append(
                {
                    "date": day,
                    "pnl": round(
                        daily_totals[day],
                        2,
                    ),
                }
            )

        # ==========================================================
        # Build Monthly Returns
        # ==========================================================

        monthly_returns = []

        for month in sorted(monthly_first.keys()):

            start_equity = monthly_first[month]

            end_equity = monthly_last[month]

            if start_equity > 0:

                pct = (
                              (
                                      end_equity
                                      - start_equity
                              )
                              / start_equity
                      ) * 100.0

            else:

                pct = 0.0

            monthly_returns.append(
                {
                    "month": month,
                    "return_pct": round(
                        pct,
                        2,
                    ),
                }
            )

        return {

            "equity_curve": equity_curve,

            "daily_pnl": daily_pnl,

            "monthly_returns": monthly_returns,

        }
        return {
            "equity_curve": equity_curve,
            "daily_pnl": daily_pnl,
            "monthly_returns": monthly_returns,
        }
    # ------------------------------------------------------------------
    # Terminal Snapshot / Institutional Analytics
    # ------------------------------------------------------------------

    def get_terminal_snapshot(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        persist: bool = False,
        refresh: bool = True,
        include_orders: bool = True,
        include_history: bool = True,
    ) -> ForexTerminalSnapshot:
        """
        Build a complete institutional terminal snapshot.

        The dashboard should consume this method instead of independently
        calculating account, portfolio, risk, position, order, or performance
        values.
        """
        # ------------------------------------------------------------
        # Step-by-step timing instrumentation.
        #
        # This method fans out into ~10 DB queries and computations
        # (position refresh/live quotes, risk, VaR, orders, execution
        # history across up to 4 tables, cash ledger, exposure, and
        # performance statistics). Users have reported the Institutional
        # Terminal's browser tab going unresponsive while this snapshot is
        # being built, with no visibility into which specific step is
        # slow. Logging a per-step elapsed_ms breakdown (matching the
        # existing "FOREX ALPHA DEBUG"-style convention used elsewhere in
        # this codebase) lets the next occurrence be diagnosed from the
        # console output instead of guessing.
        import time as _time
        _t0 = _time.perf_counter()
        _step_times: Dict[str, float] = {}

        def _mark(step_name: str, since: float) -> float:
            now = _time.perf_counter()
            _step_times[step_name] = round((now - since) * 1000.0, 2)
            return now

        _t_prev = _t0

        account = None

        if account_id:
            account = self.get_account(account_id=account_id)

        if account is None:
            account = self.get_or_create_account(
                portfolio_id=portfolio_id or self.portfolio_id,
            )
        _t_prev = _mark("resolve_account", _t_prev)

        if refresh:
            print("=" * 80)
            print("REFRESH POSITIONS")
            print("account:", account.id)
            print("=" * 80)
            self.refresh_positions(account_id=account.id)
            print("REFRESH COMPLETE")
            account = self.get_account(account_id=account.id) or account
        else:
            account = self.recalculate_account(account.id) or account
        _t_prev = _mark("recalculate_account", _t_prev)

        portfolio_snapshot = self.get_snapshot(
            account_id=account.id,
            persist=persist,
            refresh=False,
        )
        _t_prev = _mark("get_snapshot", _t_prev)

        positions = self.list_positions(
            account_id=account.id,
            status="OPEN",
        )
        closed_positions = self.list_positions(
            account_id=account.id,
            status="CLOSED",
        )
        _t_prev = _mark("list_positions", _t_prev)
        print("=" * 80)
        print("CLOSED POSITIONS")
        for p in closed_positions:
            print(
                p.id,
                p.status,
                p.units,
                p.pair,
            )
        print("=" * 80)
        position_rows = [position.to_dict() for position in positions]
        closed_position_rows = [position.to_dict() for position in closed_positions]

        risk_result = self.calculate_risk(
            account_id=account.id,
            account=account,
            positions=positions,
        )
        _t_prev = _mark("calculate_risk", _t_prev)

        institutional_risk = self._build_var_summary(
            account=account,
            positions=positions,
        )
        _t_prev = _mark("build_var_summary", _t_prev)

        open_orders = self.load_open_orders(
            account_id=account.id,
            portfolio_id=account.portfolio_id,
        ) if include_orders else []

        filled_orders = self.load_filled_orders(
            account_id=account.id,
            portfolio_id=account.portfolio_id,
        ) if include_orders else []
        _t_prev = _mark("load_orders", _t_prev)

        execution_history = self.load_execution_history(
            account_id=account.id,
            portfolio_id=account.portfolio_id,
        ) if include_history else []
        _t_prev = _mark("load_execution_history", _t_prev)

        cash_ledger = self.load_cash_ledger(
            account_id=account.id,
            limit=100,
        ) if include_history else []
        _t_prev = _mark("load_cash_ledger", _t_prev)

        currency_exposure = self.calculate_currency_exposure(
            positions=positions,
            account=account,
        )

        pair_exposure = self.calculate_pair_exposure(
            positions=positions,
            account=account,
        )
        _t_prev = _mark("exposure_calcs", _t_prev)

        performance = self.calculate_performance_statistics(
            account=account,
            positions=positions,
            closed_positions=closed_positions,
            filled_orders=filled_orders,
            execution_history=execution_history,
            cash_ledger=cash_ledger,
        )
        _t_prev = _mark("calculate_performance_statistics", _t_prev)

        margin = {
            "margin_used": _round(account.margin_used, 2),
            "margin_available": _round(account.margin_available, 2),
            "buying_power": _round(account.margin_available, 2),
            "leverage": _round(account.leverage, 2),
            "margin_utilization_pct": _round(
                (account.margin_used / max(account.equity * account.leverage, 1e-9)) * 100.0,
                4,
            ),
        }

        portfolio = portfolio_snapshot.to_dict() if portfolio_snapshot else {}

        allocation = self._build_portfolio_allocation(
            account=account,
            positions=positions,
        )

        performance_attribution = (
            self._build_performance_attribution(
                closed_positions=closed_positions,
                execution_history=execution_history,
            )
        )
        _t_prev = _mark("allocation_and_attribution", _t_prev)

        portfolio.update({
            "closed_positions": closed_position_rows,
            "open_orders": open_orders,
            "filled_orders": filled_orders,
            "execution_history": execution_history,
            "cash_ledger": cash_ledger,
            "currency_exposure": currency_exposure,
            "pair_exposure": pair_exposure,
            "performance": performance,
            "margin": margin,

            # Sprint 26 Phase 3A
            "institutional_risk": institutional_risk,
            "allocation": allocation,
            "performance_attribution": performance_attribution,
        })

        system = {
            "status": "READY",
            "source": "forex_portfolio_engine",
            "snapshot_type": "ForexTerminalSnapshot",
            "refresh": bool(refresh),
            "persist": bool(persist),
            "positions_live": len(position_rows) > 0,
            "orders_live": len(open_orders) > 0 or len(filled_orders) > 0,
            "cash_ledger_live": len(cash_ledger) > 0,
            "generated_at": _utc_now().isoformat(),
        }

        _total_ms = round((_time.perf_counter() - _t0) * 1000.0, 2)
        print("=" * 80)
        print(f"FOREX SNAPSHOT DEBUG | account={account.id} | portfolio={account.portfolio_id} | refresh={refresh}")
        for _step, _ms in _step_times.items():
            print(f"  {_step:32s} {_ms:>9.2f} ms")
        print(f"  {'TOTAL':32s} {_total_ms:>9.2f} ms")
        print("=" * 80)

        return ForexTerminalSnapshot(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=account.portfolio_id,
            account_id=account.id,
            generated_at=_utc_now(),
            account=account.to_dict(),
            portfolio=portfolio,
            positions=position_rows,
            open_orders=open_orders,
            filled_orders=filled_orders,
            execution_history=execution_history,
            cash_ledger=cash_ledger,
            currency_exposure=currency_exposure,
            pair_exposure=pair_exposure,
            risk=risk_result.to_dict(),
            performance=performance,
            margin=margin,
            system=system,
            raw={
                "portfolio_snapshot": (
                    portfolio_snapshot.to_dict()
                    if portfolio_snapshot
                    else None
                ),
                "risk": risk_result.to_dict(),
                "institutional_risk": institutional_risk,
            },
        )

    def calculate_currency_exposure(
        self,
        *,
        positions: Optional[List[ForexPosition]] = None,
        account: Optional[ForexPortfolioAccount] = None,
        account_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Calculate net, long, and short exposure by currency.

        For a LONG EUR/USD:
            +EUR base exposure
            -USD quote exposure
        For a SHORT EUR/USD:
            -EUR base exposure
            +USD quote exposure
        """
        if positions is None:
            if account is None and account_id:
                account = self.get_account(account_id=account_id)
            positions = self.list_positions(
                account_id=(account.id if account else account_id),
                status="OPEN",
            )
            print("=" * 80)
            print("OPEN POSITIONS")
            for p in positions:
                print(
                    p.id,
                    p.status,
                    p.units,
                    p.pair,
                )
            print("=" * 80)
        equity = _safe_float(account.equity if account else 0.0)
        exposures: Dict[str, Dict[str, float]] = {}

        def bucket(currency: str) -> Dict[str, float]:
            code = str(currency or "").upper()[:3]
            if code not in exposures:
                exposures[code] = {
                    "long_exposure": 0.0,
                    "short_exposure": 0.0,
                    "net_exposure": 0.0,
                    "gross_exposure": 0.0,
                }
            return exposures[code]

        for position in positions or []:
            base = str(position.base_currency or "").upper()[:3]
            quote = str(position.quote_currency or "").upper()[:3]
            side = str(position.side or "").upper()
            notional = abs(_safe_float(position.notional_value))

            if not base or not quote or notional <= 0:
                continue

            base_bucket = bucket(base)
            quote_bucket = bucket(quote)

            if side in {"LONG", "BUY"}:
                base_bucket["long_exposure"] += notional
                base_bucket["net_exposure"] += notional
                quote_bucket["short_exposure"] += notional
                quote_bucket["net_exposure"] -= notional
            else:
                base_bucket["short_exposure"] += notional
                base_bucket["net_exposure"] -= notional
                quote_bucket["long_exposure"] += notional
                quote_bucket["net_exposure"] += notional

            base_bucket["gross_exposure"] += notional
            quote_bucket["gross_exposure"] += notional

        rows: List[Dict[str, Any]] = []
        for currency, values in exposures.items():
            gross = _safe_float(values.get("gross_exposure"))
            net = _safe_float(values.get("net_exposure"))
            rows.append({
                "currency": currency,
                "long_exposure": _round(values.get("long_exposure"), 2),
                "short_exposure": _round(values.get("short_exposure"), 2),
                "net_exposure": _round(net, 2),
                "gross_exposure": _round(gross, 2),
                "net_exposure_pct": _round((net / equity) * 100.0, 4) if equity > 0 else 0.0,
                "gross_exposure_pct": _round((gross / equity) * 100.0, 4) if equity > 0 else 0.0,
                "bias": "LONG" if net > 0 else "SHORT" if net < 0 else "FLAT",
            })

        rows.sort(key=lambda row: abs(_safe_float(row.get("net_exposure"))), reverse=True)
        return rows

    def calculate_pair_exposure(
        self,
        *,
        positions: Optional[List[ForexPosition]] = None,
        account: Optional[ForexPortfolioAccount] = None,
        account_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Aggregate exposure by currency pair."""
        if positions is None:
            if account is None and account_id:
                account = self.get_account(account_id=account_id)
            positions = self.list_positions(
                account_id=(account.id if account else account_id),
                status="OPEN",
            )

        equity = _safe_float(account.equity if account else 0.0)
        pairs: Dict[str, Dict[str, Any]] = {}

        for position in positions or []:
            pair = normalize_pair(position.pair)
            side = str(position.side or "").upper()
            notional = abs(_safe_float(position.notional_value))
            pnl = _safe_float(position.unrealized_pnl)
            margin = _safe_float(position.margin_required)

            if pair not in pairs:
                pairs[pair] = {
                    "pair": pair,
                    "long_notional": 0.0,
                    "short_notional": 0.0,
                    "net_notional": 0.0,
                    "gross_notional": 0.0,
                    "unrealized_pnl": 0.0,
                    "margin_required": 0.0,
                    "position_count": 0,
                    "long_count": 0,
                    "short_count": 0,
                }

            row = pairs[pair]
            if side in {"LONG", "BUY"}:
                row["long_notional"] += notional
                row["net_notional"] += notional
                row["long_count"] += 1
            else:
                row["short_notional"] += notional
                row["net_notional"] -= notional
                row["short_count"] += 1

            row["gross_notional"] += notional
            row["unrealized_pnl"] += pnl
            row["margin_required"] += margin
            row["position_count"] += 1

        rows: List[Dict[str, Any]] = []
        for pair, values in pairs.items():
            net = _safe_float(values.get("net_notional"))
            gross = _safe_float(values.get("gross_notional"))
            rows.append({
                **values,
                "long_notional": _round(values.get("long_notional"), 2),
                "short_notional": _round(values.get("short_notional"), 2),
                "net_notional": _round(net, 2),
                "gross_notional": _round(gross, 2),
                "unrealized_pnl": _round(values.get("unrealized_pnl"), 2),
                "margin_required": _round(values.get("margin_required"), 2),
                "net_exposure_pct": _round((net / equity) * 100.0, 4) if equity > 0 else 0.0,
                "gross_exposure_pct": _round((gross / equity) * 100.0, 4) if equity > 0 else 0.0,
                "bias": "LONG" if net > 0 else "SHORT" if net < 0 else "FLAT",
            })

        rows.sort(key=lambda row: abs(_safe_float(row.get("net_notional"))), reverse=True)
        return rows

    def calculate_performance_statistics(
        self,
        *,
        account: Optional[ForexPortfolioAccount] = None,
        positions: Optional[List[ForexPosition]] = None,
        closed_positions: Optional[List[ForexPosition]] = None,
        filled_orders: Optional[List[Dict[str, Any]]] = None,
        execution_history: Optional[List[Dict[str, Any]]] = None,
        cash_ledger: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate terminal-level performance statistics.

        Uses realized P/L from closed positions, filled orders, executions, and
        cash ledger events where available. Falls back gracefully when no closed
        trade history exists.
        """
        positions = positions or []
        closed_positions = closed_positions or []
        filled_orders = filled_orders or []
        execution_history = execution_history or []
        cash_ledger = cash_ledger or []

        # ---------------------------------------------------------
        # Build historical performance series for dashboard charts
        # ---------------------------------------------------------

        history = {}

        if account is not None:

            try:

                history = self._build_performance_history(
                    account_id=account.id,
                )

            except Exception as exc:

                logger.warning(
                    "Failed to build performance history: %s",
                    exc,
                )

                history = {}

        realized_values: List[float] = []

        for position in closed_positions:
            realized_values.append(_safe_float(position.realized_pnl))

        for row in filled_orders + execution_history:
            if isinstance(row, dict):
                for key in ("realized_pnl", "pnl", "profit_loss", "net_pnl", "gross_pnl"):
                    if key in row and row.get(key) is not None:
                        realized_values.append(_safe_float(row.get(key)))
                        break

        for row in cash_ledger:
            if isinstance(row, dict) and str(row.get("event_type", "")).upper() in {
                "POSITION_CLOSED",
                "TRADE_CLOSED",
                "REALIZED_PNL",
                "ORDER_FILLED",
            }:
                realized_values.append(_safe_float(row.get("amount")))

        realized_values = [value for value in realized_values if abs(value) > 1e-12]
        wins = [value for value in realized_values if value > 0]
        losses = [value for value in realized_values if value < 0]

        total_realized = sum(realized_values)
        total_unrealized = sum(_safe_float(position.unrealized_pnl) for position in positions)
        total_pnl = total_realized + total_unrealized

        trade_count = len(realized_values)
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / trade_count * 100.0) if trade_count else 0.0

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

        average_win = gross_profit / win_count if win_count else 0.0
        average_loss = gross_loss / loss_count if loss_count else 0.0
        expectancy = (win_rate / 100.0) * average_win - (1.0 - win_rate / 100.0) * average_loss if trade_count else 0.0

        largest_win = max(wins) if wins else 0.0
        largest_loss = min(losses) if losses else 0.0

        equity = _safe_float(account.equity if account else 0.0)
        realized_return_pct = (total_realized / equity * 100.0) if equity > 0 else 0.0
        unrealized_return_pct = (total_unrealized / equity * 100.0) if equity > 0 else 0.0

        # Conservative placeholder based on observed trade P/L distribution.
        # If richer daily equity history is connected later, these can be
        # replaced by full time-series calculations.
        mean = sum(realized_values) / trade_count if trade_count else 0.0
        variance = (
            sum((value - mean) ** 2 for value in realized_values) / trade_count
            if trade_count
            else 0.0
        )
        stdev = math.sqrt(variance) if variance > 0 else 0.0
        sharpe = mean / stdev if stdev > 0 else 0.0

        downside = [value for value in realized_values if value < 0]
        downside_variance = (
            sum((value) ** 2 for value in downside) / len(downside)
            if downside
            else 0.0
        )
        downside_dev = math.sqrt(downside_variance) if downside_variance > 0 else 0.0
        sortino = mean / downside_dev if downside_dev > 0 else 0.0

        kelly = 0.0
        if average_win > 0 and average_loss > 0:
            win_prob = win_rate / 100.0
            loss_prob = 1.0 - win_prob
            payoff = average_win / average_loss
            kelly = win_prob - (loss_prob / payoff)
        print("=" * 80)
        print("PERFORMANCE HISTORY")
        print("Equity :", len(history.get("equity_curve", [])))
        print("Daily  :", len(history.get("daily_pnl", [])))
        print("Monthly:", len(history.get("monthly_returns", [])))
        print("=" * 80)
        return {
            "trade_count": trade_count,
            "open_position_count": len(positions),
            "closed_position_count": len(closed_positions),
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": _round(win_rate, 2),
            "gross_profit": _round(gross_profit, 2),
            "gross_loss": _round(gross_loss, 2),
            "profit_factor": _round(profit_factor, 4),
            "average_win": _round(average_win, 2),
            "average_loss": _round(average_loss, 2),
            "largest_win": _round(largest_win, 2),
            "largest_loss": _round(largest_loss, 2),
            "expectancy": _round(expectancy, 2),
            "total_realized_pnl": _round(total_realized, 2),
            "total_unrealized_pnl": _round(total_unrealized, 2),
            "total_pnl": _round(total_pnl, 2),
            "realized_return_pct": _round(realized_return_pct, 4),
            "unrealized_return_pct": _round(unrealized_return_pct, 4),
                        "sharpe": _round(sharpe, 4),
            "sortino": _round(sortino, 4),
            "kelly_fraction": _round(kelly, 4),

            # -----------------------------------------------------
            # Dashboard chart data
            # -----------------------------------------------------

            "equity_curve": history.get(
                "equity_curve",
                [],
            ),

            "daily_pnl": history.get(
                "daily_pnl",
                [],
            ),

            "monthly_returns": history.get(
                "monthly_returns",
                [],
            ),
        }


    def load_open_orders(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return self._load_orders(
            statuses=("open", "pending", "submitted", "new"),
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=limit,
        )

    def load_filled_orders(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return self._load_orders(
            statuses=("filled", "complete", "completed", "closed"),
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=limit,
        )

    def load_execution_history(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 250,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        tables = [
            "forex_fills",
            "forex_executions",
            "forex_execution_history",
            "forex_trade_orders",
        ]

        for table in tables:
            rows = self._load_table_rows(
                table=table,
                account_id=account_id,
                portfolio_id=portfolio_id,
                limit=limit,
                order_by_candidates=("filled_at", "executed_at", "created_at", "updated_at", "id"),
            )
            if rows:
                return rows

        return []

    def load_cash_ledger(
        self,
        *,
        account_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        try:
            #self.ensure_tables()

            params: Dict[str, Any] = {
                "tenant_id": self.tenant_id,
                "limit": int(limit),
            }
            where = "tenant_id = :tenant_id"

            if account_id:
                where += " AND account_id = :account_id"
                params["account_id"] = account_id

            rows = self.db.execute(text(
                f"""
                SELECT *
                FROM forex_cash_ledger
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT :limit
                """),
                params,
            ).fetchall()

            return [dict(row._mapping) for row in rows]

        except Exception as exc:
            logger.warning("Failed to load forex cash ledger: %s", exc)
            self._rollback_quietly()
            return []

    def _load_orders(
        self,
        *,
        statuses: Tuple[str, ...],
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        # Prefer the existing order management engine if available.
        try:
            from modules.forex.forex_order_management_engine import (
                get_forex_order_management_engine,
            )

            order_engine = get_forex_order_management_engine(db=self.db)
            if statuses and any(status in statuses for status in ("open", "pending", "submitted", "new")):
                rows = order_engine.open_orders(account_id=account_id, portfolio_id=portfolio_id)
            else:
                rows = order_engine.filled_orders(account_id=account_id, portfolio_id=portfolio_id)

            if rows:
                return self._filter_order_rows(
                    rows,
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                    limit=limit,
                )

        except Exception:
            pass

        tables = ["forex_trade_orders", "forex_orders"]
        rows: List[Dict[str, Any]] = []

        for table in tables:
            rows = self._load_table_rows(
                table=table,
                account_id=account_id,
                portfolio_id=portfolio_id,
                limit=limit,
                order_by_candidates=("created_at", "filled_at", "updated_at", "id"),
            )
            if rows:
                break

        wanted = {str(status).lower() for status in statuses}
        filtered = [
            row
            for row in rows
            if str(row.get("status", "")).lower() in wanted
        ]

        return filtered[: int(limit)]

    def _filter_order_rows(
        self,
        rows: List[Dict[str, Any]],
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []

        for row in rows:
            if not isinstance(row, dict):
                continue

            if account_id and row.get("account_id") and str(row.get("account_id")) != str(account_id):
                continue

            if portfolio_id and row.get("portfolio_id") and str(row.get("portfolio_id")) != str(portfolio_id):
                continue

            filtered.append(row)

        return filtered[: int(limit)]

    def _load_table_rows(
        self,
        *,
        table: str,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 100,
        order_by_candidates: Tuple[str, ...] = ("created_at", "updated_at", "id"),
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        try:
            columns = self._table_columns(table)
            if not columns:
                return []

            params: Dict[str, Any] = {"limit": int(limit)}
            where_parts: List[str] = []

            if "tenant_id" in columns:
                where_parts.append("tenant_id = :tenant_id")
                params["tenant_id"] = self.tenant_id

            if account_id and "account_id" in columns:
                where_parts.append("account_id = :account_id")
                params["account_id"] = account_id

            if portfolio_id and "portfolio_id" in columns:
                where_parts.append("portfolio_id = :portfolio_id")
                params["portfolio_id"] = portfolio_id

            where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

            order_col = next((col for col in order_by_candidates if col in columns), None)
            order_by = f"ORDER BY {order_col} DESC" if order_col else ""

            rows = self.db.execute(text(
                f"""
                SELECT *
                FROM {table}
                {where}
                {order_by}
                LIMIT :limit
                """),
                params,
            ).fetchall()

            return [dict(row._mapping) for row in rows]

        except Exception as exc:
            logger.warning("Failed to load rows from %s: %s", table, exc)
            self._rollback_quietly()
            return []

    def _table_columns(self, table: str) -> List[str]:
        if self.db is None:
            return []

        try:
            rows = self.db.execute(text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table
                """),
                {"table": table},
            ).fetchall()

            return [str(_row_get(row, "column_name")) for row in rows]

        except Exception:
            try:
                row = self.db.execute(text(f"SELECT * FROM {table} LIMIT 1")).fetchone()
                if row is None:
                    return []
                return list(dict(row._mapping).keys())
            except Exception:
                return []


    def _calculate_position_pnl(
        self,
        *,
        side: str,
        units: float,
        entry_price: float,
        current_price: float,
        base_currency: Optional[str] = None,
        quote_currency: Optional[str] = None,
    ) -> float:
        """
        (current_price - entry_price) * units is a PnL denominated in the
        pair's QUOTE currency. That only equals the account-currency PnL
        when quote_currency matches the account currency (EUR/USD, GBP/USD
        on a USD account). For pairs where the account currency is the BASE
        instead (USD/JPY, USD/CHF on a USD account), the same JPY/CHF-
        denominated PnL needs converting back to USD by dividing by the
        current price -- otherwise a real ~$14 move reads as ~-220 (JPY
        terms mistaken for USD). base_currency/quote_currency are optional
        for backwards compatibility with any other caller of this method;
        omitting them reproduces the old (quote-currency) behavior.
        """
        normalized_side = str(side or "").upper()
        if normalized_side == "SHORT":
            pnl = (entry_price - current_price) * units
        else:
            pnl = (current_price - entry_price) * units

        if not base_currency or not quote_currency:
            return pnl

        base = base_currency.upper()
        quote = quote_currency.upper()
        acct = self.account_currency

        if quote == acct:
            return pnl
        if base == acct and current_price:
            return pnl / current_price
        return pnl

    def _persist_account(self, account: ForexPortfolioAccount) -> None:
        if self.db is None:
            return

        try:
            #self.ensure_tables()

            self.db.execute(text(
                """
                INSERT INTO forex_accounts (
                    id,
                    tenant_id,
                    user_id,
                    portfolio_id,
                    account_name,
                    account_currency,
                    cash_balance,
                    realized_pnl,
                    unrealized_pnl,
                    equity,
                    margin_used,
                    margin_available,
                    leverage,
                    status,
                    raw_payload,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id,
                    :tenant_id,
                    :user_id,
                    :portfolio_id,
                    :account_name,
                    :account_currency,
                    :cash_balance,
                    :realized_pnl,
                    :unrealized_pnl,
                    :equity,
                    :margin_used,
                    :margin_available,
                    :leverage,
                    :status,
                    :raw_payload,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT (id)
                DO UPDATE SET
                    account_name = EXCLUDED.account_name,
                    account_currency = EXCLUDED.account_currency,
                    cash_balance = EXCLUDED.cash_balance,
                    realized_pnl = EXCLUDED.realized_pnl,
                    unrealized_pnl = EXCLUDED.unrealized_pnl,
                    equity = EXCLUDED.equity,
                    margin_used = EXCLUDED.margin_used,
                    margin_available = EXCLUDED.margin_available,
                    leverage = EXCLUDED.leverage,
                    status = EXCLUDED.status,
                    raw_payload = EXCLUDED.raw_payload,
                    updated_at = EXCLUDED.updated_at
                """),
                {
                    "id": account.id,
                    "tenant_id": account.tenant_id,
                    "user_id": account.user_id,
                    "portfolio_id": account.portfolio_id,
                    "account_name": account.account_name,
                    "account_currency": account.account_currency,
                    "cash_balance": account.cash_balance,
                    "realized_pnl": account.realized_pnl,
                    "unrealized_pnl": account.unrealized_pnl,
                    "equity": account.equity,
                    "margin_used": account.margin_used,
                    "margin_available": account.margin_available,
                    "leverage": account.leverage,
                    "status": account.status,
                    "raw_payload": _json_payload(account.to_dict()),
                    "created_at": account.created_at.replace(tzinfo=None),
                    "updated_at": account.updated_at.replace(tzinfo=None),
                },
            )

            if hasattr(self.db, "commit"):
                self.db.commit()

        except Exception as exc:
            logger.warning("Failed to persist forex account: %s", exc)
            self._rollback_quietly()

    def _persist_position(self, position: ForexPosition, *, commit: bool = True) -> None:
        if self.db is None:
            return

        try:
            #self.ensure_tables()

            self.db.execute(text(
                """
                INSERT INTO forex_positions (
                    id,
                    tenant_id,
                    user_id,
                    portfolio_id,
                    account_id,
                    pair,
                    base_currency,
                    quote_currency,
                    side,
                    units,
                    avg_entry_price,
                    current_price,
                    notional_value,
                    market_value,
                    unrealized_pnl,
                    realized_pnl,
                    stop_price,
                    target_price,
                    margin_required,
                    leverage,
                    status,
                    raw_payload,
                    opened_at,
                    updated_at
                )
                VALUES (
                    :id,
                    :tenant_id,
                    :user_id,
                    :portfolio_id,
                    :account_id,
                    :pair,
                    :base_currency,
                    :quote_currency,
                    :side,
                    :units,
                    :avg_entry_price,
                    :current_price,
                    :notional_value,
                    :market_value,
                    :unrealized_pnl,
                    :realized_pnl,
                    :stop_price,
                    :target_price,
                    :margin_required,
                    :leverage,
                    :status,
                    :raw_payload,
                    :opened_at,
                    :updated_at
                )
                ON CONFLICT (id)
                DO UPDATE SET
                    units = EXCLUDED.units,
                    current_price = EXCLUDED.current_price,
                    notional_value = EXCLUDED.notional_value,
                    market_value = EXCLUDED.market_value,
                    unrealized_pnl = EXCLUDED.unrealized_pnl,
                    realized_pnl = EXCLUDED.realized_pnl,
                    stop_price = EXCLUDED.stop_price,
                    target_price = EXCLUDED.target_price,
                    margin_required = EXCLUDED.margin_required,
                    leverage = EXCLUDED.leverage,
                    status = EXCLUDED.status,
                    raw_payload = EXCLUDED.raw_payload,
                    updated_at = EXCLUDED.updated_at
                """),
                {
                    "id": position.id,
                    "tenant_id": position.tenant_id,
                    "user_id": position.user_id,
                    "portfolio_id": position.portfolio_id,
                    "account_id": position.account_id,
                    "pair": position.pair,
                    "base_currency": position.base_currency,
                    "quote_currency": position.quote_currency,
                    "side": position.side,
                    "units": position.units,
                    "avg_entry_price": position.avg_entry_price,
                    "current_price": position.current_price,
                    "notional_value": position.notional_value,
                    "market_value": position.market_value,
                    "unrealized_pnl": position.unrealized_pnl,
                    "realized_pnl": position.realized_pnl,
                    "stop_price": position.stop_price,
                    "target_price": position.target_price,
                    "margin_required": position.margin_required,
                    "leverage": position.leverage,
                    "status": position.status,
                    "raw_payload": _json_payload(position.raw or position.to_dict()),
                    "opened_at": position.opened_at.replace(tzinfo=None),
                    "updated_at": position.updated_at.replace(tzinfo=None),
                },
            )

            if commit and hasattr(self.db, "commit"):
                self.db.commit()

        except Exception as exc:
            logger.warning("Failed to persist forex position: %s", exc)
            self._rollback_quietly()

    def _persist_snapshot(self, snapshot: ForexPortfolioSnapshot) -> None:

        #self.ensure_tables()
        print("ensure_tables() COMPLETE")
        try:
            #self.ensure_tables()

            self.db.execute(text(
                """
                INSERT INTO forex_portfolio_snapshots (
                    tenant_id,
                    user_id,
                    portfolio_id,
                    account_id,
                    account_currency,
                    cash_balance,
                    equity,
                    total_notional,
                    total_market_value,
                    total_unrealized_pnl,
                    total_realized_pnl,
                    margin_used,
                    margin_available,
                    exposure_pct,
                    position_count,
                    long_count,
                    short_count,
                    risk_score,
                    warnings,
                    payload,
                    asof
                )
                VALUES (
                    :tenant_id,
                    :user_id,
                    :portfolio_id,
                    :account_id,
                    :account_currency,
                    :cash_balance,
                    :equity,
                    :total_notional,
                    :total_market_value,
                    :total_unrealized_pnl,
                    :total_realized_pnl,
                    :margin_used,
                    :margin_available,
                    :exposure_pct,
                    :position_count,
                    :long_count,
                    :short_count,
                    :risk_score,
                    :warnings,
                    :payload,
                    :asof
                )
                """),
                {
                    "tenant_id": snapshot.tenant_id,
                    "user_id": snapshot.user_id,
                    "portfolio_id": snapshot.portfolio_id,
                    "account_id": snapshot.account_id,
                    "account_currency": snapshot.account_currency,
                    "cash_balance": snapshot.cash_balance,
                    "equity": snapshot.equity,
                    "total_notional": snapshot.total_notional,
                    "total_market_value": snapshot.total_market_value,
                    "total_unrealized_pnl": snapshot.total_unrealized_pnl,
                    "total_realized_pnl": snapshot.total_realized_pnl,
                    "margin_used": snapshot.margin_used,
                    "margin_available": snapshot.margin_available,
                    "exposure_pct": snapshot.exposure_pct,
                    "position_count": snapshot.position_count,
                    "long_count": snapshot.long_count,
                    "short_count": snapshot.short_count,
                    "risk_score": snapshot.risk_score,
                    "warnings": snapshot.warnings,
                    "payload": _json_payload(snapshot.to_dict()),
                    "asof": snapshot.asof.replace(tzinfo=None),
                },
            )
            print("INSERT COMPLETE")

            if hasattr(self.db, "commit"):
                self.db.commit()
                print("COMMIT COMPLETE")



        except Exception as exc:

            print("=" * 80)

            print("FOREX SNAPSHOT PERSIST FAILED")

            print(type(exc).__name__)

            print(str(exc))

            print("=" * 80)

            logger.exception(

                "Failed to persist forex portfolio snapshot"

            )

            self._rollback_quietly()

            raise

    def _record_cash_event(
        self,
        *,
        account_id: str,
        event_type: str,
        amount: float,
        currency: str,
        balance_after: float,
        notes: str,
        raw: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self.db is None:
            return

        try:
            #self.ensure_tables()

            self.db.execute(text(
                """
                INSERT INTO forex_cash_ledger (
                    tenant_id,
                    user_id,
                    portfolio_id,
                    account_id,
                    event_type,
                    amount,
                    currency,
                    balance_after,
                    notes,
                    raw_payload
                )
                VALUES (
                    :tenant_id,
                    :user_id,
                    :portfolio_id,
                    :account_id,
                    :event_type,
                    :amount,
                    :currency,
                    :balance_after,
                    :notes,
                    :raw_payload
                )
                """),
                {
                    "tenant_id": self.tenant_id,
                    "user_id": self.user_id,
                    "portfolio_id": self.portfolio_id,
                    "account_id": account_id,
                    "event_type": event_type,
                    "amount": amount,
                    "currency": currency,
                    "balance_after": balance_after,
                    "notes": notes,
                    "raw_payload": _json_payload(raw),
                },
            )

            if hasattr(self.db, "commit"):
                self.db.commit()

        except Exception as exc:
            logger.warning("Failed to record forex cash event: %s", exc)
            self._rollback_quietly()

    def _account_from_row(self, row: Any) -> ForexPortfolioAccount:
        created_at = _coerce_datetime(_row_get(row, "created_at"))
        updated_at = _coerce_datetime(_row_get(row, "updated_at"))

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        return ForexPortfolioAccount(
            id=str(_row_get(row, "id")),
            tenant_id=_row_get(row, "tenant_id"),
            user_id=_row_get(row, "user_id"),
            portfolio_id=_row_get(row, "portfolio_id"),
            account_name=_row_get(row, "account_name") or "Forex Account",
            account_currency=_row_get(row, "account_currency") or DEFAULT_ACCOUNT_CURRENCY,
            cash_balance=_safe_float(_row_get(row, "cash_balance")),
            realized_pnl=_safe_float(_row_get(row, "realized_pnl")),
            unrealized_pnl=_safe_float(_row_get(row, "unrealized_pnl")),
            equity=_safe_float(_row_get(row, "equity")),
            margin_used=_safe_float(_row_get(row, "margin_used")),
            margin_available=_safe_float(_row_get(row, "margin_available")),
            leverage=_safe_float(_row_get(row, "leverage"), 1.0),
            status=_row_get(row, "status") or "ACTIVE",
            created_at=created_at,
            updated_at=updated_at,
        )

    def _position_from_row(self, row: Any) -> ForexPosition:
        opened_at = _coerce_datetime(_row_get(row, "opened_at"))
        updated_at = _coerce_datetime(_row_get(row, "updated_at"))

        if opened_at.tzinfo is None:
            opened_at = opened_at.replace(tzinfo=timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        pair = normalize_pair(_row_get(row, "pair"))
        try:
            base_currency, quote_currency = split_pair(pair)
        except Exception:
            base_currency = _row_get(row, "base_currency") or ""
            quote_currency = _row_get(row, "quote_currency") or ""

        return ForexPosition(
            id=str(_row_get(row, "id")),
            tenant_id=_row_get(row, "tenant_id"),
            user_id=_row_get(row, "user_id"),
            portfolio_id=_row_get(row, "portfolio_id"),
            account_id=str(_row_get(row, "account_id")),
            pair=pair,
            base_currency=_row_get(row, "base_currency") or base_currency,
            quote_currency=_row_get(row, "quote_currency") or quote_currency,
            side=str(_row_get(row, "side") or "LONG").upper(),
            units=_safe_float(_row_get(row, "units")),
            avg_entry_price=_safe_float(_row_get(row, "avg_entry_price")),
            current_price=_safe_float(_row_get(row, "current_price")),
            notional_value=_safe_float(_row_get(row, "notional_value")),
            market_value=_safe_float(_row_get(row, "market_value")),
            unrealized_pnl=_safe_float(_row_get(row, "unrealized_pnl")),
            realized_pnl=_safe_float(_row_get(row, "realized_pnl")),
            stop_price=_row_get(row, "stop_price"),
            target_price=_row_get(row, "target_price"),
            margin_required=_safe_float(_row_get(row, "margin_required")),
            leverage=_safe_float(_row_get(row, "leverage"), 1.0),
            status=_row_get(row, "status") or "OPEN",
            opened_at=opened_at,
            updated_at=updated_at,
            raw=_row_get(row, "raw_payload"),
        )

    def _rollback_quietly(self) -> None:
        try:
            if self.db is not None and hasattr(self.db, "rollback"):
                self.db.rollback()
        except Exception:
            pass


def get_forex_portfolio_engine(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    forex_service: Optional[ForexService] = None,
    forex_ai_engine: Optional[ForexAIEngine] = None,
    account_currency: str = DEFAULT_ACCOUNT_CURRENCY,
) -> ForexPortfolioEngine:
    return ForexPortfolioEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
        forex_service=forex_service,
        forex_ai_engine=forex_ai_engine,
        account_currency=account_currency,
    )


def get_forex_terminal_snapshot(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    account_id: Optional[str] = None,
    db: Any = None,
    persist: bool = False,
    refresh: bool = True,
    include_orders: bool = True,
    include_history: bool = True,
) -> Dict[str, Any]:
    engine = get_forex_portfolio_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    return engine.get_terminal_snapshot(
        account_id=account_id,
        portfolio_id=portfolio_id,
        persist=persist,
        refresh=refresh,
        include_orders=include_orders,
        include_history=include_history,
    ).to_dict()


def create_forex_account(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    account_name: str = "Forex Paper Account",
    starting_cash: float = DEFAULT_STARTING_CASH,
    leverage: float = 10.0,
) -> Dict[str, Any]:
    engine = get_forex_portfolio_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    return engine.create_account(
        account_name=account_name,
        starting_cash=starting_cash,
        leverage=leverage,
        portfolio_id=portfolio_id,
    ).to_dict()


def get_forex_portfolio_snapshot(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    account_id: str,
    db: Any = None,
    persist: bool = False,
    refresh: bool = True,
) -> Optional[Dict[str, Any]]:
    engine = get_forex_portfolio_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    snapshot = engine.get_snapshot(
        account_id=account_id,
        persist=persist,
        refresh=refresh,
    )
    return snapshot.to_dict() if snapshot else None


def open_forex_position(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    account_id: str,
    pair: str,
    side: str,
    units: float,
    entry_price: Optional[float] = None,
    stop_price: Optional[float] = None,
    target_price: Optional[float] = None,
    leverage: Optional[float] = None,
) -> Dict[str, Any]:
    engine = get_forex_portfolio_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    print("=" * 80)
    print("ENTER open_position")
    print("account_id param  :", account_id)
    print("=" * 80)
    return engine.open_position(
        account_id=account_id,
        pair=pair,
        side=side,
        units=units,
        entry_price=entry_price,
        stop_price=stop_price,
        target_price=target_price,
        leverage=leverage,
    ).to_dict()


def close_forex_position(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    position_id: str,
    close_price: Optional[float] = None,
    close_units: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    engine = get_forex_portfolio_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    position = engine.close_position(
        position_id=position_id,
        close_price=close_price,
        close_units=close_units,
    )
    return position.to_dict() if position else None