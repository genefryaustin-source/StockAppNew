"""
modules/forex/forex_terminal_execution_service.py

Phase 4 — Dashboard Auto-Refresh + Trade Validation.

This service validates terminal paper orders before execution and returns a
snapshot payload that the dashboard can immediately consume.

Adds:
- structured order validation
- margin pre-checks
- bad pair / size checks
- last execution payload
- execution verification helper
- updated ForexTerminalSnapshot after order submit
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

try:
    from sqlalchemy import text
except Exception:
    text = None


MAJOR_CURRENCIES = {"USD", "EUR", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _naive_now() -> datetime:
    return _utc_now().replace(tzinfo=None)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            cleaned = value.replace("$", "").replace(",", "").replace("%", "").strip()
            if cleaned in {"", "-", "—", "None"}:
                return default
            return float(cleaned)
        return float(value)
    except Exception:
        return default


def _normalize_pair(pair: Any) -> str:
    value = str(pair or "").replace("-", "/").replace("_", "/").upper().strip()
    if "/" not in value and len(value) == 6:
        value = f"{value[:3]}/{value[3:]}"
    return value


def _compact_pair(pair: Any) -> str:
    return _normalize_pair(pair).replace("/", "")


def _normalize_side(side: Any) -> str:
    value = str(side or "BUY").upper().strip()
    if value in {"LONG"}:
        return "BUY"
    if value in {"SHORT"}:
        return "SELL"
    return "SELL" if value in {"SELL", "S"} else "BUY"


def _now_iso() -> str:
    return _utc_now().isoformat()


class ForexTerminalExecutionService:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_order(
        self,
        *,
        pair: str,
        side: str,
        units: Optional[float] = None,
        qty: Optional[float] = None,
        lots: Optional[float] = None,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        account_id: Optional[str] = None,
        leverage: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        errors: List[str] = []
        warnings: List[str] = []

        if self.db is None:
            errors.append("Database session is required.")

        pair_norm = _normalize_pair(pair)
        compact = _compact_pair(pair_norm)

        if len(compact) != 6:
            errors.append(f"Invalid Forex pair '{pair}'. Expected format like EUR/USD or EURUSD.")
            base = quote = ""
        else:
            base, quote = compact[:3], compact[3:]
            if base not in MAJOR_CURRENCIES:
                warnings.append(f"Base currency '{base}' is not in the configured major currency list.")
            if quote not in MAJOR_CURRENCIES:
                warnings.append(f"Quote currency '{quote}' is not in the configured major currency list.")
            if base == quote:
                errors.append("Base and quote currency cannot be the same.")

        side_norm = _normalize_side(side)
        if side_norm not in {"BUY", "SELL"}:
            errors.append("Side must be BUY or SELL.")

        order_units = self._resolve_units(units=units, qty=qty, lots=lots)
        if order_units <= 0:
            errors.append("Order units must be greater than zero.")
        if order_units > 100000000:
            warnings.append("Order size is unusually large for paper validation.")

        order_type_norm = str(order_type or "MARKET").upper().strip()
        if order_type_norm not in {"MARKET", "MKT", "LIMIT", "STOP", "STOP_LIMIT", "TRAILING_STOP"}:
            errors.append(f"Unsupported order type '{order_type}'.")

        if order_type_norm in {"LIMIT", "STOP_LIMIT"} and _safe_float(limit_price) <= 0:
            errors.append("Limit orders require a positive limit price.")

        if order_type_norm in {"STOP", "STOP_LIMIT"} and _safe_float(stop_price) <= 0:
            errors.append("Stop orders require a positive stop price.")

        account_payload: Dict[str, Any] = {}
        margin_payload: Dict[str, Any] = {}
        estimated_margin = 0.0

        if self.db is not None and not errors:
            try:
                engine = self._portfolio_engine(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    portfolio_id=portfolio_id,
                )
                account = engine.get_account(account_id=account_id) if account_id else None
                if account is None:
                    account = engine.get_or_create_account(portfolio_id=portfolio_id)

                account_payload = account.to_dict() if hasattr(account, "to_dict") else {}
                account_leverage = _safe_float(leverage or getattr(account, "leverage", 50) or 50, 50)
                notional = order_units
                estimated_margin = notional / max(account_leverage, 1.0)
                margin_available = _safe_float(
                    getattr(account, "margin_available", None)
                    or account_payload.get("margin_available")
                    or account_payload.get("equity")
                )

                margin_payload = {
                    "notional": notional,
                    "leverage": account_leverage,
                    "estimated_margin_required": estimated_margin,
                    "margin_available": margin_available,
                    "margin_ok": margin_available >= estimated_margin,
                }

                if margin_available < estimated_margin:
                    errors.append(
                        f"Insufficient margin. Required ${estimated_margin:,.2f}, available ${margin_available:,.2f}."
                    )

            except Exception as exc:
                errors.append(f"Account validation failed: {exc}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "pair": pair_norm,
            "symbol": compact,
            "base_currency": compact[:3] if len(compact) == 6 else "",
            "quote_currency": compact[3:] if len(compact) == 6 else "",
            "side": side_norm,
            "order_type": order_type_norm,
            "units": order_units,
            "lots": order_units / 100000.0 if order_units else 0.0,
            "account": account_payload,
            "margin": margin_payload,
            "checked_at": _now_iso(),
        }

    def submit_order(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Phase 12 broker-routed submit.

        Paper remains the default. Non-paper brokers route through the broker
        abstraction layer. Live adapters are safety-locked by their configs.
        """
        broker = str(kwargs.get("broker") or "paper").lower()

        # Paper orders use the local validated execution path to avoid router
        # recursion through ForexPaperBroker -> execution service.
        if broker in {"paper", "sim", "simulation"}:
            return self._submit_order_internal(**kwargs)

        try:
            from modules.forex.forex_broker_router import get_forex_broker_router
            routed = get_forex_broker_router(db=self.db, default_broker="paper").route_order(**kwargs)
            if isinstance(routed, dict):
                routed.setdefault("broker_routed", True)
                routed.setdefault("broker", broker)
            return routed
        except Exception as exc:
            return {
                "status": "ERROR",
                "message": "Broker routing failed.",
                "broker": broker,
                "error": str(exc),
            }

    def _submit_order_internal(self, **kwargs: Any) -> Dict[str, Any]:
        validation = self.validate_order(**kwargs)

        if not validation["valid"]:
            return {
                "status": "REJECTED",
                "message": "Order validation failed.",
                "validation": validation,
                "timestamp": _now_iso(),
            }

        order_type_norm = validation["order_type"]
        pair_norm = validation["pair"]
        side_norm = validation["side"]
        order_units = validation["units"]

        tenant_id = kwargs.get("tenant_id")
        user_id = kwargs.get("user_id")
        portfolio_id = kwargs.get("portfolio_id")
        account_id = kwargs.get("account_id")
        broker = kwargs.get("broker") or "paper"

        engine = self._portfolio_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

        account = engine.get_account(account_id=account_id) if account_id else None
        if account is None:
            account = engine.get_or_create_account(portfolio_id=portfolio_id)

        broker_order_id = kwargs.get("broker_order_id") or f"FXP-{uuid.uuid4().hex[:12].upper()}"

        if order_type_norm in {"MARKET", "MKT"}:
            result = self._execute_market_order(
                engine=engine,
                account=account,
                broker_order_id=broker_order_id,
                pair=pair_norm,
                side=side_norm,
                units=order_units,
                requested_price=(
                    _safe_float(kwargs.get("limit_price"))
                    or _safe_float(kwargs.get("price"))
                    or _safe_float(kwargs.get("entry_price"))
                    or None
                ),
                stop_price=kwargs.get("stop_price"),
                target_price=kwargs.get("target_price") if kwargs.get("target_price") is not None else kwargs.get("take_profit"),
                leverage=kwargs.get("leverage"),
                broker=broker,
                raw=kwargs,
                validation=validation,
            )
        else:
            result = self._persist_open_order(
                engine=engine,
                account=account,
                broker_order_id=broker_order_id,
                pair=pair_norm,
                side=side_norm,
                units=order_units,
                order_type=order_type_norm,
                limit_price=kwargs.get("limit_price"),
                stop_price=kwargs.get("stop_price"),
                target_price=kwargs.get("target_price") if kwargs.get("target_price") is not None else kwargs.get("take_profit"),
                risk_pct=kwargs.get("risk_pct"),
                broker=broker,
                raw=kwargs,
                validation=validation,
            )

        result["validation"] = validation
        result["verification"] = self.verify_execution(
            broker_order_id=result.get("broker_order_id"),
            position_id=result.get("position_id"),
            account_id=result.get("account_id"),
            portfolio_id=result.get("portfolio_id"),
        )
        return result

    def verify_execution(
        self,
        *,
        broker_order_id: Optional[str] = None,
        position_id: Optional[str] = None,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self.db is None or text is None:
            return {"verified": False, "checks": {"db": False}, "errors": ["Database unavailable."]}

        checks = {
            "db": True,
            "order_row": False,
            "position_row": False,
            "account_snapshot": False,
            "terminal_snapshot": False,
        }
        errors: List[str] = []

        try:
            self.ensure_order_tables()

            if broker_order_id:
                row = self.db.execute(
                    text("""
                        SELECT *
                        FROM forex_trade_orders
                        WHERE broker_order_id = :broker_order_id
                        LIMIT 1
                    """),
                    {"broker_order_id": broker_order_id},
                ).fetchone()
                checks["order_row"] = row is not None

            if position_id:
                try:
                    row = self.db.execute(
                        text("SELECT * FROM forex_positions WHERE id = :position_id LIMIT 1"),
                        {"position_id": position_id},
                    ).fetchone()
                    checks["position_row"] = row is not None
                except Exception:
                    # Some engine versions use different schemas; snapshot check below is still authoritative.
                    checks["position_row"] = False

            if account_id:
                engine = self._portfolio_engine(tenant_id=None, user_id=None, portfolio_id=portfolio_id)
                account = engine.get_account(account_id=account_id)
                checks["account_snapshot"] = account is not None
                snap = engine.get_terminal_snapshot(
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                    refresh=True,
                    persist=True,
                    include_orders=True,
                    include_history=True,
                )
                snap_dict = snap.to_dict() if hasattr(snap, "to_dict") else snap
                checks["terminal_snapshot"] = isinstance(snap_dict, dict) and bool(snap_dict.get("account"))

        except Exception as exc:
            errors.append(str(exc))

        return {
            "verified": all(checks.values()) and not errors,
            "checks": checks,
            "errors": errors,
            "verified_at": _now_iso(),
        }

    def cancel_order(self, broker_order_id: str, broker: str = "paper") -> Dict[str, Any]:
        broker_name = str(broker or "paper").lower()
        if broker_name not in {"paper", "sim", "simulation"}:
            try:
                from modules.forex.forex_broker_router import get_forex_broker_router
                return get_forex_broker_router(db=self.db).cancel_order(broker_order_id, broker=broker_name)
            except Exception as exc:
                return {"status": "ERROR", "broker": broker_name, "broker_order_id": broker_order_id, "error": str(exc)}

        if self.db is None or text is None:
            return {"status": "ERROR", "message": "Database unavailable."}

        self.ensure_order_tables()
        self.db.execute(
            text("""
                UPDATE forex_trade_orders
                SET status = 'cancelled',
                    updated_at = :updated_at
                WHERE broker_order_id = :broker_order_id
                  AND lower(status) IN ('open','pending','submitted','new')
            """),
            {"broker_order_id": broker_order_id, "updated_at": _naive_now()},
        )
        self._commit()
        return {"status": "cancelled", "broker_order_id": broker_order_id, "timestamp": _now_iso()}

    # ------------------------------------------------------------------
    # Execution paths
    # ------------------------------------------------------------------

    def _execute_market_order(
        self,
        *,
        engine: Any,
        account: Any,
        broker_order_id: str,
        pair: str,
        side: str,
        units: float,
        requested_price: Optional[float],
        stop_price: Optional[float],
        target_price: Optional[float],
        leverage: Optional[float],
        broker: str,
        raw: Dict[str, Any],
        validation: Dict[str, Any],
    ) -> Dict[str, Any]:
        position = engine.open_position(
            account_id=account.id,
            pair=pair,
            side=side,
            units=units,
            entry_price=requested_price,
            stop_price=stop_price,
            target_price=target_price,
            leverage=leverage,
            raw={
                "broker_order_id": broker_order_id,
                "broker": broker,
                "source": "forex_terminal_execution_service",
                "validation": validation,
                **(raw or {}),
            },
        )

        order_row = {
            "tenant_id": getattr(engine, "tenant_id", None),
            "user_id": getattr(engine, "user_id", None),
            "portfolio_id": position.portfolio_id,
            "account_id": account.id,
            "broker": broker,
            "broker_order_id": broker_order_id,
            "position_id": position.id,
            "symbol": _compact_pair(pair),
            "pair": pair,
            "side": side,
            "order_type": "MARKET",
            "quantity": units,
            "qty": units,
            "units": units,
            "lots": units / 100000.0,
            "limit_price": requested_price,
            "stop_price": stop_price,
            "target_price": target_price,
            "price": position.avg_entry_price,
            "avg_fill_price": position.avg_entry_price,
            "filled_qty": units,
            "status": "filled",
            "submitted_at": _naive_now(),
            "filled_at": _naive_now(),
            "created_at": _naive_now(),
            "updated_at": _naive_now(),
            "notes": "Paper Forex market order filled by terminal execution service.",
            "raw_payload": {"position": position.to_dict(), "raw": raw, "validation": validation},
        }

        self._insert_trade_order(order_row)

        snapshot = engine.get_terminal_snapshot(
            account_id=account.id,
            portfolio_id=position.portfolio_id,
            refresh=True,
            persist=True,
            include_orders=True,
            include_history=True,
        )

        snap_dict = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot

        return {
            "status": "filled",
            "message": "Paper Forex market order filled.",
            "broker": broker,
            "broker_order_id": broker_order_id,
            "account_id": account.id,
            "portfolio_id": position.portfolio_id,
            "position_id": position.id,
            "pair": pair,
            "symbol": _compact_pair(pair),
            "side": side,
            "units": units,
            "lots": units / 100000.0,
            "avg_fill_price": position.avg_entry_price,
            "filled_qty": units,
            "submitted_at": _now_iso(),
            "filled_at": _now_iso(),
            "position": position.to_dict(),
            "snapshot": snap_dict,
            "last_execution": {
                "broker_order_id": broker_order_id,
                "pair": pair,
                "side": side,
                "units": units,
                "lots": units / 100000.0,
                "avg_fill_price": position.avg_entry_price,
                "status": "filled",
                "timestamp": _now_iso(),
            },
        }

    def _persist_open_order(
        self,
        *,
        engine: Any,
        account: Any,
        broker_order_id: str,
        pair: str,
        side: str,
        units: float,
        order_type: str,
        limit_price: Optional[float],
        stop_price: Optional[float],
        target_price: Optional[float],
        risk_pct: Optional[float],
        broker: str,
        raw: Dict[str, Any],
        validation: Dict[str, Any],
    ) -> Dict[str, Any]:
        row = {
            "tenant_id": getattr(engine, "tenant_id", None),
            "user_id": getattr(engine, "user_id", None),
            "portfolio_id": account.portfolio_id,
            "account_id": account.id,
            "broker": broker,
            "broker_order_id": broker_order_id,
            "symbol": _compact_pair(pair),
            "pair": pair,
            "side": side,
            "order_type": order_type,
            "quantity": units,
            "qty": units,
            "units": units,
            "lots": units / 100000.0,
            "limit_price": limit_price,
            "stop_price": stop_price,
            "target_price": target_price,
            "price": limit_price,
            "status": "open",
            "submitted_at": _naive_now(),
            "created_at": _naive_now(),
            "updated_at": _naive_now(),
            "notes": "Paper Forex order staged by terminal execution service.",
            "raw_payload": {"risk_pct": risk_pct, "raw": raw, "validation": validation},
        }
        self._insert_trade_order(row)

        snapshot = engine.get_terminal_snapshot(
            account_id=account.id,
            portfolio_id=account.portfolio_id,
            refresh=True,
            persist=True,
            include_orders=True,
            include_history=True,
        )
        snap_dict = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot

        return {
            "status": "open",
            "message": "Paper Forex order staged.",
            "broker": broker,
            "broker_order_id": broker_order_id,
            "account_id": account.id,
            "portfolio_id": account.portfolio_id,
            "pair": pair,
            "symbol": _compact_pair(pair),
            "side": side,
            "units": units,
            "lots": units / 100000.0,
            "order_type": order_type,
            "snapshot": snap_dict,
            "last_execution": {
                "broker_order_id": broker_order_id,
                "pair": pair,
                "side": side,
                "units": units,
                "lots": units / 100000.0,
                "status": "open",
                "timestamp": _now_iso(),
            },
        }

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def ensure_order_tables(self) -> None:
        if self.db is None or text is None:
            return

        self.db.execute(text("""
            CREATE TABLE IF NOT EXISTS forex_trade_orders (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                account_id VARCHAR(64),
                broker VARCHAR(80),
                broker_order_id VARCHAR(120),
                position_id VARCHAR(64),
                symbol VARCHAR(20),
                pair VARCHAR(20),
                side VARCHAR(20),
                order_type VARCHAR(50),
                quantity DOUBLE PRECISION,
                qty DOUBLE PRECISION,
                units DOUBLE PRECISION,
                lots DOUBLE PRECISION,
                limit_price DOUBLE PRECISION,
                stop_price DOUBLE PRECISION,
                target_price DOUBLE PRECISION,
                price DOUBLE PRECISION,
                avg_fill_price DOUBLE PRECISION,
                filled_qty DOUBLE PRECISION,
                status VARCHAR(50),
                submitted_at TIMESTAMP WITHOUT TIME ZONE,
                filled_at TIMESTAMP WITHOUT TIME ZONE,
                cancelled_at TIMESTAMP WITHOUT TIME ZONE,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                raw_payload JSONB
            )
        """))

        self.db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_forex_trade_orders_portfolio_status
            ON forex_trade_orders (portfolio_id, status)
        """))

        self.db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_forex_trade_orders_broker_order_id
            ON forex_trade_orders (broker_order_id)
        """))

        self._commit()

    def _insert_trade_order(self, row: Dict[str, Any]) -> None:
        if self.db is None or text is None:
            return

        self.ensure_order_tables()
        columns = self._table_columns("forex_trade_orders")
        if not columns:
            return

        payload = {key: self._coerce_value(value) for key, value in row.items() if key in columns}
        if not payload:
            return

        names = list(payload.keys())
        self.db.execute(
            text(f"""
                INSERT INTO forex_trade_orders ({", ".join(names)})
                VALUES ({", ".join([f":{name}" for name in names])})
            """),
            payload,
        )
        self._commit()

    def _table_columns(self, table: str) -> List[str]:
        if self.db is None or text is None:
            return []
        try:
            rows = self.db.execute(
                text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = :table
                """),
                {"table": table},
            ).fetchall()
            return [str(row._mapping["column_name"]) for row in rows]
        except Exception:
            return []

    def _coerce_value(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value
        return value

    def _portfolio_engine(self, *, tenant_id: Optional[str], user_id: Optional[str], portfolio_id: Optional[str]) -> Any:
        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
        return get_forex_portfolio_engine(tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id, db=self.db)

    def _resolve_units(self, *, units: Optional[float], qty: Optional[float], lots: Optional[float]) -> float:
        if units is not None:
            return _safe_float(units)
        if qty is not None:
            return _safe_float(qty)
        if lots is not None:
            return _safe_float(lots) * 100000.0
        return 100000.0

    def _commit(self) -> None:
        try:
            if hasattr(self.db, "commit"):
                self.db.commit()
        except Exception:
            pass


_SERVICE = None


def get_forex_terminal_execution_service(db: Optional[Any] = None) -> ForexTerminalExecutionService:
    global _SERVICE
    if _SERVICE is None or (db is not None and _SERVICE.db is None):
        _SERVICE = ForexTerminalExecutionService(db=db)
    return _SERVICE
