# =============================================================================
# Risk Event Correlation Engine
# Sprint 30
# Phase 4C-3-3-1
# =============================================================================

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# =============================================================================
# Helpers
# =============================================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Event Types
# =============================================================================

EVENT_PROVIDER_FAILURE = "provider_failure"
EVENT_PROVIDER_RECOVERY = "provider_recovery"
EVENT_HIGH_LATENCY = "high_latency"
EVENT_QUOTE_REFRESH = "quote_refresh"

EVENT_AI_SIGNAL = "ai_signal"

EVENT_REGIME_CHANGE = "regime_change"

EVENT_RISK_CHANGE = "risk_change"

EVENT_PORTFOLIO_CHANGE = "portfolio_change"

EVENT_EXPOSURE_CHANGE = "exposure_change"

EVENT_MARGIN_WARNING = "margin_warning"

EVENT_DRAWDOWN = "drawdown"

EVENT_VOLATILITY_SPIKE = "volatility_spike"

EVENT_CURRENCY_ROTATION = "currency_rotation"


# =============================================================================
# Event
# =============================================================================

@dataclass(slots=True)
class RiskEvent:

    runtime_id: str

    event_type: str

    severity: str

    timestamp: str

    source: str

    description: str

    score: float = 0.0

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


# =============================================================================
# Correlation
# =============================================================================

@dataclass(slots=True)
class RiskCorrelation:

    event_a: str

    event_b: str

    occurrences: int

    correlation_score: float

    confidence: float

    first_seen: Optional[str] = None

    last_seen: Optional[str] = None


# =============================================================================
# Engine
# =============================================================================

class ForexRiskEventCorrelationEngine:

    def __init__(self):

        self.events: List[RiskEvent] = []

    # ---------------------------------------------------------------------
    # Register
    # ---------------------------------------------------------------------

    def register_event(

        self,

        runtime_id: str,

        event_type: str,

        severity: str,

        source: str,

        description: str,

        score: float = 0.0,

        metadata=None,

    ):

        self.events.append(

            RiskEvent(

                runtime_id=runtime_id,

                event_type=event_type,

                severity=severity,

                timestamp=utc_now_iso(),

                source=source,

                description=description,

                score=score,

                metadata=metadata or {},

            )

        )

    # ---------------------------------------------------------------------
    # Timeline
    # ---------------------------------------------------------------------

    def timeline(

        self,

        runtime_id: Optional[str] = None,

    ):

        rows=[]

        for e in self.events:

            if runtime_id:

                if e.runtime_id != runtime_id:
                    continue

            rows.append({

                "runtime_id":e.runtime_id,

                "timestamp":e.timestamp,

                "event":e.event_type,

                "severity":e.severity,

                "source":e.source,

                "description":e.description,

                "score":e.score,

            })

        rows.sort(

            key=lambda x:x["timestamp"]

        )

        return rows

    # ---------------------------------------------------------------------
    # Statistics
    # ---------------------------------------------------------------------

    def event_statistics(self):

        counts=defaultdict(int)

        severity=defaultdict(int)

        for e in self.events:

            counts[e.event_type]+=1

            severity[e.severity]+=1

        return {

            "events":len(self.events),

            "by_type":dict(counts),

            "by_severity":dict(severity),

        }

    # ---------------------------------------------------------------------
    # Correlation Matrix
    # ---------------------------------------------------------------------

    def correlation_matrix(self):

        runtime_events=defaultdict(set)

        for e in self.events:

            runtime_events[
                e.runtime_id
            ].add(
                e.event_type
            )

        pairs=defaultdict(int)

        event_counts=defaultdict(int)

        for events in runtime_events.values():

            events=list(events)

            for e in events:

                event_counts[e]+=1

            for i in range(len(events)):

                for j in range(i+1,len(events)):

                    pair=tuple(

                        sorted(

                            [

                                events[i],

                                events[j],

                            ]

                        )

                    )

                    pairs[pair]+=1

        matrix=[]

        total=max(

            len(runtime_events),

            1,

        )

        for pair,count in pairs.items():

            matrix.append(

                RiskCorrelation(

                    event_a=pair[0],

                    event_b=pair[1],

                    occurrences=count,

                    correlation_score=

                        count/total,

                    confidence=

                        min(

                            1.0,

                            count/5,

                        ),

                )

            )

        matrix.sort(

            key=lambda x:x.correlation_score,

            reverse=True,

        )

        return matrix

    # ---------------------------------------------------------------------
    # Top Correlations
    # ---------------------------------------------------------------------

    def strongest_correlations(

        self,

        limit=10,

    ):

        rows=[]

        for c in self.correlation_matrix():

            rows.append({

                "event_a":

                    c.event_a,

                "event_b":

                    c.event_b,

                "occurrences":

                    c.occurrences,

                "correlation":

                    round(

                        c.correlation_score,

                        3,

                    ),

                "confidence":

                    round(

                        c.confidence,

                        3,

                    ),

            })

        return rows[:limit]

    # ---------------------------------------------------------------------
    # Provider Failure Correlations
    # ---------------------------------------------------------------------

    def provider_failure_analysis(self):

        failures=[]

        for e in self.events:

            if e.event_type!=EVENT_PROVIDER_FAILURE:

                continue

            failures.append(e.score)

        if not failures:

            return {}

        return {

            "count":

                len(failures),

            "average":

                statistics.mean(

                    failures

                ),

            "maximum":

                max(

                    failures

                ),

            "minimum":

                min(

                    failures

                ),

        }

    # ---------------------------------------------------------------------
    # AI Correlations
    # ---------------------------------------------------------------------

    def ai_signal_analysis(self):

        ai=[]

        for e in self.events:

            if e.event_type==EVENT_AI_SIGNAL:

                ai.append(e.score)

        if not ai:

            return {}

        return {

            "signals":

                len(ai),

            "average_score":

                statistics.mean(ai),

            "highest_score":

                max(ai),

            "lowest_score":

                min(ai),

        }

    # ---------------------------------------------------------------------
    # Volatility Analysis
    # ---------------------------------------------------------------------

    def volatility_analysis(self):

        spikes=[]

        for e in self.events:

            if e.event_type==EVENT_VOLATILITY_SPIKE:

                spikes.append(e.score)

        if not spikes:

            return {}

        return {

            "spikes":

                len(spikes),

            "average":

                statistics.mean(spikes),

            "maximum":

                max(spikes),

        }

    # ---------------------------------------------------------------------
    # Dashboard Packet
    # ---------------------------------------------------------------------

    def build_dashboard_packet(self):

        return {

            "status":"success",

            "generated_at":

                utc_now_iso(),

            "statistics":

                self.event_statistics(),

            "timeline":

                self.timeline(),

            "correlations":

                self.strongest_correlations(),

            "provider":

                self.provider_failure_analysis(),

            "ai":

                self.ai_signal_analysis(),

            "volatility":

                self.volatility_analysis(),

        }


# =============================================================================
# Singleton
# =============================================================================

_ENGINE=None


def get_forex_risk_event_correlation_engine():

    global _ENGINE

    if _ENGINE is None:

        _ENGINE=ForexRiskEventCorrelationEngine()

    return _ENGINE