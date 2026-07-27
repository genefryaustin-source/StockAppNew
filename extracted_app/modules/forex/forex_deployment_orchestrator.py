"""
modules/forex/forex_deployment_orchestrator.py

Deployment orchestrator for the Forex subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

try:
    from sqlalchemy import text
except Exception:
    text = None

try:
    from modules.forex.forex_release_manager import get_forex_release_manager
except Exception:
    get_forex_release_manager = None

try:
    from modules.forex.forex_production_readiness_suite import run_forex_production_readiness_suite
except Exception:
    run_forex_production_readiness_suite = None

try:
    from modules.forex.forex_provider_health import get_forex_provider_health
except Exception:
    get_forex_provider_health = None

try:
    from modules.forex.forex_registry import get_forex_registry
except Exception:
    get_forex_registry = None


@dataclass
class ForexDeploymentSnapshot:
    deployment_id: str
    environment: str
    status: str
    created_at: str
    readiness_status: str
    readiness_score: float
    provider_status: str
    registry_status: str
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ForexDeploymentOrchestrator:
    def __init__(self, db=None):
        self.db = db
        self.release_manager = get_forex_release_manager(db=db) if get_forex_release_manager else None
        self.history: List[Dict[str, Any]] = []

    def ensure_tables(self) -> None:
        if self.db is None or text is None:
            return

        self.db.execute(text("""
            CREATE TABLE IF NOT EXISTS forex_deployment_history (
                id SERIAL PRIMARY KEY,
                deployment_id VARCHAR(100),
                environment VARCHAR(50),
                status VARCHAR(50),
                readiness_status VARCHAR(100),
                readiness_score DOUBLE PRECISION,
                provider_status VARCHAR(100),
                registry_status VARCHAR(100),
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        self.db.commit()

    def validate_configuration(self) -> Dict[str, Any]:
        checks = {
            "release_manager": self.release_manager is not None,
            "production_readiness_suite": run_forex_production_readiness_suite is not None,
            "provider_health": get_forex_provider_health is not None,
            "registry": get_forex_registry is not None,
        }
        return {
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
        }

    def verify_provider_configuration(self) -> Dict[str, Any]:
        if get_forex_provider_health is None:
            return {"status": "UNAVAILABLE", "providers": {}}

        try:
            health = get_forex_provider_health()
            summary = health.summary()
            return {
                "status": "PASS",
                "providers": summary,
            }
        except Exception as exc:
            return {
                "status": "FAIL",
                "error": str(exc),
                "providers": {},
            }

    def verify_database_connectivity(self) -> Dict[str, Any]:
        if self.db is None or text is None:
            return {
                "status": "SKIPPED",
                "message": "Database connection not supplied.",
            }

        try:
            self.db.execute(text("SELECT 1"))
            return {"status": "PASS"}
        except Exception as exc:
            return {
                "status": "FAIL",
                "error": str(exc),
            }

    def verify_ai_configuration(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_ai_assistant import get_forex_ai_assistant
            obj = get_forex_ai_assistant(db=self.db)
            return {
                "status": "PASS" if obj is not None else "FAIL",
                "object_type": type(obj).__name__ if obj is not None else None,
            }
        except Exception as exc:
            return {
                "status": "FAIL",
                "error": str(exc),
            }

    def verify_trading_configuration(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_trade_execution_engine import get_forex_trade_execution_engine
            from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager
            execution = get_forex_trade_execution_engine(db=self.db)
            portfolio = get_forex_portfolio_manager(db=self.db)
            return {
                "status": "PASS",
                "execution_engine": type(execution).__name__,
                "portfolio_manager": type(portfolio).__name__,
                "mode": "paper_ready",
            }
        except Exception as exc:
            return {
                "status": "FAIL",
                "error": str(exc),
            }

    def run_readiness(self, live_provider_checks: bool = False, execute_paper_trade: bool = False) -> Dict[str, Any]:
        if run_forex_production_readiness_suite is None:
            return {
                "production_status": "UNAVAILABLE",
                "overall_score": 0.0,
                "error": "Production readiness suite unavailable.",
            }

        return run_forex_production_readiness_suite(
            db=self.db,
            live_provider_checks=live_provider_checks,
            execute_paper_trade=execute_paper_trade,
        )

    def create_deployment_snapshot(
        self,
        environment: str,
        readiness: Dict[str, Any],
        provider_check: Dict[str, Any],
        registry_check: Dict[str, Any],
        status: str,
        notes: str = "",
    ) -> Dict[str, Any]:
        snapshot = ForexDeploymentSnapshot(
            deployment_id=f"FXDEP-{uuid.uuid4().hex[:12].upper()}",
            environment=environment,
            status=status,
            created_at=datetime.now(timezone.utc).isoformat(),
            readiness_status=str(readiness.get("production_status", "UNKNOWN")),
            readiness_score=float(readiness.get("overall_score") or 0.0),
            provider_status=str(provider_check.get("status", "UNKNOWN")),
            registry_status=str(registry_check.get("status", "UNKNOWN")),
            notes=notes,
        ).to_dict()

        self.history.append(snapshot)
        self._persist_snapshot(snapshot)
        return snapshot

    def _persist_snapshot(self, snapshot: Dict[str, Any]) -> None:
        if self.db is None or text is None:
            return

        self.ensure_tables()
        self.db.execute(text("""
            INSERT INTO forex_deployment_history (
                deployment_id,
                environment,
                status,
                readiness_status,
                readiness_score,
                provider_status,
                registry_status,
                notes,
                created_at
            )
            VALUES (
                :deployment_id,
                :environment,
                :status,
                :readiness_status,
                :readiness_score,
                :provider_status,
                :registry_status,
                :notes,
                :created_at
            )
        """), {
            "deployment_id": snapshot.get("deployment_id"),
            "environment": snapshot.get("environment"),
            "status": snapshot.get("status"),
            "readiness_status": snapshot.get("readiness_status"),
            "readiness_score": snapshot.get("readiness_score"),
            "provider_status": snapshot.get("provider_status"),
            "registry_status": snapshot.get("registry_status"),
            "notes": snapshot.get("notes"),
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
        })
        self.db.commit()

    def deployment_status(self) -> Dict[str, Any]:
        latest = self.history[-1] if self.history else None

        if latest is None and self.db is not None and text is not None:
            try:
                self.ensure_tables()
                row = self.db.execute(text("""
                    SELECT *
                    FROM forex_deployment_history
                    ORDER BY created_at DESC
                    LIMIT 1
                """)).fetchone()
                latest = dict(row._mapping) if row else None
            except Exception:
                latest = None

        return {
            "status": latest.get("status") if latest else "NO_DEPLOYMENTS",
            "latest": latest,
            "history_count": len(self.history),
        }

    def deployment_history(self, limit: int = 25) -> List[Dict[str, Any]]:
        if self.db is not None and text is not None:
            try:
                self.ensure_tables()
                rows = self.db.execute(text("""
                    SELECT *
                    FROM forex_deployment_history
                    ORDER BY created_at DESC
                    LIMIT :limit
                """), {"limit": int(limit)}).fetchall()
                return [dict(r._mapping) for r in rows]
            except Exception:
                pass

        return list(reversed(self.history[-int(limit):]))

    def deploy_staging(self) -> Dict[str, Any]:
        return self._deploy(
            environment="staging",
            live_provider_checks=False,
            execute_paper_trade=False,
            require_ready=False,
        )

    def deploy_production(
        self,
        live_provider_checks: bool = False,
        execute_paper_trade: bool = False,
    ) -> Dict[str, Any]:
        return self._deploy(
            environment="production",
            live_provider_checks=live_provider_checks,
            execute_paper_trade=execute_paper_trade,
            require_ready=True,
        )

    def _deploy(
        self,
        environment: str,
        live_provider_checks: bool,
        execute_paper_trade: bool,
        require_ready: bool,
    ) -> Dict[str, Any]:
        config = self.validate_configuration()
        providers = self.verify_provider_configuration()
        database = self.verify_database_connectivity()
        ai = self.verify_ai_configuration()
        trading = self.verify_trading_configuration()
        readiness = self.run_readiness(
            live_provider_checks=live_provider_checks,
            execute_paper_trade=execute_paper_trade,
        )

        registry_status = "PASS" if config.get("checks", {}).get("registry") else "FAIL"
        ready = readiness.get("production_status") == "READY_FOR_DEPLOYMENT"

        blockers = []
        for name, result in {
            "configuration": config,
            "providers": providers,
            "database": database,
            "ai": ai,
            "trading": trading,
        }.items():
            if result.get("status") == "FAIL":
                blockers.append(name)

        if require_ready and not ready:
            blockers.append("production_readiness")

        status = "DEPLOYED" if not blockers else "BLOCKED"

        snapshot = self.create_deployment_snapshot(
            environment=environment,
            readiness=readiness,
            provider_check=providers,
            registry_check={"status": registry_status},
            status=status,
            notes="Blocked by: " + ", ".join(blockers) if blockers else "Deployment completed.",
        )

        return {
            "deployment": snapshot,
            "status": status,
            "environment": environment,
            "blockers": blockers,
            "configuration": config,
            "providers": providers,
            "database": database,
            "ai": ai,
            "trading": trading,
            "readiness": readiness,
        }

    def rollback(self, deployment_id: Optional[str] = None, reason: str = "") -> Dict[str, Any]:
        target = deployment_id or ((self.history[-1] or {}).get("deployment_id") if self.history else None)

        snapshot = {
            "deployment_id": f"FXROLLBACK-{uuid.uuid4().hex[:12].upper()}",
            "environment": "rollback",
            "status": "ROLLED_BACK",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "readiness_status": "ROLLBACK",
            "readiness_score": 0.0,
            "provider_status": "UNCHANGED",
            "registry_status": "UNCHANGED",
            "notes": f"Rollback target={target}. {reason}".strip(),
        }

        self.history.append(snapshot)
        self._persist_snapshot(snapshot)

        return {
            "status": "ROLLED_BACK",
            "target_deployment_id": target,
            "rollback": snapshot,
        }

    def deployment_report(self) -> Dict[str, Any]:
        status = self.deployment_status()
        history = self.deployment_history()
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "history": history,
        }


_ORCHESTRATOR = None


def get_forex_deployment_orchestrator(db=None) -> ForexDeploymentOrchestrator:
    global _ORCHESTRATOR
    if _ORCHESTRATOR is None or (db is not None and _ORCHESTRATOR.db is None):
        _ORCHESTRATOR = ForexDeploymentOrchestrator(db=db)
    return _ORCHESTRATOR
