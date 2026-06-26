
from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from sqlalchemy import text
except Exception:
    text = None


REQUIRED_MODULES = [
    "modules.forex.forex_portfolio_engine",
    "modules.forex.forex_terminal_api",
    "modules.forex.forex_terminal_execution_service",
    "modules.forex.forex_institutional_trade_ticket",
    "modules.forex.forex_ai_trade_assistant",
    "modules.forex.forex_institutional_risk_manager",
    "modules.forex.forex_autonomous_trading_engine",
    "modules.forex.forex_execution_monitor",
    "modules.forex.forex_institutional_workstation",
    "modules.forex.forex_trading_workspace",
    "modules.forex.forex_order_book",
    "modules.forex.forex_watchlist_manager",
    "modules.forex.forex_market_depth",
    "modules.forex.forex_trade_journal",
    "modules.forex.forex_execution_blotter",
    "modules.forex.forex_ai_command_center",
    "modules.forex.forex_economic_intelligence",
    "modules.forex.forex_microstructure_engine",
    "modules.forex.forex_autonomous_portfolio_manager",
]

REQUIRED_TABLES = [
    "forex_accounts",
    "forex_positions",
    "forex_cash_ledger",
    "forex_portfolio_snapshots",
    "forex_trade_orders",
    "forex_trade_journal",
]


class ForexTerminalValidationCenter:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def run_validation(self, *, execute_trade: bool = True, **kwargs) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        artifacts: Dict[str, Any] = {}

        def add(category: str, test: str, passed: bool, details: str = "", severity: str = "required"):
            results.append({
                "Category": category,
                "Test": test,
                "Passed": bool(passed),
                "Severity": severity,
                "Details": details,
            })

        self._validate_files(add)
        self._validate_imports(add)
        self._validate_tables(add)

        account_id = None
        portfolio_id = kwargs.get("portfolio_id")
        snapshot: Dict[str, Any] = {}

        try:
            from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
            pe = get_forex_portfolio_engine(
                db=self.db,
                tenant_id=kwargs.get("tenant_id"),
                user_id=kwargs.get("user_id"),
                portfolio_id=portfolio_id,
            )
            account = pe.get_or_create_account(portfolio_id=portfolio_id)
            account_id = getattr(account, "id", None)
            portfolio_id = getattr(account, "portfolio_id", portfolio_id)
            add("Portfolio", "Account create/load", account_id is not None, str(account_id))

            snap = pe.get_terminal_snapshot(
                account_id=account_id,
                portfolio_id=portfolio_id,
                refresh=True,
                persist=True,
                include_orders=True,
                include_history=True,
            )
            snapshot = snap.to_dict() if hasattr(snap, "to_dict") else snap
            artifacts["snapshot"] = snapshot
            add("Portfolio", "Terminal snapshot returned", isinstance(snapshot, dict), "snapshot dict")
            self._validate_snapshot_shape(snapshot, add)
        except Exception as exc:
            add("Portfolio", "Portfolio engine snapshot", False, str(exc))
            snapshot = {}

        execution: Dict[str, Any] = {}
        if execute_trade:
            try:
                from modules.forex.forex_terminal_execution_service import get_forex_terminal_execution_service
                svc = get_forex_terminal_execution_service(db=self.db)

                validation = svc.validate_order(
                    pair="EUR/USD",
                    side="BUY",
                    lots=0.01,
                    order_type="MARKET",
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                )
                artifacts["order_validation"] = validation
                add("Execution", "Order validation", validation.get("valid", False), "; ".join(validation.get("errors", [])))

                if validation.get("valid"):
                    execution = svc.submit_order(
                        pair="EUR/USD",
                        side="BUY",
                        lots=0.01,
                        order_type="MARKET",
                        account_id=account_id,
                        portfolio_id=portfolio_id,
                    )
                    artifacts["execution"] = execution
                    add("Execution", "Paper order submit", str(execution.get("status", "")).upper() in {"FILLED", "OPEN"}, str(execution.get("status")))
                    verification = execution.get("verification") or {}
                    add("Execution", "Execution verification", verification.get("verified", False), str(verification.get("checks", {})))
                    self._validate_order_and_position_rows(execution, add)
            except Exception as exc:
                add("Execution", "Paper execution workflow", False, str(exc))

        try:
            from modules.forex.forex_trading_workspace import get_forex_trading_workspace
            workspace = get_forex_trading_workspace(db=self.db).workspace_snapshot(pair="EUR/USD")
            artifacts["workspace"] = workspace
            add("Workstation", "Phase 6 workspace payload", isinstance(workspace, dict) and workspace.get("status") == "READY", str(workspace.get("status")))
            self._validate_workspace_shape(workspace, add)
        except Exception as exc:
            add("Workstation", "Phase 6 workspace", False, str(exc))

        passed = sum(1 for r in results if r["Passed"])
        failed = sum(1 for r in results if not r["Passed"])
        required_failed = sum(1 for r in results if not r["Passed"] and r["Severity"] == "required")

        return {
            "status": "PASS" if required_failed == 0 else "FAIL",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "passed": passed,
                "failed": failed,
                "required_failed": required_failed,
                "total": len(results),
            },
            "results": results,
            "artifacts": artifacts,
        }

    def _validate_files(self, add) -> None:
        for module_name in REQUIRED_MODULES:
            rel = Path(*module_name.split(".")).with_suffix(".py")
            exists = rel.exists()
            add("Files", str(rel), exists, "exists" if exists else "missing", "warning")

    def _validate_imports(self, add) -> None:
        for module_name in REQUIRED_MODULES:
            try:
                import_module(module_name)
                add("Imports", module_name, True, "import ok")
            except Exception as exc:
                add("Imports", module_name, False, str(exc))

    def _validate_tables(self, add) -> None:
        if self.db is None or text is None:
            add("Database", "DB session available", False, "No db session or SQLAlchemy text unavailable")
            return

        add("Database", "DB session available", True, "db session present")

        for table in REQUIRED_TABLES:
            exists = self._table_exists(table)
            add("Database", f"Table {table}", exists, "exists" if exists else "missing", "warning" if table in {"forex_trade_orders", "forex_trade_journal"} else "required")

    def _validate_snapshot_shape(self, snapshot: Dict[str, Any], add) -> None:
        for key in ["account", "portfolio", "positions", "open_orders", "filled_orders", "execution_history", "risk", "performance", "margin", "currency_exposure", "pair_exposure"]:
            add("Snapshot", f"snapshot.{key}", key in snapshot, "present" if key in snapshot else "missing")

    def _validate_workspace_shape(self, workspace: Dict[str, Any], add) -> None:
        for key in ["terminal", "watchlist", "order_book", "market_depth", "journal", "execution_blotter", "ai_command_center", "economic_intelligence", "microstructure"]:
            add("Workstation", f"workspace.{key}", key in workspace, "present" if key in workspace else "missing")

    def _validate_order_and_position_rows(self, execution: Dict[str, Any], add) -> None:
        if self.db is None or text is None:
            return

        broker_order_id = execution.get("broker_order_id")
        position_id = execution.get("position_id")

        try:
            if broker_order_id:
                row = self.db.execute(
                    text("SELECT 1 FROM forex_trade_orders WHERE broker_order_id = :id LIMIT 1"),
                    {"id": broker_order_id},
                ).fetchone()
                add("Database Rows", "Order row exists", row is not None, str(broker_order_id))
        except Exception as exc:
            add("Database Rows", "Order row exists", False, str(exc))

        try:
            if position_id:
                row = self.db.execute(
                    text("SELECT 1 FROM forex_positions WHERE id = :id LIMIT 1"),
                    {"id": position_id},
                ).fetchone()
                add("Database Rows", "Position row exists", row is not None, str(position_id))
        except Exception as exc:
            add("Database Rows", "Position row exists", False, str(exc), "warning")

    def _table_exists(self, table: str) -> bool:
        try:
            row = self.db.execute(
                text("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name = :table
                    )
                """),
                {"table": table},
            ).fetchone()
            return bool(row[0]) if row else False
        except Exception:
            try:
                self.db.execute(text(f"SELECT 1 FROM {table} LIMIT 1")).fetchone()
                return True
            except Exception:
                return False


_VALID = None


def get_forex_terminal_validation_center(db=None):
    global _VALID
    if _VALID is None or (db is not None and _VALID.db is None):
        _VALID = ForexTerminalValidationCenter(db=db)
    return _VALID
