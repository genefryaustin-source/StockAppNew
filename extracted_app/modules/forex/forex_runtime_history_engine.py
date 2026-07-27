"""
===============================================================================
forex_runtime_history_engine.py
Sprint 30 - Phase 2 (Part 3)
Runtime History Engine
===============================================================================
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from modules.forex.forex_runtime_history_models import (
    ForexRuntimeSnapshot,
    RuntimeTimeline,
)

from modules.forex.forex_runtime_history_repository import (
    get_forex_runtime_history_repository,
)

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _pct_change(old: float, new: float) -> float:
    old = _safe_float(old)
    new = _safe_float(new)

    if old == 0:
        return 0.0

    return ((new - old) / abs(old)) * 100.0


class ForexRuntimeHistoryEngine:
    """
    High-level historical intelligence layer for Forex runtime snapshots.

    This engine sits above the repository and provides dashboard-ready APIs.
    """

    def __init__(
        self,
        db=None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id

        self.repository = get_forex_runtime_history_repository(
            db=db,
        )

    # ---------------------------------------------------------------------
    # Timeline loading
    # ---------------------------------------------------------------------

    def load_latest_runtime(self) -> Dict[str, Any]:
        if not self.tenant_id:
            return {
                "status": "missing_tenant",
                "generated_at": _utc_now_iso(),
                "runtime": None,
            }

        snapshot = self.repository.load_latest_runtime(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

        return {
            "status": "success" if snapshot else "no_data",
            "generated_at": _utc_now_iso(),
            "runtime": snapshot.to_dict() if snapshot else None,
        }

    def load_user_timeline(self) -> Dict[str, Any]:
        if not self.tenant_id or not self.user_id:
            return {
                "status": "missing_identity",
                "generated_at": _utc_now_iso(),
                "timeline": {
                    "count": 0,
                    "snapshots": [],
                },
            }

        timeline = self.repository.load_history_for_user(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

        return {
            "status": "success",
            "generated_at": _utc_now_iso(),
            "timeline": timeline.to_dict(),
        }

    def load_portfolio_timeline(self) -> Dict[str, Any]:
        if not self.portfolio_id:
            return {
                "status": "missing_portfolio",
                "generated_at": _utc_now_iso(),
                "timeline": {
                    "count": 0,
                    "snapshots": [],
                },
            }

        timeline = self.repository.load_history_for_portfolio(
            portfolio_id=self.portfolio_id,
        )

        return {
            "status": "success",
            "generated_at": _utc_now_iso(),
            "timeline": timeline.to_dict(),
        }

    # ---------------------------------------------------------------------
    # Runtime replay
    # ---------------------------------------------------------------------

    def replay_runtime(
        self,
        runtime_id: str,
    ) -> Dict[str, Any]:

        timeline = self.repository.load_runtime_history(
            runtime_id=runtime_id,
        )

        return {
            "status": "success" if timeline.snapshots else "no_data",
            "generated_at": _utc_now_iso(),
            "runtime_id": runtime_id,
            "timeline": timeline.to_dict(),
            "summary": self._timeline_summary(timeline),
        }

    # ---------------------------------------------------------------------
    # Comparison
    # ---------------------------------------------------------------------

    def compare_latest_to_previous(self) -> Dict[str, Any]:
        if not self.tenant_id or not self.user_id:
            return {
                "status": "missing_identity",
                "generated_at": _utc_now_iso(),
                "comparison": {},
            }

        timeline = self.repository.load_history_for_user(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

        if len(timeline.snapshots) < 2:
            return {
                "status": "insufficient_history",
                "generated_at": _utc_now_iso(),
                "comparison": {},
            }

        previous = timeline.snapshots[-2]
        latest = timeline.snapshots[-1]

        return {
            "status": "success",
            "generated_at": _utc_now_iso(),
            "previous_runtime_id": previous.runtime_id,
            "latest_runtime_id": latest.runtime_id,
            "comparison": self._compare_snapshots(
                previous,
                latest,
            ),
        }

    # ---------------------------------------------------------------------
    # Trend APIs
    # ---------------------------------------------------------------------

    def provider_trends(self) -> Dict[str, Any]:
        timeline = self._active_timeline()

        rows: Dict[str, Dict[str, Any]] = {}

        for snapshot in timeline.snapshots:
            for provider in snapshot.provider_history:
                row = rows.setdefault(
                    provider.provider,
                    {
                        "provider": provider.provider,
                        "runs": 0,
                        "successes": 0,
                        "failures": 0,
                        "latency_total_ms": 0.0,
                        "quote_count": 0,
                        "latest_health_score": None,
                    },
                )

                row["runs"] += 1

                if provider.success:
                    row["successes"] += 1
                else:
                    row["failures"] += 1

                row["latency_total_ms"] += _safe_float(
                    provider.latency_ms
                )
                row["quote_count"] += int(provider.quote_count or 0)
                row["latest_health_score"] = provider.health_score

        output = []

        for row in rows.values():
            runs = max(row["runs"], 1)

            output.append(
                {
                    "provider": row["provider"],
                    "runs": row["runs"],
                    "successes": row["successes"],
                    "failures": row["failures"],
                    "success_rate": row["successes"] / runs,
                    "avg_latency_ms": row["latency_total_ms"] / runs,
                    "quote_count": row["quote_count"],
                    "latest_health_score": row["latest_health_score"],
                }
            )

        output.sort(
            key=lambda x: (
                -x["success_rate"],
                x["avg_latency_ms"],
            )
        )

        return {
            "status": "success",
            "generated_at": _utc_now_iso(),
            "providers": output,
        }

    def currency_strength_trends(self) -> Dict[str, Any]:
        timeline = self._active_timeline()

        rows: Dict[str, List[Dict[str, Any]]] = {}

        for snapshot in timeline.snapshots:
            for item in snapshot.currency_strength:
                rows.setdefault(
                    item.currency,
                    [],
                ).append(
                    item.to_dict()
                )

        summary = []

        for currency, values in rows.items():
            first = values[0]
            last = values[-1]

            first_strength = _safe_float(
                first.get("strength")
            )
            last_strength = _safe_float(
                last.get("strength")
            )

            summary.append(
                {
                    "currency": currency,
                    "observations": len(values),
                    "first_strength": first_strength,
                    "latest_strength": last_strength,
                    "strength_change": last_strength - first_strength,
                    "strength_change_pct": _pct_change(
                        first_strength,
                        last_strength,
                    ),
                    "latest_rank": last.get("rank"),
                    "latest_confidence": last.get("confidence"),
                }
            )

        summary.sort(
            key=lambda x: x["latest_strength"],
            reverse=True,
        )

        return {
            "status": "success",
            "generated_at": _utc_now_iso(),
            "currencies": summary,
            "series": rows,
        }

    def portfolio_trends(self) -> Dict[str, Any]:
        timeline = self._active_timeline()

        series = []

        for snapshot in timeline.snapshots:
            if not snapshot.portfolio_history:
                continue

            p = snapshot.portfolio_history

            series.append(
                {
                    "runtime_id": snapshot.runtime_id,
                    "created_at": snapshot.created_at.isoformat(),
                    "equity": p.equity,
                    "cash": p.cash,
                    "unrealized_pnl": p.unrealized_pnl,
                    "realized_pnl": p.realized_pnl,
                    "exposure": p.exposure,
                    "positions": p.positions,
                }
            )

        summary = {}

        if series:
            first = series[0]
            last = series[-1]

            summary = {
                "observations": len(series),
                "first_equity": first["equity"],
                "latest_equity": last["equity"],
                "equity_change": _safe_float(last["equity"])
                - _safe_float(first["equity"]),
                "equity_change_pct": _pct_change(
                    first["equity"],
                    last["equity"],
                ),
                "latest_exposure": last["exposure"],
                "latest_positions": last["positions"],
            }

        return {
            "status": "success" if series else "no_data",
            "generated_at": _utc_now_iso(),
            "summary": summary,
            "series": series,
        }

    def ai_signal_trends(self) -> Dict[str, Any]:
        timeline = self._active_timeline()

        rows = []

        for snapshot in timeline.snapshots:
            for item in snapshot.ai_history:
                rows.append(
                    {
                        "runtime_id": snapshot.runtime_id,
                        "created_at": snapshot.created_at.isoformat(),
                        "recommendation": item.recommendation,
                        "confidence": item.confidence,
                        "score": item.score,
                        "explanation": item.explanation,
                    }
                )

        if not rows:
            return {
                "status": "no_data",
                "generated_at": _utc_now_iso(),
                "signals": [],
                "summary": {},
            }

        avg_confidence = sum(
            _safe_float(x["confidence"])
            for x in rows
        ) / len(rows)

        avg_score = sum(
            _safe_float(x["score"])
            for x in rows
        ) / len(rows)

        recommendation_counts: Dict[str, int] = {}

        for row in rows:
            recommendation_counts[row["recommendation"]] = (
                recommendation_counts.get(
                    row["recommendation"],
                    0,
                )
                + 1
            )

        return {
            "status": "success",
            "generated_at": _utc_now_iso(),
            "summary": {
                "signal_count": len(rows),
                "avg_confidence": avg_confidence,
                "avg_score": avg_score,
                "recommendation_counts": recommendation_counts,
            },
            "signals": rows,
        }

    # ---------------------------------------------------------------------
    # Dashboard packet
    # ---------------------------------------------------------------------

    def build_dashboard_packet(self) -> Dict[str, Any]:
        timeline = self._active_timeline()

        return {
            "status": "success",
            "generated_at": _utc_now_iso(),
            "identity": {
                "tenant_id": self.tenant_id,
                "user_id": self.user_id,
                "portfolio_id": self.portfolio_id,
            },
            "timeline_summary": self._timeline_summary(
                timeline,
            ),
            "latest_runtime": (
                timeline.last.to_dict()
                if timeline.last
                else None
            ),
            "provider_trends": self.provider_trends(),
            "currency_strength_trends": self.currency_strength_trends(),
            "portfolio_trends": self.portfolio_trends(),
            "ai_signal_trends": self.ai_signal_trends(),
        }

    # ---------------------------------------------------------------------
    # internals
    # ---------------------------------------------------------------------

    def _active_timeline(self) -> RuntimeTimeline:
        if self.portfolio_id:
            return self.repository.load_history_for_portfolio(
                portfolio_id=self.portfolio_id,
            )

        if self.tenant_id and self.user_id:
            return self.repository.load_history_for_user(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )

        return RuntimeTimeline()

    def _timeline_summary(
        self,
        timeline: RuntimeTimeline,
    ) -> Dict[str, Any]:

        if not timeline.snapshots:
            return {
                "snapshot_count": 0,
                "first_runtime_id": None,
                "latest_runtime_id": None,
                "first_created_at": None,
                "latest_created_at": None,
            }

        first = timeline.first
        last = timeline.last

        return {
            "snapshot_count": len(timeline.snapshots),
            "first_runtime_id": first.runtime_id if first else None,
            "latest_runtime_id": last.runtime_id if last else None,
            "first_created_at": first.created_at.isoformat()
            if first
            else None,
            "latest_created_at": last.created_at.isoformat()
            if last
            else None,
        }

    def _compare_snapshots(
        self,
        previous: ForexRuntimeSnapshot,
        latest: ForexRuntimeSnapshot,
    ) -> Dict[str, Any]:

        prev_portfolio = previous.portfolio_history
        latest_portfolio = latest.portfolio_history

        portfolio_delta = {}

        if prev_portfolio and latest_portfolio:
            portfolio_delta = {
                "equity_change": _safe_float(latest_portfolio.equity)
                - _safe_float(prev_portfolio.equity),
                "equity_change_pct": _pct_change(
                    prev_portfolio.equity,
                    latest_portfolio.equity,
                ),
                "exposure_change": _safe_float(latest_portfolio.exposure)
                - _safe_float(prev_portfolio.exposure),
                "position_count_change": int(
                    latest_portfolio.positions or 0
                )
                - int(prev_portfolio.positions or 0),
            }

        return {
            "runtime": {
                "previous_runtime_id": previous.runtime_id,
                "latest_runtime_id": latest.runtime_id,
                "previous_created_at": previous.created_at.isoformat(),
                "latest_created_at": latest.created_at.isoformat(),
            },
            "portfolio_delta": portfolio_delta,
            "provider_delta": {
                "previous_provider_count": len(
                    previous.provider_history
                ),
                "latest_provider_count": len(
                    latest.provider_history
                ),
            },
            "currency_strength_delta": {
                "previous_currency_count": len(
                    previous.currency_strength
                ),
                "latest_currency_count": len(
                    latest.currency_strength
                ),
            },
            "ai_delta": {
                "previous_signal_count": len(
                    previous.ai_history
                ),
                "latest_signal_count": len(
                    latest.ai_history
                ),
            },
        }


_ENGINE = None


def get_forex_runtime_history_engine(
    db=None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
) -> ForexRuntimeHistoryEngine:

    global _ENGINE

    if (
        _ENGINE is None
        or getattr(_ENGINE, "db", None) is not db
        or getattr(_ENGINE, "tenant_id", None) != tenant_id
        or getattr(_ENGINE, "user_id", None) != user_id
        or getattr(_ENGINE, "portfolio_id", None) != portfolio_id
    ):
        _ENGINE = ForexRuntimeHistoryEngine(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

    return _ENGINE