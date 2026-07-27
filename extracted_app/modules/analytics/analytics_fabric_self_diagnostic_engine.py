"""
modules/analytics/analytics_fabric_self_diagnostic_engine.py
"""

from __future__ import annotations

import statistics
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(minimum, min(maximum, float(value)))


class DiagnosticSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ComponentHealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    FAILED = "FAILED"


@dataclass
class DiagnosticFinding:
    finding_id: str
    component: str
    severity: str
    title: str
    description: str
    recommendation: str
    created_at: str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComponentDiagnostic:
    component: str
    health_score: float
    risk_score: float
    state: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    findings: List[DiagnosticFinding] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "health_score": self.health_score,
            "risk_score": self.risk_score,
            "state": self.state,
            "metrics": self.metrics,
            "findings": [f.as_dict() for f in self.findings],
        }


@dataclass
class FabricHealthReport:
    report_id: str
    generated_at: str
    overall_health_score: float
    overall_risk_score: float
    state: str
    component_reports: List[ComponentDiagnostic]
    recommendations: List[str]
    anomalies: List[Dict[str, Any]]
    predicted_failures: List[Dict[str, Any]]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "overall_health_score": self.overall_health_score,
            "overall_risk_score": self.overall_risk_score,
            "state": self.state,
            "component_reports": [
                component.as_dict()
                for component in self.component_reports
            ],
            "recommendations": self.recommendations,
            "anomalies": self.anomalies,
            "predicted_failures": self.predicted_failures,
        }


class AnalyticsFabricSelfDiagnosticEngine:
    """
    Autonomous health and diagnostics engine
    for the Analytics Fabric ecosystem.
    """

    def __init__(
        self,
        *,
        control_plane: Optional[Any] = None,
        command_processor: Optional[Any] = None,
        continuous_runtime_engine: Optional[Any] = None,
        autonomous_supervisor: Optional[Any] = None,
        runtime_controller: Optional[Any] = None,
        execution_orchestrator: Optional[Any] = None,
        execution_planner: Optional[Any] = None,
        forecast_optimizer: Optional[Any] = None,
        forecasting_engine: Optional[Any] = None,
        persistence_engine: Optional[Any] = None,
    ):
        self.control_plane = control_plane
        self.command_processor = command_processor
        self.continuous_runtime_engine = continuous_runtime_engine
        self.autonomous_supervisor = autonomous_supervisor
        self.runtime_controller = runtime_controller
        self.execution_orchestrator = execution_orchestrator
        self.execution_planner = execution_planner
        self.forecast_optimizer = forecast_optimizer
        self.forecasting_engine = forecasting_engine
        self.persistence_engine = persistence_engine

        self.diagnostic_history: List[FabricHealthReport] = []
        self.findings_history: List[DiagnosticFinding] = []
        self.last_report: Optional[FabricHealthReport] = None

    # ============================================================
    # Main APIs
    # ============================================================

    def run_diagnostics(self) -> FabricHealthReport:
        reports = [
            self.run_component_diagnostics("control_plane", self.control_plane),
            self.run_component_diagnostics("command_processor", self.command_processor),
            self.run_component_diagnostics("continuous_runtime", self.continuous_runtime_engine),
            self.run_component_diagnostics("autonomous_supervisor", self.autonomous_supervisor),
            self.run_component_diagnostics("runtime_controller", self.runtime_controller),
            self.run_component_diagnostics("execution_orchestrator", self.execution_orchestrator),
            self.run_component_diagnostics("execution_planner", self.execution_planner),
            self.run_component_diagnostics("forecast_optimizer", self.forecast_optimizer),
            self.run_component_diagnostics("forecasting_engine", self.forecasting_engine),
            self.run_component_diagnostics("persistence_engine", self.persistence_engine),
        ]

        reports = [r for r in reports if r is not None]

        overall_health = self.calculate_health_score(reports)
        overall_risk = self.calculate_risk_score(reports)

        anomalies = self.detect_anomalies(reports)
        predicted_failures = self.predict_failures(reports)
        recommendations = self.generate_recommendations(
            reports,
            anomalies,
            predicted_failures,
        )

        report = FabricHealthReport(
            report_id=f"diag_{uuid.uuid4().hex}",
            generated_at=utc_now_iso(),
            overall_health_score=overall_health,
            overall_risk_score=overall_risk,
            state=self._health_state(overall_health),
            component_reports=reports,
            recommendations=recommendations,
            anomalies=anomalies,
            predicted_failures=predicted_failures,
        )

        self.last_report = report
        self.diagnostic_history.append(report)

        self._trim_history()

        return report

    def run_component_diagnostics(
        self,
        component_name: str,
        component: Any,
    ) -> ComponentDiagnostic:
        if component is None:
            finding = self._finding(
                component_name,
                DiagnosticSeverity.HIGH,
                "Component Missing",
                f"{component_name} is not registered.",
                "Verify bootstrap registration.",
            )

            return ComponentDiagnostic(
                component=component_name,
                health_score=0,
                risk_score=100,
                state=ComponentHealthState.FAILED.value,
                findings=[finding],
            )

        findings = []
        metrics = {}

        metrics["registered"] = True
        metrics["object_type"] = type(component).__name__

        health = 100.0
        risk = 0.0

        if hasattr(component, "health_score"):
            try:
                score = getattr(component, "health_score")

                if callable(score):
                    score = score()

                metrics["native_health"] = score

                if isinstance(score, (int, float)):
                    health = min(health, float(score))

            except Exception:
                pass

        if hasattr(component, "state"):
            metrics["state"] = str(getattr(component, "state"))

        if hasattr(component, "status"):
            metrics["status"] = str(getattr(component, "status"))

        if hasattr(component, "summary"):
            try:
                summary = component.summary()

                if isinstance(summary, dict):
                    metrics["summary"] = summary

            except Exception:
                pass

        if health < 90:
            findings.append(
                self._finding(
                    component_name,
                    DiagnosticSeverity.MEDIUM,
                    "Health Degradation",
                    f"{component_name} health below optimal.",
                    "Investigate component metrics.",
                )
            )

            risk += 15

        if health < 70:
            findings.append(
                self._finding(
                    component_name,
                    DiagnosticSeverity.HIGH,
                    "Component Degraded",
                    f"{component_name} health significantly degraded.",
                    "Trigger remediation workflow.",
                )
            )

            risk += 25

        if health < 50:
            findings.append(
                self._finding(
                    component_name,
                    DiagnosticSeverity.CRITICAL,
                    "Critical Health State",
                    f"{component_name} may require recovery.",
                    "Execute recovery orchestration.",
                )
            )

            risk += 40

        return ComponentDiagnostic(
            component=component_name,
            health_score=round(health, 2),
            risk_score=round(clamp(risk), 2),
            state=self._health_state(health),
            metrics=metrics,
            findings=findings,
        )

    def calculate_health_score(
        self,
        reports: List[ComponentDiagnostic],
    ) -> float:
        if not reports:
            return 0.0

        return round(
            statistics.mean(
                report.health_score
                for report in reports
            ),
            2,
        )

    def calculate_risk_score(
        self,
        reports: List[ComponentDiagnostic],
    ) -> float:
        if not reports:
            return 100.0

        return round(
            statistics.mean(
                report.risk_score
                for report in reports
            ),
            2,
        )

    def detect_anomalies(
        self,
        reports: List[ComponentDiagnostic],
    ) -> List[Dict[str, Any]]:
        anomalies = []

        for report in reports:
            if report.health_score < 70:
                anomalies.append(
                    {
                        "component": report.component,
                        "type": "health_degradation",
                        "health_score": report.health_score,
                    }
                )

            if report.risk_score > 50:
                anomalies.append(
                    {
                        "component": report.component,
                        "type": "high_risk",
                        "risk_score": report.risk_score,
                    }
                )

        return anomalies

    def predict_failures(
        self,
        reports: List[ComponentDiagnostic],
    ) -> List[Dict[str, Any]]:
        predictions = []

        for report in reports:
            if report.health_score < 50:
                predictions.append(
                    {
                        "component": report.component,
                        "probability": 0.85,
                        "reason": "Critical health score.",
                    }
                )
            elif report.health_score < 70:
                predictions.append(
                    {
                        "component": report.component,
                        "probability": 0.55,
                        "reason": "Degraded health score.",
                    }
                )

        return predictions

    def generate_recommendations(
        self,
        reports: List[ComponentDiagnostic],
        anomalies: List[Dict[str, Any]],
        predictions: List[Dict[str, Any]],
    ) -> List[str]:
        recommendations = []

        for anomaly in anomalies:
            recommendations.append(
                f"Investigate {anomaly['component']} anomaly."
            )

        for prediction in predictions:
            recommendations.append(
                f"Prepare recovery workflow for {prediction['component']}."
            )

        if not recommendations:
            recommendations.append(
                "All monitored Analytics Fabric components are healthy."
            )

        return sorted(set(recommendations))

    def generate_health_report(self) -> Dict[str, Any]:
        report = self.run_diagnostics()
        return report.as_dict()

    def generate_executive_health_report(self) -> Dict[str, Any]:
        report = self.run_diagnostics()

        return {
            "generated_at": report.generated_at,
            "overall_health_score": report.overall_health_score,
            "overall_risk_score": report.overall_risk_score,
            "state": report.state,
            "recommendation_count": len(report.recommendations),
            "anomaly_count": len(report.anomalies),
            "predicted_failure_count": len(report.predicted_failures),
            "top_recommendations": report.recommendations[:10],
        }

    def generate_control_plane_health_snapshot(self) -> Dict[str, Any]:
        report = self.run_diagnostics()

        return {
            "snapshot_id": f"snapshot_{uuid.uuid4().hex}",
            "created_at": utc_now_iso(),
            "overall_health_score": report.overall_health_score,
            "overall_risk_score": report.overall_risk_score,
            "state": report.state,
            "components": [
                {
                    "component": component.component,
                    "health_score": component.health_score,
                    "risk_score": component.risk_score,
                    "state": component.state,
                }
                for component in report.component_reports
            ],
        }

    # ============================================================
    # Utility
    # ============================================================

    def diagnostics_summary(self) -> Dict[str, Any]:
        return {
            "reports_generated": len(self.diagnostic_history),
            "findings_recorded": len(self.findings_history),
            "last_health_score": (
                self.last_report.overall_health_score
                if self.last_report
                else None
            ),
            "last_risk_score": (
                self.last_report.overall_risk_score
                if self.last_report
                else None
            ),
        }

    def _finding(
        self,
        component: str,
        severity: DiagnosticSeverity,
        title: str,
        description: str,
        recommendation: str,
    ) -> DiagnosticFinding:
        finding = DiagnosticFinding(
            finding_id=f"finding_{uuid.uuid4().hex}",
            component=component,
            severity=severity.value,
            title=title,
            description=description,
            recommendation=recommendation,
            created_at=utc_now_iso(),
        )

        self.findings_history.append(finding)

        return finding

    def _health_state(
        self,
        score: float,
    ) -> str:
        if score >= 90:
            return ComponentHealthState.HEALTHY.value

        if score >= 75:
            return ComponentHealthState.WARNING.value

        if score >= 50:
            return ComponentHealthState.DEGRADED.value

        if score >= 25:
            return ComponentHealthState.CRITICAL.value

        return ComponentHealthState.FAILED.value

    def _trim_history(self) -> None:
        if len(self.diagnostic_history) > 1000:
            self.diagnostic_history = self.diagnostic_history[-1000:]

        if len(self.findings_history) > 10000:
            self.findings_history = self.findings_history[-10000:]