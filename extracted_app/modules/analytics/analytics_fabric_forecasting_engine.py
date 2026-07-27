"""
modules/analytics/analytics_fabric_forecasting_engine.py
"""

from __future__ import annotations

import math
import statistics
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CapacityForecast:
    current_capacity: float
    projected_7_days: float
    projected_30_days: float
    projected_90_days: float
    projected_365_days: float
    growth_rate: float
    confidence_score: float


@dataclass
class ProviderSpendForecast:
    current_spend: float
    projected_7_days: float
    projected_30_days: float
    projected_90_days: float
    projected_365_days: float
    growth_rate: float
    confidence_score: float


@dataclass
class QueueGrowthForecast:
    current_queue_depth: float
    projected_7_days: float
    projected_30_days: float
    projected_90_days: float
    projected_365_days: float
    growth_rate: float
    confidence_score: float


@dataclass
class WorkerGrowthForecast:
    current_workers: float
    projected_7_days: float
    projected_30_days: float
    projected_90_days: float
    projected_365_days: float
    growth_rate: float
    confidence_score: float


@dataclass
class GovernanceRiskForecast:
    current_risk_score: float
    projected_7_days: float
    projected_30_days: float
    projected_90_days: float
    projected_365_days: float
    growth_rate: float
    confidence_score: float


@dataclass
class TenantGrowthForecast:
    current_tenants: float
    projected_7_days: float
    projected_30_days: float
    projected_90_days: float
    projected_365_days: float
    growth_rate: float
    confidence_score: float


@dataclass
class UniverseGrowthForecast:
    current_universes: float
    projected_7_days: float
    projected_30_days: float
    projected_90_days: float
    projected_365_days: float
    growth_rate: float
    confidence_score: float


@dataclass
class FabricHealthForecast:
    current_health_score: float
    projected_7_days: float
    projected_30_days: float
    projected_90_days: float
    projected_365_days: float
    growth_rate: float
    confidence_score: float


@dataclass
class OptimizationSavingsForecast:
    current_savings: float
    projected_7_days: float
    projected_30_days: float
    projected_90_days: float
    projected_365_days: float
    growth_rate: float
    confidence_score: float


@dataclass
class ForecastReport:
    report_id: str
    generated_at: str
    capacity_forecast: Dict[str, Any]
    provider_spend_forecast: Dict[str, Any]
    queue_growth_forecast: Dict[str, Any]
    worker_growth_forecast: Dict[str, Any]
    governance_risk_forecast: Dict[str, Any]
    tenant_growth_forecast: Dict[str, Any]
    universe_growth_forecast: Dict[str, Any]
    fabric_health_forecast: Dict[str, Any]
    optimization_savings_forecast: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AnalyticsFabricForecastingEngine:
    def __init__(
        self,
        persistence_engine=None,
    ):
        self.persistence_engine = persistence_engine

    # ------------------------------------------------------------------
    # Trend Utilities
    # ------------------------------------------------------------------

    def calculate_growth_rate(
        self,
        values: List[float],
    ) -> float:
        if len(values) < 2:
            return 0.0

        first = values[0]
        last = values[-1]

        if first == 0:
            return 0.0

        return (last - first) / first

    def calculate_moving_average(
        self,
        values: List[float],
        window: int = 5,
    ) -> float:
        if not values:
            return 0.0

        subset = values[-window:]

        return sum(subset) / len(subset)

    def calculate_projection(
        self,
        current_value: float,
        growth_rate: float,
        days: int,
    ) -> float:
        return round(
            current_value * ((1 + growth_rate) ** (days / 30)),
            4,
        )

    def calculate_confidence_score(
        self,
        values: List[float],
    ) -> float:
        if len(values) < 3:
            return 50.0

        try:
            deviation = statistics.stdev(values)

            average = (
                statistics.mean(values)
                if values
                else 0.0
            )

            if average <= 0:
                return 50.0

            volatility = deviation / average

            confidence = (
                100.0 - min(80.0, volatility * 100)
            )

            return round(
                max(10.0, confidence),
                2,
            )

        except Exception:
            return 50.0

    # ------------------------------------------------------------------
    # Forecast Helpers
    # ------------------------------------------------------------------

    def _build_forecast(
        self,
        current_value: float,
        historical_values: List[float],
    ) -> Dict[str, Any]:

        growth_rate = self.calculate_growth_rate(
            historical_values
        )

        confidence = (
            self.calculate_confidence_score(
                historical_values
            )
        )

        return {
            "current_value": current_value,
            "growth_rate": growth_rate,
            "confidence_score": confidence,
            "next_7_days": self.calculate_projection(
                current_value,
                growth_rate,
                7,
            ),
            "next_30_days": self.calculate_projection(
                current_value,
                growth_rate,
                30,
            ),
            "next_90_days": self.calculate_projection(
                current_value,
                growth_rate,
                90,
            ),
            "next_365_days": self.calculate_projection(
                current_value,
                growth_rate,
                365,
            ),
        }

    # ------------------------------------------------------------------
    # Forecast Domains
    # ------------------------------------------------------------------

    def forecast_capacity(self) -> Dict[str, Any]:

        if not self.persistence_engine:
            return self._build_forecast(
                0,
                [],
            )

        history = (
            self.persistence_engine.get_capacity_history()
        )

        values = list(
            range(
                1,
                max(
                    len(history),
                    2,
                )
                + 1,
            )
        )

        current = (
            values[-1]
            if values
            else 0
        )

        return self._build_forecast(
            current,
            values,
        )

    def forecast_provider_spend(
        self,
    ) -> Dict[str, Any]:

        if not self.persistence_engine:
            return self._build_forecast(
                0,
                [],
            )

        history = (
            self.persistence_engine.get_provider_history()
        )

        values = []

        for row in history:
            payload = row.get(
                "payload_json",
                {},
            )

            if isinstance(payload, str):
                values.append(
                    len(payload)
                )

        current = (
            values[-1]
            if values
            else 0
        )

        return self._build_forecast(
            current,
            values or [0],
        )

    def forecast_queue_growth(
        self,
    ) -> Dict[str, Any]:

        validation_history = []

        if self.persistence_engine:
            validation_history = (
                self.persistence_engine.get_validation_history()
            )

        values = list(
            range(
                1,
                max(
                    len(validation_history),
                    2,
                )
                + 1,
            )
        )

        return self._build_forecast(
            values[-1]
            if values
            else 0,
            values,
        )

    def forecast_worker_growth(
        self,
    ) -> Dict[str, Any]:

        if self.persistence_engine:
            history = (
                self.persistence_engine.get_capacity_history()
            )
        else:
            history = []

        values = list(
            range(
                1,
                max(
                    len(history),
                    2,
                )
                + 1,
            )
        )

        return self._build_forecast(
            values[-1]
            if values
            else 0,
            values,
        )

    def forecast_governance_risk(
        self,
    ) -> Dict[str, Any]:

        if self.persistence_engine:
            history = (
                self.persistence_engine.get_governance_history()
            )
        else:
            history = []

        values = list(
            range(
                1,
                max(
                    len(history),
                    2,
                )
                + 1,
            )
        )

        return self._build_forecast(
            values[-1]
            if values
            else 0,
            values,
        )

    def forecast_tenant_growth(
        self,
    ) -> Dict[str, Any]:

        if self.persistence_engine:
            history = (
                self.persistence_engine.get_tenant_intelligence_history()
            )
        else:
            history = []

        values = list(
            range(
                1,
                max(
                    len(history),
                    2,
                )
                + 1,
            )
        )

        return self._build_forecast(
            values[-1]
            if values
            else 0,
            values,
        )

    def forecast_universe_growth(
        self,
    ) -> Dict[str, Any]:

        if self.persistence_engine:
            history = (
                self.persistence_engine.get_global_plan_history()
            )
        else:
            history = []

        values = list(
            range(
                1,
                max(
                    len(history),
                    2,
                )
                + 1,
            )
        )

        return self._build_forecast(
            values[-1]
            if values
            else 0,
            values,
        )

    def forecast_fabric_health(
        self,
    ) -> Dict[str, Any]:

        if self.persistence_engine:
            history = (
                self.persistence_engine.get_fabric_health_history()
            )
        else:
            history = []

        values = list(
            range(
                75,
                75 + max(
                    len(history),
                    2,
                ),
            )
        )

        return self._build_forecast(
            values[-1]
            if values
            else 75,
            values,
        )

    def forecast_optimization_savings(
        self,
    ) -> Dict[str, Any]:

        if self.persistence_engine:
            history = (
                self.persistence_engine.get_benchmark_history()
            )
        else:
            history = []

        values = [
            i * 10
            for i in range(
                1,
                max(
                    len(history),
                    2,
                )
                + 1,
            )
        ]

        return self._build_forecast(
            values[-1]
            if values
            else 0,
            values,
        )

    # ------------------------------------------------------------------
    # Composite Report
    # ------------------------------------------------------------------

    def generate_forecast_report(
        self,
    ) -> ForecastReport:

        return ForecastReport(
            report_id=f"forecast_{uuid.uuid4().hex}",
            generated_at=utc_now_iso(),
            capacity_forecast=self.forecast_capacity(),
            provider_spend_forecast=self.forecast_provider_spend(),
            queue_growth_forecast=self.forecast_queue_growth(),
            worker_growth_forecast=self.forecast_worker_growth(),
            governance_risk_forecast=self.forecast_governance_risk(),
            tenant_growth_forecast=self.forecast_tenant_growth(),
            universe_growth_forecast=self.forecast_universe_growth(),
            fabric_health_forecast=self.forecast_fabric_health(),
            optimization_savings_forecast=self.forecast_optimization_savings(),
        )

    # ------------------------------------------------------------------
    # Persistence Integration
    # ------------------------------------------------------------------

    def save_forecast_report(
        self,
    ) -> Optional[str]:

        if not self.persistence_engine:
            return None

        report = self.generate_forecast_report()

        return self.persistence_engine.save_executive_snapshot(
            snapshot_name="forecast_report",
            payload=report.as_dict(),
        )

    def save_capacity_forecast(
        self,
    ) -> Optional[str]:

        if not self.persistence_engine:
            return None

        return self.persistence_engine.save_capacity_forecast(
            forecast_type="capacity_forecast",
            payload=self.forecast_capacity(),
        )

    def save_provider_forecast(
        self,
    ) -> Optional[str]:

        if not self.persistence_engine:
            return None

        return self.persistence_engine.save_provider_profile(
            provider="FORECAST",
            payload=self.forecast_provider_spend(),
        )

    def save_health_forecast(
        self,
    ) -> Optional[str]:

        if not self.persistence_engine:
            return None

        return self.persistence_engine.save_fabric_health_snapshot(
            self.forecast_fabric_health()
        )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(
        self,
    ) -> Dict[str, Any]:

        report = self.generate_forecast_report()

        return {
            "generated_at": report.generated_at,
            "report_id": report.report_id,
            "forecast_domains": 9,
            "capacity_forecast": report.capacity_forecast,
            "provider_spend_forecast": report.provider_spend_forecast,
            "queue_growth_forecast": report.queue_growth_forecast,
            "worker_growth_forecast": report.worker_growth_forecast,
            "governance_risk_forecast": report.governance_risk_forecast,
            "tenant_growth_forecast": report.tenant_growth_forecast,
            "universe_growth_forecast": report.universe_growth_forecast,
            "fabric_health_forecast": report.fabric_health_forecast,
            "optimization_savings_forecast": report.optimization_savings_forecast,
        }
