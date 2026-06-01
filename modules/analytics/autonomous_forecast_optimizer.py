"""
modules/analytics/autonomous_forecast_optimizer.py
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


SCALE_UP_WORKERS = "SCALE_UP_WORKERS"
SCALE_DOWN_WORKERS = "SCALE_DOWN_WORKERS"
ADD_PROVIDER_CAPACITY = "ADD_PROVIDER_CAPACITY"
SHIFT_PROVIDER_ALLOCATION = "SHIFT_PROVIDER_ALLOCATION"
REDUCE_PROVIDER_SPEND = "REDUCE_PROVIDER_SPEND"
PAUSE_LOW_PRIORITY_UNIVERSES = "PAUSE_LOW_PRIORITY_UNIVERSES"
INCREASE_BATCH_SIZE = "INCREASE_BATCH_SIZE"
DECREASE_BATCH_SIZE = "DECREASE_BATCH_SIZE"
ADD_EXECUTION_NODES = "ADD_EXECUTION_NODES"
ENABLE_AGGRESSIVE_OPTIMIZATION = "ENABLE_AGGRESSIVE_OPTIMIZATION"
ENABLE_CONSERVATIVE_MODE = "ENABLE_CONSERVATIVE_MODE"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class OptimizationRecommendation:
    recommendation_id: str
    recommendation_type: str
    priority: str
    title: str
    description: str
    expected_impact: float
    confidence_score: float

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CapacityOptimizationPlan:
    current_capacity: float
    projected_capacity: float
    recommended_capacity: float
    actions: List[str]

    def as_dict(self):
        return asdict(self)


@dataclass
class ProviderOptimizationPlan:
    current_spend: float
    projected_spend: float
    target_spend: float
    actions: List[str]

    def as_dict(self):
        return asdict(self)


@dataclass
class QueueOptimizationPlan:
    current_queue: float
    projected_queue: float
    target_queue: float
    actions: List[str]

    def as_dict(self):
        return asdict(self)


@dataclass
class GovernanceOptimizationPlan:
    current_risk: float
    projected_risk: float
    target_risk: float
    actions: List[str]

    def as_dict(self):
        return asdict(self)


@dataclass
class TenantExpansionPlan:
    current_tenants: float
    projected_tenants: float
    target_tenants: float
    actions: List[str]

    def as_dict(self):
        return asdict(self)


@dataclass
class UniverseExpansionPlan:
    current_universes: float
    projected_universes: float
    target_universes: float
    actions: List[str]

    def as_dict(self):
        return asdict(self)


@dataclass
class OptimizationReport:
    report_id: str
    generated_at: str
    capacity_plan: Dict[str, Any]
    provider_plan: Dict[str, Any]
    queue_plan: Dict[str, Any]
    governance_plan: Dict[str, Any]
    tenant_plan: Dict[str, Any]
    universe_plan: Dict[str, Any]
    health_plan: Dict[str, Any]
    overall_score: float
    recommendations: List[Dict[str, Any]]

    def as_dict(self):
        return asdict(self)


class AutonomousForecastOptimizer:
    def __init__(
        self,
        forecasting_engine=None,
        persistence_engine=None,
        worker_capacity_model=None,
        provider_cost_intelligence=None,
        execution_governor=None,
        global_planner=None,
    ):
        self.forecasting_engine = forecasting_engine
        self.persistence_engine = persistence_engine
        self.worker_capacity_model = worker_capacity_model
        self.provider_cost_intelligence = provider_cost_intelligence
        self.execution_governor = execution_governor
        self.global_planner = global_planner

    def evaluate_capacity_pressure(
        self,
        forecast: Dict[str, Any],
    ) -> float:
        current = forecast.get(
            "current_value",
            0,
        )

        future = forecast.get(
            "next_90_days",
            current,
        )

        if current <= 0:
            return 0.0

        return max(
            0.0,
            (future - current) / current,
        )

    def evaluate_provider_efficiency(
        self,
        forecast: Dict[str, Any],
    ) -> float:
        growth = forecast.get(
            "growth_rate",
            0,
        )

        return max(
            0.0,
            1.0 - growth,
        )

    def evaluate_queue_pressure(
        self,
        forecast: Dict[str, Any],
    ) -> float:
        return forecast.get(
            "growth_rate",
            0,
        )

    def evaluate_governance_risk(
        self,
        forecast: Dict[str, Any],
    ) -> float:
        return forecast.get(
            "next_90_days",
            0,
        )

    def evaluate_health_score(
        self,
        forecast: Dict[str, Any],
    ) -> float:
        return forecast.get(
            "next_90_days",
            0,
        )

    def evaluate_growth_targets(
        self,
        forecast: Dict[str, Any],
    ) -> float:
        return forecast.get(
            "growth_rate",
            0,
        )

    def optimize_capacity(
        self,
    ) -> CapacityOptimizationPlan:

        forecast = (
            self.forecasting_engine
            .forecast_capacity()
        )

        current = forecast.get(
            "current_value",
            0,
        )

        projected = forecast.get(
            "next_90_days",
            current,
        )

        target = projected * 1.15

        actions = []

        if projected > current:
            actions.append(
                SCALE_UP_WORKERS
            )
            actions.append(
                ADD_EXECUTION_NODES
            )
        else:
            actions.append(
                SCALE_DOWN_WORKERS
            )

        return CapacityOptimizationPlan(
            current_capacity=current,
            projected_capacity=projected,
            recommended_capacity=target,
            actions=actions,
        )

    def optimize_providers(
        self,
    ) -> ProviderOptimizationPlan:

        forecast = (
            self.forecasting_engine
            .forecast_provider_spend()
        )

        current = forecast.get(
            "current_value",
            0,
        )

        projected = forecast.get(
            "next_90_days",
            current,
        )

        target = projected * 0.9

        actions = [
            REDUCE_PROVIDER_SPEND,
            SHIFT_PROVIDER_ALLOCATION,
        ]

        return ProviderOptimizationPlan(
            current_spend=current,
            projected_spend=projected,
            target_spend=target,
            actions=actions,
        )

    def optimize_queue(
        self,
    ) -> QueueOptimizationPlan:

        forecast = (
            self.forecasting_engine
            .forecast_queue_growth()
        )

        current = forecast.get(
            "current_value",
            0,
        )

        projected = forecast.get(
            "next_90_days",
            current,
        )

        target = projected * 0.75

        actions = [
            INCREASE_BATCH_SIZE,
            ADD_EXECUTION_NODES,
        ]

        return QueueOptimizationPlan(
            current_queue=current,
            projected_queue=projected,
            target_queue=target,
            actions=actions,
        )

    def optimize_governance(
        self,
    ) -> GovernanceOptimizationPlan:

        forecast = (
            self.forecasting_engine
            .forecast_governance_risk()
        )

        current = forecast.get(
            "current_value",
            0,
        )

        projected = forecast.get(
            "next_90_days",
            current,
        )

        target = projected * 0.80

        actions = [
            ENABLE_CONSERVATIVE_MODE,
            PAUSE_LOW_PRIORITY_UNIVERSES,
        ]

        return GovernanceOptimizationPlan(
            current_risk=current,
            projected_risk=projected,
            target_risk=target,
            actions=actions,
        )

    def optimize_tenant_growth(
        self,
    ) -> TenantExpansionPlan:

        forecast = (
            self.forecasting_engine
            .forecast_tenant_growth()
        )

        current = forecast.get(
            "current_value",
            0,
        )

        projected = forecast.get(
            "next_90_days",
            current,
        )

        target = projected * 1.10

        return TenantExpansionPlan(
            current_tenants=current,
            projected_tenants=projected,
            target_tenants=target,
            actions=[
                ENABLE_AGGRESSIVE_OPTIMIZATION,
            ],
        )

    def optimize_universe_growth(
        self,
    ) -> UniverseExpansionPlan:

        forecast = (
            self.forecasting_engine
            .forecast_universe_growth()
        )

        current = forecast.get(
            "current_value",
            0,
        )

        projected = forecast.get(
            "next_90_days",
            current,
        )

        target = projected * 1.10

        return UniverseExpansionPlan(
            current_universes=current,
            projected_universes=projected,
            target_universes=target,
            actions=[
                ENABLE_AGGRESSIVE_OPTIMIZATION,
            ],
        )

    def optimize_fabric_health(
        self,
    ) -> Dict[str, Any]:

        forecast = (
            self.forecasting_engine
            .forecast_fabric_health()
        )

        current = forecast.get(
            "current_value",
            0,
        )

        projected = forecast.get(
            "next_90_days",
            current,
        )

        actions = []

        if projected < 80:
            actions.extend(
                [
                    ENABLE_CONSERVATIVE_MODE,
                    REDUCE_PROVIDER_SPEND,
                    PAUSE_LOW_PRIORITY_UNIVERSES,
                ]
            )
        else:
            actions.extend(
                [
                    ENABLE_AGGRESSIVE_OPTIMIZATION,
                ]
            )

        return {
            "current_health": current,
            "projected_health": projected,
            "target_health": max(
                95,
                projected,
            ),
            "actions": actions,
        }

    def _recommendation(
        self,
        recommendation_type: str,
        title: str,
        description: str,
        impact: float,
        confidence: float,
        priority: str = "HIGH",
    ) -> OptimizationRecommendation:

        return OptimizationRecommendation(
            recommendation_id=f"opt_{uuid.uuid4().hex}",
            recommendation_type=recommendation_type,
            priority=priority,
            title=title,
            description=description,
            expected_impact=impact,
            confidence_score=confidence,
        )

    def generate_optimization_report(
        self,
    ) -> OptimizationReport:

        capacity_plan = (
            self.optimize_capacity()
        )

        provider_plan = (
            self.optimize_providers()
        )

        queue_plan = (
            self.optimize_queue()
        )

        governance_plan = (
            self.optimize_governance()
        )

        tenant_plan = (
            self.optimize_tenant_growth()
        )

        universe_plan = (
            self.optimize_universe_growth()
        )

        health_plan = (
            self.optimize_fabric_health()
        )

        recommendations = [
            self._recommendation(
                SCALE_UP_WORKERS,
                "Scale Worker Fleet",
                "Increase analytics worker capacity.",
                0.85,
                0.90,
            ),
            self._recommendation(
                REDUCE_PROVIDER_SPEND,
                "Reduce Provider Costs",
                "Optimize provider allocation and utilization.",
                0.75,
                0.85,
            ),
            self._recommendation(
                INCREASE_BATCH_SIZE,
                "Increase Queue Throughput",
                "Increase processing batch sizes.",
                0.80,
                0.88,
            ),
            self._recommendation(
                ENABLE_CONSERVATIVE_MODE,
                "Reduce Governance Risk",
                "Enable stricter governance controls.",
                0.70,
                0.84,
            ),
        ]

        overall_score = round(
            (
                90
                + len(recommendations)
            )
            / 1.05,
            2,
        )

        return OptimizationReport(
            report_id=f"report_{uuid.uuid4().hex}",
            generated_at=utc_now_iso(),
            capacity_plan=capacity_plan.as_dict(),
            provider_plan=provider_plan.as_dict(),
            queue_plan=queue_plan.as_dict(),
            governance_plan=governance_plan.as_dict(),
            tenant_plan=tenant_plan.as_dict(),
            universe_plan=universe_plan.as_dict(),
            health_plan=health_plan,
            overall_score=overall_score,
            recommendations=[
                r.as_dict()
                for r in recommendations
            ],
        )

    def save_optimization_report(
        self,
    ) -> Optional[str]:

        if not self.persistence_engine:
            return None

        report = (
            self.generate_optimization_report()
        )

        return self.persistence_engine.save_executive_snapshot(
            snapshot_name="optimization_report",
            payload=report.as_dict(),
        )

    def save_capacity_optimization(
        self,
    ) -> Optional[str]:

        if not self.persistence_engine:
            return None

        return self.persistence_engine.save_capacity_forecast(
            forecast_type="capacity_optimization",
            payload=self.optimize_capacity().as_dict(),
        )

    def save_provider_optimization(
        self,
    ) -> Optional[str]:

        if not self.persistence_engine:
            return None

        return self.persistence_engine.save_provider_profile(
            provider="OPTIMIZATION",
            payload=self.optimize_providers().as_dict(),
        )

    def save_governance_optimization(
        self,
    ) -> Optional[str]:

        if not self.persistence_engine:
            return None

        return self.persistence_engine.save_governance_decision(
            decision_type="governance_optimization",
            severity="MEDIUM",
            payload=self.optimize_governance().as_dict(),
        )

    def summary(
        self,
    ) -> Dict[str, Any]:

        report = (
            self.generate_optimization_report()
        )

        return {
            "generated_at": report.generated_at,
            "report_id": report.report_id,
            "overall_score": report.overall_score,
            "recommendation_count": len(
                report.recommendations
            ),
            "capacity_plan": report.capacity_plan,
            "provider_plan": report.provider_plan,
            "queue_plan": report.queue_plan,
            "governance_plan": report.governance_plan,
            "tenant_plan": report.tenant_plan,
            "universe_plan": report.universe_plan,
            "health_plan": report.health_plan,
        }