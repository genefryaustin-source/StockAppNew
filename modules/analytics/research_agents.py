"""
modules/analytics/research_agents.py

Institutional multi-agent research intelligence system.

Phase 1:
- base agent framework
- specialized research agents
- consensus orchestration
- institutional rationale synthesis

Future:
- autonomous collaboration
- agent memory
- reinforcement learning
- cross-agent negotiation
- autonomous thesis generation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime, UTC
import math

from modules.analytics.agent_memory import (
    AgentMemoryRecord,
    get_agent_memory_store,
)


# ---------------------------------------------------
# BASE DATA MODELS
# ---------------------------------------------------

@dataclass
class AgentDecision:

    agent_name: str

    symbol: str

    score: float
    confidence: float

    bullish_factors: List[str] = field(default_factory=list)

    bearish_factors: List[str] = field(default_factory=list)

    risk_flags: List[str] = field(default_factory=list)

    rationale: str = ""

    metadata: Dict[str, Any] = field(default_factory=dict)

    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )


@dataclass
class ConsensusResult:

    symbol: str

    consensus_score: float

    consensus_confidence: float

    agent_count: int

    bullish_factors: List[str]

    bearish_factors: List[str]

    risk_flags: List[str]

    summary: str

    decisions: List[AgentDecision]

    generated_at: datetime


# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:

        if value is None:
            return default

        value = float(value)

        if math.isnan(value):
            return default

        if math.isinf(value):
            return default

        return value

    except Exception:

        return default


def _clamp(
    value: float,
    low: float = 0.0,
    high: float = 100.0,
) -> float:

    return max(low, min(high, value))


# ---------------------------------------------------
# BASE AGENT
# ---------------------------------------------------

class BaseResearchAgent:

    AGENT_NAME = "base"

    def evaluate(
        self,
        symbol: str,
        context: Dict[str, Any],
    ) -> AgentDecision:

        raise NotImplementedError


# ---------------------------------------------------
# NEWS AGENT
# ---------------------------------------------------

class NewsAgent(BaseResearchAgent):

    AGENT_NAME = "news_agent"

    def evaluate(
        self,
        symbol: str,
        context: Dict[str, Any],
    ) -> AgentDecision:

        sentiment_score = _safe_float(
            context.get("sentiment_score"),
            50.0,
        )

        market_tone = str(
            context.get("market_tone", "neutral")
        )

        catalysts = context.get(
            "catalysts",
            [],
        )

        risks = context.get(
            "risks",
            [],
        )

        confidence = min(
            100.0,
            55.0 + (
                len(catalysts) * 4
            )
        )

        rationale = (
            f"Market tone is {market_tone}. "
            f"Detected {len(catalysts)} bullish "
            f"catalysts and {len(risks)} risks."
        )

        return AgentDecision(

            agent_name=self.AGENT_NAME,

            symbol=symbol,

            score=sentiment_score,

            confidence=confidence,

            bullish_factors=list(catalysts),

            bearish_factors=list(risks),

            risk_flags=list(risks),

            rationale=rationale,
        )


# ---------------------------------------------------
# EARNINGS AGENT
# ---------------------------------------------------

class EarningsAgent(BaseResearchAgent):

    AGENT_NAME = "earnings_agent"

    def evaluate(
        self,
        symbol: str,
        context: Dict[str, Any],
    ) -> AgentDecision:

        guidance = _safe_float(
            context.get("guidance_score"),
            50.0,
        )

        ceo_conf = _safe_float(
            context.get("ceo_confidence"),
            50.0,
        )

        risk_pressure = _safe_float(
            context.get("risk_pressure"),
            50.0,
        )

        score = (
            guidance * 0.45
        ) + (
            ceo_conf * 0.40
        ) - (
            risk_pressure * 0.25
        )

        score = _clamp(score)

        confidence = min(
            100.0,
            60.0 + (
                ceo_conf * 0.25
            )
        )

        rationale = (
            f"Guidance score={guidance}, "
            f"CEO confidence={ceo_conf}, "
            f"risk pressure={risk_pressure}."
        )

        return AgentDecision(

            agent_name=self.AGENT_NAME,

            symbol=symbol,

            score=score,

            confidence=confidence,

            bullish_factors=[
                "executive confidence"
            ] if ceo_conf > 65 else [],

            bearish_factors=[
                "guidance deterioration"
            ] if guidance < 45 else [],

            risk_flags=[
                "earnings risk"
            ] if risk_pressure > 65 else [],

            rationale=rationale,
        )


# ---------------------------------------------------
# TECHNICAL AGENT
# ---------------------------------------------------

class TechnicalAgent(BaseResearchAgent):

    AGENT_NAME = "technical_agent"

    def evaluate(
        self,
        symbol: str,
        context: Dict[str, Any],
    ) -> AgentDecision:

        momentum = _safe_float(
            context.get("momentum"),
            50.0,
        )

        volatility = _safe_float(
            context.get("volatility"),
            25.0,
        )

        trend_strength = _safe_float(
            context.get("trend_strength"),
            50.0,
        )

        score = (
            momentum * 0.45
        ) + (
            trend_strength * 0.40
        ) - (
            volatility * 0.20
        )

        score = _clamp(score)

        confidence = min(
            100.0,
            50.0 + (
                trend_strength * 0.35
            )
        )

        rationale = (
            f"Momentum={momentum}, "
            f"trend strength={trend_strength}, "
            f"volatility={volatility}."
        )

        bullish = []

        bearish = []

        if momentum > 70:
            bullish.append(
                "strong momentum"
            )

        if trend_strength > 70:
            bullish.append(
                "strong trend"
            )

        if volatility > 70:
            bearish.append(
                "high volatility"
            )

        return AgentDecision(

            agent_name=self.AGENT_NAME,

            symbol=symbol,

            score=score,

            confidence=confidence,

            bullish_factors=bullish,

            bearish_factors=bearish,

            risk_flags=bearish,

            rationale=rationale,
        )


# ---------------------------------------------------
# MACRO AGENT
# ---------------------------------------------------

class MacroAgent(BaseResearchAgent):

    AGENT_NAME = "macro_agent"

    def evaluate(
        self,
        symbol: str,
        context: Dict[str, Any],
    ) -> AgentDecision:

        regime = str(
            context.get(
                "market_regime",
                "neutral",
            )
        )

        sector = str(
            context.get(
                "sector",
                "Unknown",
            )
        )

        base_score = 50.0

        bullish = []

        bearish = []

        if regime == "bull":

            base_score += 20

            bullish.append(
                "bull market regime"
            )

        elif regime == "bear":

            base_score -= 15

            bearish.append(
                "bear market regime"
            )

        elif regime == "panic":

            base_score -= 25

            bearish.append(
                "panic regime"
            )

        confidence = 75.0

        rationale = (
            f"Market regime={regime}, "
            f"sector={sector}."
        )

        return AgentDecision(

            agent_name=self.AGENT_NAME,

            symbol=symbol,

            score=_clamp(base_score),

            confidence=confidence,

            bullish_factors=bullish,

            bearish_factors=bearish,

            risk_flags=bearish,

            rationale=rationale,
        )


# ---------------------------------------------------
# RISK AGENT
# ---------------------------------------------------

class RiskAgent(BaseResearchAgent):

    AGENT_NAME = "risk_agent"

    def evaluate(
        self,
        symbol: str,
        context: Dict[str, Any],
    ) -> AgentDecision:

        risk_score = _safe_float(
            context.get("risk"),
            50.0,
        )

        leverage = _safe_float(
            context.get("leverage"),
            0.0,
        )

        volatility = _safe_float(
            context.get("volatility"),
            25.0,
        )

        penalty = (
            risk_score * 0.50
        ) + (
            leverage * 0.20
        ) + (
            volatility * 0.30
        )

        score = 100.0 - penalty

        score = _clamp(score)

        confidence = 80.0

        risks = []

        if risk_score > 70:
            risks.append(
                "elevated risk"
            )

        if leverage > 60:
            risks.append(
                "high leverage"
            )

        if volatility > 70:
            risks.append(
                "extreme volatility"
            )

        rationale = (
            f"Risk score={risk_score}, "
            f"leverage={leverage}, "
            f"volatility={volatility}."
        )

        return AgentDecision(

            agent_name=self.AGENT_NAME,

            symbol=symbol,

            score=score,

            confidence=confidence,

            bearish_factors=risks,

            risk_flags=risks,

            rationale=rationale,
        )


# ---------------------------------------------------
# FUNDAMENTALS AGENT
# ---------------------------------------------------

class FundamentalsAgent(BaseResearchAgent):

    AGENT_NAME = "fundamentals_agent"

    def evaluate(
        self,
        symbol: str,
        context: Dict[str, Any],
    ) -> AgentDecision:

        quality = _safe_float(
            context.get("quality"),
            50.0,
        )

        growth = _safe_float(
            context.get("growth"),
            50.0,
        )

        value = _safe_float(
            context.get("value"),
            50.0,
        )

        score = (
            quality * 0.40
        ) + (
            growth * 0.35
        ) + (
            value * 0.25
        )

        score = _clamp(score)

        confidence = min(
            100.0,
            50.0 + (
                quality * 0.40
            )
        )

        bullish = []

        if quality > 70:
            bullish.append(
                "high quality"
            )

        if growth > 70:
            bullish.append(
                "strong growth"
            )

        if value > 70:
            bullish.append(
                "attractive valuation"
            )

        rationale = (
            f"Quality={quality}, "
            f"growth={growth}, "
            f"value={value}."
        )

        return AgentDecision(

            agent_name=self.AGENT_NAME,

            symbol=symbol,

            score=score,

            confidence=confidence,

            bullish_factors=bullish,

            rationale=rationale,
        )


# ---------------------------------------------------
# RESEARCH COORDINATOR
# ---------------------------------------------------

class ResearchCoordinator:

    def __init__(self):

        self.agents = [

            NewsAgent(),

            EarningsAgent(),

            TechnicalAgent(),

            MacroAgent(),

            RiskAgent(),

            FundamentalsAgent(),
        ]

        self.memory = (
            get_agent_memory_store()
        )

    def evaluate_symbol(
        self,
        symbol: str,
        context: Dict[str, Any],
    ) -> ConsensusResult:

        decisions = []

        for agent in self.agents:

            try:

                decision = agent.evaluate(
                    symbol=symbol,
                    context=context,
                )

                decisions.append(decision)
                try:

                    memory_record = AgentMemoryRecord(

                        symbol=symbol,

                        agent_name=decision.agent_name,

                        decision_score=decision.score,

                        confidence=decision.confidence,

                        market_regime=str(
                            context.get(
                                "market_regime",
                                "unknown",
                            )
                        ),

                        thesis=decision.rationale,

                        metadata={

                            "bullish_factors":
                                decision.bullish_factors,

                            "bearish_factors":
                                decision.bearish_factors,

                            "risk_flags":
                                decision.risk_flags,
                        },
                    )

                    self.memory.add_record(
                        memory_record
                    )

                except Exception as e:

                    print(
                        "AGENT MEMORY ERROR",
                        symbol,
                        e,
                    )

            except Exception as e:

                print(
                    "AGENT ERROR",
                    agent.AGENT_NAME,
                    symbol,
                    e,
                )

        if not decisions:

            return ConsensusResult(

                symbol=symbol,

                consensus_score=50.0,

                consensus_confidence=0.0,

                agent_count=0,

                bullish_factors=[],

                bearish_factors=[],

                risk_flags=[],

                summary="No agent decisions available.",

                decisions=[],

                generated_at=datetime.now(UTC),
            )
        reliability = (
            self.memory.compute_agent_weights()
        )
        weighted_scores = []

        weighted_confidences = []

        for d in decisions:
            weight = reliability.get(
                d.agent_name,
                1.0,
            )

            weighted_scores.append(
                d.score * weight
            )

            weighted_confidences.append(
                d.confidence * weight
            )

        if weighted_scores:

            consensus_score = (
                    sum(weighted_scores)
                    / sum(reliability.values())
            )

        else:

            consensus_score = 50.0

        if weighted_confidences:

            consensus_confidence = (
                    sum(weighted_confidences)
                    / sum(reliability.values())
            )

        else:

            consensus_confidence = 50.0

        bullish = []

        bearish = []

        risks = []

        rationales = []

        for d in decisions:

            bullish.extend(
                d.bullish_factors
            )

            bearish.extend(
                d.bearish_factors
            )

            risks.extend(
                d.risk_flags
            )

            rationales.append(
                f"{d.agent_name}: {d.rationale}"
            )

        summary = " | ".join(rationales)
        if reliability:
            summary += (
                f" | Agent reliability "
                f"weighting active."
            )
        return ConsensusResult(

            symbol=symbol,

            consensus_score=round(
                consensus_score,
                4,
            ),

            consensus_confidence=round(
                consensus_confidence,
                4,
            ),

            agent_count=len(decisions),

            bullish_factors=sorted(
                list(set(bullish))
            ),

            bearish_factors=sorted(
                list(set(bearish))
            ),

            risk_flags=sorted(
                list(set(risks))
            ),

            summary=summary,

            decisions=decisions,

            generated_at=datetime.now(UTC),
        )


# ---------------------------------------------------
# BATCH CONSENSUS
# ---------------------------------------------------

def evaluate_symbols_with_agents(
    symbols_context: Dict[str, Dict[str, Any]],
) -> Dict[str, ConsensusResult]:

    coordinator = ResearchCoordinator()

    results = {}

    for symbol, context in symbols_context.items():

        try:

            results[symbol] = (
                coordinator.evaluate_symbol(
                    symbol=symbol,
                    context=context,
                )
            )

        except Exception as e:

            print(
                "RESEARCH COORDINATOR ERROR",
                symbol,
                e,
            )

    return results
# ---------------------------------------------------
# CONSENSUS OVERLAY MAP
# ---------------------------------------------------

def consensus_results_to_overlay_map(
    results: Dict[str, ConsensusResult],
) -> Dict[str, float]:

    overlay = {}

    for symbol, r in results.items():

        normalized = (
            (r.consensus_score - 50.0)
            / 50.0
        )

        confidence_adj = (
            r.consensus_confidence
            / 100.0
        )

        overlay[symbol] = round(
            normalized * confidence_adj,
            4,
        )

    return overlay