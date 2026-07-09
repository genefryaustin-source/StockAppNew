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
import json

from modules.execution.execution_context_validator import ExecutionContext
from modules.execution.execution_models import AssetClass, ExecutionActor, ExecutionSource
from modules.execution.execution_pipeline_factory import (
    build_execution_pipeline,
)
from modules.execution.execution_service import (
    get_execution_service,
)
from modules.execution.execution_service import (
    get_execution_service,
)

from modules.forex.forex_portfolio_engine import (
    get_forex_portfolio_engine,
)
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

def _optional_price(value: Any) -> Optional[float]:
    price = _safe_float(value, default=0.0)
    return price if price > 0 else None


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

    def __init__(
        self,
        db=None,
        tenant_id=None,
        user_id=None,
        portfolio_id=None,
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id
        self.execution_service = None

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
                print("=" * 80)
                print("LOOKING UP ACCOUNT")
                print("account_id :", account_id)
                print("tenant_id  :", tenant_id)
                print("user_id    :", user_id)
                print("portfolio  :", portfolio_id)
                print("=" * 80)
                account = engine.get_account(account_id=account_id) if account_id else None
                print("=" * 80)
                print("GET_ACCOUNT RESULT")
                print(account)
                print("=" * 80)
                if account is None:
                    account = engine.get_or_create_account(portfolio_id=portfolio_id)
                    print("=" * 80)
                    print("ACCOUNT CREATED/LOADED")
                    print("tenant_id   :", engine.tenant_id)
                    print("user_id     :", engine.user_id)
                    print("portfolio_id:", engine.portfolio_id)
                    print("account_id  :", account.id)
                    print("=" * 80)
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
            print("=" * 80)
            print("ORDER VALIDATION")
            print("VALID   :", validation.get("valid"))
            print("ERRORS  :", validation.get("errors"))
            print("WARNINGS:", validation.get("warnings"))
            print("ACCOUNT :", validation.get("account"))
            print("MARGIN  :", validation.get("margin"))
            print("=" * 80)
            return {
                "status": "REJECTED",
                "message": "A portfolio must be created or selected before submitting a Forex order.",
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
        print("=" * 80)
        print("LOOKING UP ACCOUNT")
        print("account_id :", account_id)
        print("tenant_id  :", tenant_id)
        print("user_id    :", user_id)
        print("portfolio  :", portfolio_id)
        print("=" * 80)
        account = engine.get_account(account_id=account_id) if account_id else None
        print("=" * 80)
        print("GET_ACCOUNT RESULT")
        print(account)
        print("=" * 80)
        if account is None:
            account = engine.get_or_create_account(portfolio_id=portfolio_id)

        broker_order_id = kwargs.get("broker_order_id") or f"FXP-{uuid.uuid4().hex[:12].upper()}"

        service = self._get_execution_service(
            engine,
        )
        print("=" * 80)
        print("CONTEXT INPUT")
        print("requested_price :", kwargs.get("price"))
        print("stop_price      :", kwargs.get("stop_price"))
        print("target_price    :", kwargs.get("target_price"))
        print("take_profit     :", kwargs.get("take_profit"))
        print("=" * 80)

        requested_price = (
                _safe_float(kwargs.get("limit_price"))
                or _safe_float(kwargs.get("price"))
                or _safe_float(kwargs.get("entry_price"))
        )

        stop_price = _optional_price(
            kwargs.get("stop_price")
        )

        target_price = (
            _optional_price(kwargs.get("target_price"))
            if kwargs.get("target_price") is not None
            else _optional_price(kwargs.get("take_profit"))
        )
        context = service.submit(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            account_id=getattr(account, "id", None),
            account=account,
            asset_class="FOREX",
            pair=pair_norm,
            symbol=pair_norm.replace("/", ""),
            side=side_norm,
            units=order_units,
            broker=broker,
            broker_order_id=broker_order_id,
            requested_price=requested_price,
            stop_price=stop_price,
            target_price=target_price,
            leverage=kwargs.get("leverage"),
            raw_request=kwargs,
        )

        context.validation = validation

        result = self._context_to_result(context)

        try:
            verification = service.verify_execution(context)
            if verification:
                result["verification"] = verification
        except Exception:
            pass

        return result

    def verify_execution(
            self,
            *,
            broker_order_id: Optional[str] = None,
            position_id: Optional[str] = None,
            account_id: Optional[str] = None,
            portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Temporary compatibility wrapper.

        Sprint 26:
            Verification is owned by ExecutionSnapshotPipeline.

        Sprint 27:
            Remove the legacy implementation once all callers
            provide an ExecutionContext.
        """

        pipeline = getattr(self, "execution_pipeline", None)

        if (
                pipeline is not None
                and hasattr(pipeline, "snapshot_pipeline")
                and hasattr(pipeline.snapshot_pipeline, "verify_execution")
        ):
            #
            # We cannot delegate yet because this legacy API receives
            # IDs instead of an ExecutionContext.
            #
            pass

        return self._verify_execution_legacy(
            broker_order_id=broker_order_id,
            position_id=position_id,
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

    def _verify_execution_legacy(
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

        portfolio_engine = get_forex_portfolio_engine(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            db=self.db,
        )

        service = get_execution_service(
            db=self.db,
            portfolio_engine=portfolio_engine,
        )

        try:

            service.get_pipeline().order_repository.ensure_tables()

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

        pipeline = self._get_execution_pipeline(
            self._portfolio_engine(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
            )
        )

        pipeline.order_repository.cancel_pending_order(
            broker_order_id=broker_order_id,
        )
        return {"status": "cancelled", "broker_order_id": broker_order_id, "timestamp": _now_iso()}

    # ------------------------------------------------------------------
    # Execution paths
    # ------------------------------------------------------------------





    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------











    def _context_to_result(
            self,
            context: ExecutionContext,
    ) -> Dict[str, Any]:

        if context is None:
            return {
                "status": "ERROR",
                "message": "Execution context unavailable.",
            }

        if hasattr(context, "to_response"):
            return context.to_response()

        return context.to_dict()

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

    def _get_execution_service(
            self,
            portfolio_engine,
    ):

        if self.execution_service is None:
            self.execution_service = get_execution_service(

                db=self.db,

                portfolio_engine=portfolio_engine,

                actor=self.actor,

                source=self.source,

            )

        return self.execution_service

    def _get_execution_pipeline(
            self,
            engine,
    ):
        """
        Return the institutional execution pipeline for this
        execution service.

        The pipeline is created lazily and cached for reuse.
        """

        if getattr(self, "execution_pipeline", None) is None:
            self.execution_service = build_execution_pipeline(
                db=self.db,
                portfolio_engine=engine,
            )

        return self.execution_service

    
    # ------------------------------------------------------------------
    # Sprint 26 Phase 2A Event Recording
    # ------------------------------------------------------------------



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
