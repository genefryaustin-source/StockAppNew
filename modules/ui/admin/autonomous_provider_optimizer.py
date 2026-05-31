"""
modules/market_data/autonomous_provider_optimizer.py
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any, Dict, List

from modules.market_data.provider_router import (
    get_provider_router,
)

from modules.market_data.provider_intelligence_engine import (
    get_provider_intelligence_engine,
)


class AutonomousProviderOptimizer:
    def __init__(self):
        self.router = get_provider_router()
        self.intelligence = get_provider_intelligence_engine()

    def build_optimization_plan(self) -> Dict[str, Any]:
        analyses = self.intelligence.analyze_all_providers()

        actions: List[Dict[str, Any]] = []

        for row in analyses:
            provider = row["provider"]
            recommendation = row["recommendation"]
            health = float(row.get("health_score") or 0)
            rate_limits = int(row.get("rate_limits") or 0)
            failures = int(row.get("failures") or 0)

            if recommendation == "FAILOVER":
                actions.append({
                    "provider": provider,
                    "action": "DISABLE_PROVIDER",
                    "reason": f"Health score below failover threshold: {health:.1f}",
                    "severity": "HIGH",
                })

            elif recommendation == "REDUCE_TRAFFIC":
                actions.append({
                    "provider": provider,
                    "action": "APPLY_COOLDOWN",
                    "reason": f"Rate limit count elevated: {rate_limits}",
                    "severity": "MEDIUM",
                })

            elif recommendation == "DEGRADED":
                actions.append({
                    "provider": provider,
                    "action": "DEPRIORITIZE",
                    "reason": f"Provider degraded. Health={health:.1f}, failures={failures}",
                    "severity": "LOW",
                })

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "actions": actions,
        }

    def optimize(
        self,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        plan = self.build_optimization_plan()

        applied = []

        for action in plan.get("actions", []):
            provider = action["provider"]
            action_type = action["action"]

            if dry_run:
                applied.append({
                    **action,
                    "applied": False,
                    "mode": "DRY_RUN",
                })
                continue

            if action_type == "DISABLE_PROVIDER":
                self.router.disable_provider(provider)
                applied.append({
                    **action,
                    "applied": True,
                })

            elif action_type == "APPLY_COOLDOWN":
                self.router.mark_rate_limited(
                    provider,
                    cooldown_minutes=30,
                )
                applied.append({
                    **action,
                    "applied": True,
                })

            elif action_type == "DEPRIORITIZE":
                self.router.mark_failure(provider)
                applied.append({
                    **action,
                    "applied": True,
                })

        return {
            "generated_at": plan["generated_at"],
            "dry_run": dry_run,
            "actions_found": len(plan.get("actions", [])),
            "actions": applied,
        }


_optimizer = None


def get_autonomous_provider_optimizer():
    global _optimizer

    if _optimizer is None:
        _optimizer = AutonomousProviderOptimizer()

    return _optimizer