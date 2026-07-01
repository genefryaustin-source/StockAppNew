# modules/forex/forex_portfolio_engine.py

from __future__ import annotations
from psycopg2.extras import Json
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


def _json_payload(value):
    if value is None:
        return None

    return Json(value)


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return getattr(row, key)
    except Exception:
        return default


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

    def ensure_tables(self) -> None:
        if self.db is None:
            return

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
            """
            CREATE TABLE IF NOT EXISTS forex_cash_ledger (
                id SERIAL PRIMARY KEY,
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
            """
            CREATE TABLE IF NOT EXISTS forex_portfolio_snapshots (
                id SERIAL PRIMARY KEY,
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
            self.ensure_tables()

            params: Dict[str, Any] = {"tenant_id": self.tenant_id}
            where = "tenant_id = :tenant_id"

            if account_id:
                where += " AND id = :account_id"
                params["account_id"] = account_id
            else:
                where += " AND portfolio_id = :portfolio_id"
                params["portfolio_id"] = portfolio_id or self.portfolio_id

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
        price = _safe_float(entry_price, quote.price)
        if price <= 0:
            raise ValueError("Entry price must be positive.")

        effective_leverage = _safe_float(leverage, account.leverage)
        notional_value = position_units * price
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
        self.recalculate_account(account.id)
        return position

    def close_position(
        self,
        *,
        position_id: str,
        close_price: Optional[float] = None,
        close_units: Optional[float] = None,
        notes: str = "Position closed.",
    ) -> Optional[ForexPosition]:
        position = self.get_position(position_id=position_id)
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
        )

        position.realized_pnl += pnl
        position.units -= units_to_close
        position.current_price = exit_price
        position.updated_at = _utc_now()

        if position.units <= 0.0000001:
            position.units = 0.0
            position.status = "CLOSED"
            position.unrealized_pnl = 0.0
            position.market_value = 0.0
            position.notional_value = 0.0
            position.margin_required = 0.0
        else:
            position.notional_value = position.units * exit_price
            position.market_value = position.notional_value
            position.unrealized_pnl = self._calculate_position_pnl(
                side=position.side,
                units=position.units,
                entry_price=position.avg_entry_price,
                current_price=exit_price,
            )
            position.margin_required = position.notional_value / max(position.leverage, 1.0)

        self._persist_position(position)

        account = self.get_account(account_id=position.account_id)
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
            self.recalculate_account(account.id)

        return position

    def get_position(
        self,
        *,
        position_id: str,
    ) -> Optional[ForexPosition]:
        if self.db is None:
            return None

        try:
            self.ensure_tables()

            row = self.db.execute(text(
                """
                SELECT *
                FROM forex_positions
                WHERE tenant_id = :tenant_id
                  AND id = :position_id
                LIMIT 1
                """),
                {
                    "tenant_id": self.tenant_id,
                    "position_id": position_id,
                },
            ).fetchone()

            if not row:
                return None

            return self._position_from_row(row)

        except Exception as exc:
            logger.warning("Failed to get forex position: %s", exc)
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
            self.ensure_tables()

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

            rows = self.db.execute(text(
                f"""
                SELECT *
                FROM forex_positions
                WHERE {where}
                ORDER BY updated_at DESC
                """),
                params,
            ).fetchall()

            return [self._position_from_row(row) for row in rows]

        except Exception as exc:
            logger.warning("Failed to list forex positions: %s", exc)
            return []

    def refresh_positions(self, *, account_id: str) -> List[ForexPosition]:
        positions = self.list_positions(account_id=account_id, status="OPEN")
        refreshed: List[ForexPosition] = []

        for position in positions:
            try:
                quote = self.forex_service.get_quote(position.pair)
                current_price = _safe_float(quote.price)

                position.current_price = current_price
                position.unrealized_pnl = self._calculate_position_pnl(
                    side=position.side,
                    units=position.units,
                    entry_price=position.avg_entry_price,
                    current_price=current_price,
                )
                position.notional_value = position.units * current_price
                position.market_value = position.notional_value
                position.margin_required = position.notional_value / max(position.leverage, 1.0)
                position.updated_at = _utc_now()

                self._persist_position(position)
                refreshed.append(position)

            except Exception as exc:
                logger.warning("Failed to refresh forex position %s: %s", position.id, exc)

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
        persist: bool = True,
        refresh: bool = True,
    ) -> Optional[ForexPortfolioSnapshot]:
        if refresh:
            self.refresh_positions(account_id=account_id)

        account = self.get_account(account_id=account_id)
        if not account:
            return None

        positions = self.list_positions(account_id=account_id, status="OPEN")
        position_rows = [position.to_dict() for position in positions]

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
        print("ABOUT TO BUILD SNAPSHOT")
        if persist:
            self._persist_snapshot(snapshot)
        print("ENTER _persist_snapshot")
        print("PERSIST =", persist)
        return snapshot

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
            try:
                signal = self.forex_ai_engine.generate_signal(position.pair, save=False)
                liquidity_scores.append(_safe_float(signal.liquidity_score, 70.0))
            except Exception:
                liquidity_scores.append(70.0)

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

    # ------------------------------------------------------------------
    # Terminal Snapshot / Institutional Analytics
    # ------------------------------------------------------------------

    def get_terminal_snapshot(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        persist: bool = True,
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
        account = None

        if account_id:
            account = self.get_account(account_id=account_id)

        if account is None:
            account = self.get_or_create_account(
                portfolio_id=portfolio_id or self.portfolio_id,
            )

        if refresh:
            self.refresh_positions(account_id=account.id)

        account = self.recalculate_account(account.id) or account

        portfolio_snapshot = self.get_snapshot(
            account_id=account.id,
            persist=persist,
            refresh=False,
        )

        positions = self.list_positions(
            account_id=account.id,
            status="OPEN",
        )
        closed_positions = self.list_positions(
            account_id=account.id,
            status="CLOSED",
        )

        position_rows = [position.to_dict() for position in positions]
        closed_position_rows = [position.to_dict() for position in closed_positions]

        risk_result = self.calculate_risk(
            account_id=account.id,
            account=account,
            positions=positions,
        )

        open_orders = self.load_open_orders(
            account_id=account.id,
            portfolio_id=account.portfolio_id,
        ) if include_orders else []

        filled_orders = self.load_filled_orders(
            account_id=account.id,
            portfolio_id=account.portfolio_id,
        ) if include_orders else []

        execution_history = self.load_execution_history(
            account_id=account.id,
            portfolio_id=account.portfolio_id,
        ) if include_history else []

        cash_ledger = self.load_cash_ledger(
            account_id=account.id,
            limit=100,
        ) if include_history else []

        currency_exposure = self.calculate_currency_exposure(
            positions=positions,
            account=account,
        )

        pair_exposure = self.calculate_pair_exposure(
            positions=positions,
            account=account,
        )

        performance = self.calculate_performance_statistics(
            account=account,
            positions=positions,
            closed_positions=closed_positions,
            filled_orders=filled_orders,
            execution_history=execution_history,
            cash_ledger=cash_ledger,
        )

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
                "portfolio_snapshot": portfolio_snapshot.to_dict() if portfolio_snapshot else None,
                "risk": risk_result.to_dict(),
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
            self.ensure_tables()

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
                rows = order_engine.open_orders()
            else:
                rows = order_engine.filled_orders()

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
    ) -> float:
        normalized_side = str(side or "").upper()
        if normalized_side == "SHORT":
            return (entry_price - current_price) * units
        return (current_price - entry_price) * units

    def _persist_account(self, account: ForexPortfolioAccount) -> None:
        if self.db is None:
            return

        try:
            self.ensure_tables()

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

    def _persist_position(self, position: ForexPosition) -> None:
        if self.db is None:
            return

        try:
            self.ensure_tables()

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

            if hasattr(self.db, "commit"):
                self.db.commit()

        except Exception as exc:
            logger.warning("Failed to persist forex position: %s", exc)
            self._rollback_quietly()

    def _persist_snapshot(self, snapshot: ForexPortfolioSnapshot) -> None:
        print("=" * 80)
        print("ENTER _persist_snapshot")

        if self.db is None:
            return
        print("CALLING ensure_tables()")
        self.ensure_tables()
        print("ensure_tables() COMPLETE")
        try:
            self.ensure_tables()
            print("=" * 80)
            print("SNAPSHOT INSERT")
            print("tenant    :", snapshot.tenant_id)
            print("user      :", snapshot.user_id)
            print("portfolio :", snapshot.portfolio_id)
            print("account   :", snapshot.account_id)
            print("asof      :", snapshot.asof)
            print("=" * 80)
            print("EXECUTING INSERT")
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
            self.ensure_tables()

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
        created_at = _row_get(row, "created_at") or _utc_now()
        updated_at = _row_get(row, "updated_at") or _utc_now()

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
        opened_at = _row_get(row, "opened_at") or _utc_now()
        updated_at = _row_get(row, "updated_at") or _utc_now()

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
    persist: bool = True,
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
    persist: bool = True,
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