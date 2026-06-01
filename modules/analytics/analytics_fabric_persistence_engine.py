"""
modules/analytics/analytics_fabric_persistence_engine.py
"""

from __future__ import annotations

import csv
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, default=str)


def _json_loads(value: Optional[str]) -> Any:
    if not value:
        return None

    try:
        return json.loads(value)
    except Exception:
        return value


@dataclass
class AnalyticsSnapshot:
    snapshot_id: str
    snapshot_type: str
    payload: Dict[str, Any]
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass
class ValidationHistoryRecord:
    record_id: str
    validation_type: str
    status: str
    passed: int
    failed: int
    warnings: int
    payload: Dict[str, Any]
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class StressHistoryRecord:
    record_id: str
    stress_type: str
    status: str
    duration_seconds: float
    payload: Dict[str, Any]
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class BenchmarkHistoryRecord:
    record_id: str
    benchmark_type: str
    operations_per_second: float
    payload: Dict[str, Any]
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class CapacityForecastRecord:
    record_id: str
    forecast_type: str
    payload: Dict[str, Any]
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class ProviderIntelligenceRecord:
    record_id: str
    provider: str
    payload: Dict[str, Any]
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class GovernanceDecisionRecord:
    record_id: str
    decision_type: str
    severity: str
    payload: Dict[str, Any]
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class GlobalPlanRecord:
    record_id: str
    plan_id: str
    state: str
    payload: Dict[str, Any]
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class TenantIntelligenceRecord:
    record_id: str
    tenant_id: str
    payload: Dict[str, Any]
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class ExecutiveSnapshotRecord:
    record_id: str
    snapshot_name: str
    payload: Dict[str, Any]
    created_at: str = field(default_factory=utc_now_iso)


class AnalyticsFabricPersistenceEngine:
    def __init__(
        self,
        db_path: str = "data/analytics_fabric_history.db",
    ) -> None:
        self.db_path = db_path

        Path(db_path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize_database()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_database(self) -> None:
        with self._connect() as conn:

            conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_validation_history (
                record_id TEXT PRIMARY KEY,
                validation_type TEXT,
                status TEXT,
                passed INTEGER,
                failed INTEGER,
                warnings INTEGER,
                payload_json TEXT,
                created_at TEXT
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_stress_history (
                record_id TEXT PRIMARY KEY,
                stress_type TEXT,
                status TEXT,
                duration_seconds REAL,
                payload_json TEXT,
                created_at TEXT
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_benchmark_history (
                record_id TEXT PRIMARY KEY,
                benchmark_type TEXT,
                operations_per_second REAL,
                payload_json TEXT,
                created_at TEXT
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_capacity_forecasts (
                record_id TEXT PRIMARY KEY,
                forecast_type TEXT,
                payload_json TEXT,
                created_at TEXT
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_provider_history (
                record_id TEXT PRIMARY KEY,
                provider TEXT,
                payload_json TEXT,
                created_at TEXT
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_governance_history (
                record_id TEXT PRIMARY KEY,
                decision_type TEXT,
                severity TEXT,
                payload_json TEXT,
                created_at TEXT
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_global_plan_history (
                record_id TEXT PRIMARY KEY,
                plan_id TEXT,
                state TEXT,
                payload_json TEXT,
                created_at TEXT
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_tenant_intelligence_history (
                record_id TEXT PRIMARY KEY,
                tenant_id TEXT,
                payload_json TEXT,
                created_at TEXT
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_control_tower_snapshots (
                record_id TEXT PRIMARY KEY,
                payload_json TEXT,
                created_at TEXT
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_executive_snapshots (
                record_id TEXT PRIMARY KEY,
                snapshot_name TEXT,
                payload_json TEXT,
                created_at TEXT
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_fabric_health_history (
                record_id TEXT PRIMARY KEY,
                payload_json TEXT,
                created_at TEXT
            )
            """)

    def save_validation_result(
        self,
        validation_type: str,
        result: Dict[str, Any],
    ) -> str:
        summary = result.get("summary", {})

        record_id = f"val_{uuid.uuid4().hex}"

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analytics_validation_history
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    validation_type,
                    summary.get("status", "UNKNOWN"),
                    summary.get("passed", 0),
                    summary.get("failed", 0),
                    summary.get("warnings", 0),
                    _json_dumps(result),
                    utc_now_iso(),
                ),
            )

        return record_id

    def save_stress_result(
        self,
        stress_type: str,
        result: Dict[str, Any],
        duration_seconds: float,
    ) -> str:
        record_id = f"stress_{uuid.uuid4().hex}"

        status = (
            result.get("summary", {})
            .get("status", "UNKNOWN")
        )

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analytics_stress_history
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    stress_type,
                    status,
                    duration_seconds,
                    _json_dumps(result),
                    utc_now_iso(),
                ),
            )

        return record_id

    def save_benchmark_result(
        self,
        benchmark_type: str,
        operations_per_second: float,
        payload: Dict[str, Any],
    ) -> str:
        record_id = f"bench_{uuid.uuid4().hex}"

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analytics_benchmark_history
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    benchmark_type,
                    operations_per_second,
                    _json_dumps(payload),
                    utc_now_iso(),
                ),
            )

        return record_id

    def save_capacity_forecast(
        self,
        forecast_type: str,
        payload: Dict[str, Any],
    ) -> str:
        record_id = f"cap_{uuid.uuid4().hex}"

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analytics_capacity_forecasts
                VALUES (?, ?, ?, ?)
                """,
                (
                    record_id,
                    forecast_type,
                    _json_dumps(payload),
                    utc_now_iso(),
                ),
            )

        return record_id

    def save_provider_profile(
        self,
        provider: str,
        payload: Dict[str, Any],
    ) -> str:
        record_id = f"prov_{uuid.uuid4().hex}"

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analytics_provider_history
                VALUES (?, ?, ?, ?)
                """,
                (
                    record_id,
                    provider,
                    _json_dumps(payload),
                    utc_now_iso(),
                ),
            )

        return record_id

    def save_governance_decision(
        self,
        decision_type: str,
        severity: str,
        payload: Dict[str, Any],
    ) -> str:
        record_id = f"gov_{uuid.uuid4().hex}"

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analytics_governance_history
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    decision_type,
                    severity,
                    _json_dumps(payload),
                    utc_now_iso(),
                ),
            )

        return record_id

    def save_global_plan(
        self,
        plan_id: str,
        state: str,
        payload: Dict[str, Any],
    ) -> str:
        record_id = f"plan_{uuid.uuid4().hex}"

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analytics_global_plan_history
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    plan_id,
                    state,
                    _json_dumps(payload),
                    utc_now_iso(),
                ),
            )

        return record_id

    def save_tenant_intelligence(
        self,
        tenant_id: str,
        payload: Dict[str, Any],
    ) -> str:
        record_id = f"tenant_{uuid.uuid4().hex}"

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analytics_tenant_intelligence_history
                VALUES (?, ?, ?, ?)
                """,
                (
                    record_id,
                    tenant_id,
                    _json_dumps(payload),
                    utc_now_iso(),
                ),
            )

        return record_id

    def save_control_tower_snapshot(
        self,
        payload: Dict[str, Any],
    ) -> str:
        record_id = f"tower_{uuid.uuid4().hex}"

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analytics_control_tower_snapshots
                VALUES (?, ?, ?)
                """,
                (
                    record_id,
                    _json_dumps(payload),
                    utc_now_iso(),
                ),
            )

        return record_id

    def save_executive_snapshot(
        self,
        snapshot_name: str,
        payload: Dict[str, Any],
    ) -> str:
        record_id = f"exec_{uuid.uuid4().hex}"

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analytics_executive_snapshots
                VALUES (?, ?, ?, ?)
                """,
                (
                    record_id,
                    snapshot_name,
                    _json_dumps(payload),
                    utc_now_iso(),
                ),
            )

        return record_id

    def save_fabric_health_snapshot(
        self,
        payload: Dict[str, Any],
    ) -> str:
        record_id = f"health_{uuid.uuid4().hex}"

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analytics_fabric_health_history
                VALUES (?, ?, ?)
                """,
                (
                    record_id,
                    _json_dumps(payload),
                    utc_now_iso(),
                ),
            )

        return record_id

    def _fetch_all(
        self,
        table: str,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM {table}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    def get_validation_history(self):
        return self._fetch_all(
            "analytics_validation_history"
        )

    def get_stress_history(self):
        return self._fetch_all(
            "analytics_stress_history"
        )

    def get_benchmark_history(self):
        return self._fetch_all(
            "analytics_benchmark_history"
        )

    def get_capacity_history(self):
        return self._fetch_all(
            "analytics_capacity_forecasts"
        )

    def get_provider_history(self):
        return self._fetch_all(
            "analytics_provider_history"
        )

    def get_governance_history(self):
        return self._fetch_all(
            "analytics_governance_history"
        )

    def get_global_plan_history(self):
        return self._fetch_all(
            "analytics_global_plan_history"
        )

    def get_tenant_intelligence_history(self):
        return self._fetch_all(
            "analytics_tenant_intelligence_history"
        )

    def get_control_tower_history(self):
        return self._fetch_all(
            "analytics_control_tower_snapshots"
        )

    def get_executive_history(self):
        return self._fetch_all(
            "analytics_executive_snapshots"
        )

    def get_fabric_health_history(self):
        return self._fetch_all(
            "analytics_fabric_health_history"
        )

    def calculate_validation_trends(self) -> Dict[str, Any]:
        rows = self.get_validation_history()

        total = len(rows)

        passed = len(
            [
                r for r in rows
                if r["status"] == "PASS"
            ]
        )

        return {
            "total_runs": total,
            "pass_rate": (
                passed / total
                if total
                else 0
            ),
        }

    def calculate_performance_trends(self):
        rows = self.get_benchmark_history()

        if not rows:
            return {}

        ops = [
            r["operations_per_second"]
            for r in rows
        ]

        return {
            "avg_ops_per_sec": sum(ops) / len(ops),
            "max_ops_per_sec": max(ops),
            "min_ops_per_sec": min(ops),
        }

    def calculate_capacity_trends(self):
        return {
            "forecasts": len(
                self.get_capacity_history()
            )
        }

    def calculate_provider_cost_trends(self):
        rows = self.get_provider_history()

        return {
            "records": len(rows)
        }

    def calculate_governance_trends(self):
        rows = self.get_governance_history()

        return {
            "decisions": len(rows)
        }

    def calculate_health_trends(self):
        rows = self.get_fabric_health_history()

        return {
            "health_snapshots": len(rows)
        }

    def export_history_json(
        self,
        output_path: str,
    ) -> str:
        export = {
            "validation": self.get_validation_history(),
            "stress": self.get_stress_history(),
            "benchmarks": self.get_benchmark_history(),
            "capacity": self.get_capacity_history(),
            "providers": self.get_provider_history(),
            "governance": self.get_governance_history(),
            "plans": self.get_global_plan_history(),
            "tenant_intelligence": self.get_tenant_intelligence_history(),
            "control_tower": self.get_control_tower_history(),
            "executive": self.get_executive_history(),
            "health": self.get_fabric_health_history(),
        }

        with open(
            output_path,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                export,
                f,
                indent=2,
                default=str,
            )

        return output_path

    def export_history_csv(
        self,
        table_name: str,
        output_path: str,
    ) -> str:
        rows = self._fetch_all(table_name)

        if not rows:
            return output_path

        with open(
            output_path,
            "w",
            newline="",
            encoding="utf-8",
        ) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=list(rows[0].keys()),
            )

            writer.writeheader()
            writer.writerows(rows)

        return output_path

    def export_history_excel(
        self,
        output_path: str,
    ) -> str:
        with pd.ExcelWriter(output_path) as writer:

            sheets = {
                "validation": self.get_validation_history(),
                "stress": self.get_stress_history(),
                "benchmark": self.get_benchmark_history(),
                "capacity": self.get_capacity_history(),
                "providers": self.get_provider_history(),
                "governance": self.get_governance_history(),
                "plans": self.get_global_plan_history(),
                "tenant_intelligence": self.get_tenant_intelligence_history(),
                "control_tower": self.get_control_tower_history(),
                "executive": self.get_executive_history(),
                "health": self.get_fabric_health_history(),
            }

            for sheet, rows in sheets.items():
                pd.DataFrame(rows).to_excel(
                    writer,
                    sheet_name=sheet[:31],
                    index=False,
                )

        return output_path

    def summary(self) -> Dict[str, Any]:
        return {
            "db_path": self.db_path,
            "validation_records": len(self.get_validation_history()),
            "stress_records": len(self.get_stress_history()),
            "benchmark_records": len(self.get_benchmark_history()),
            "capacity_records": len(self.get_capacity_history()),
            "provider_records": len(self.get_provider_history()),
            "governance_records": len(self.get_governance_history()),
            "plan_records": len(self.get_global_plan_history()),
            "tenant_records": len(self.get_tenant_intelligence_history()),
            "control_tower_records": len(self.get_control_tower_history()),
            "executive_records": len(self.get_executive_history()),
            "health_records": len(self.get_fabric_health_history()),
            "generated_at": utc_now_iso(),
        }