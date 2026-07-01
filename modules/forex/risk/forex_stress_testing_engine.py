# =============================================================================
# File: modules/forex/risk/forex_stress_testing_engine.py
#
# Sprint 30
# Phase 4C-3-3-2-3
#
# Build 1.1
#
# Institutional Stress Testing Engine
#
# Foundation
# =============================================================================

from __future__ import annotations

import json
import logging
import statistics
import uuid

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from enum import Enum
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import numpy as np

from sqlalchemy import text

logger = logging.getLogger(__name__)


# =============================================================================
# Helpers
# =============================================================================

def utc_now():

    return datetime.now(timezone.utc)


def utc_now_iso():

    return utc_now().isoformat()


def round4(value):

    try:

        return round(float(value), 4)

    except Exception:

        return 0.0


# =============================================================================
# Stress Scenario Types
# =============================================================================

class StressScenario(Enum):

    RATE_SHOCK = "RATE_SHOCK"

    USD_SURGE = "USD_SURGE"

    USD_COLLAPSE = "USD_COLLAPSE"

    VOLATILITY_SPIKE = "VOLATILITY_SPIKE"

    FLASH_CRASH = "FLASH_CRASH"

    LIQUIDITY_CRISIS = "LIQUIDITY_CRISIS"

    CENTRAL_BANK = "CENTRAL_BANK"

    RECESSION = "RECESSION"

    INFLATION = "INFLATION"

    CARRY_UNWIND = "CARRY_UNWIND"

    CORRELATION_BREAKDOWN = "CORRELATION_BREAKDOWN"

    CUSTOM = "CUSTOM"


# =============================================================================
# Scenario Definition
# =============================================================================

@dataclass

class StressScenarioDefinition:

    scenario: StressScenario

    title: str

    description: str

    shock_pct: float

    volatility_multiplier: float

    liquidity_haircut: float

    metadata: Dict[str, Any] = field(

        default_factory=dict

    )


# =============================================================================
# Stress Result
# =============================================================================

@dataclass

class StressTestResult:

    runtime_id: str

    scenario: str

    portfolio_before: float

    portfolio_after: float

    pnl: float

    pnl_pct: float

    volatility_before: float

    volatility_after: float

    survivability_score: float

    passed: bool

    generated_at: str

    metadata: Dict[str, Any] = field(

        default_factory=dict

    )

    def to_dict(self):

        return {

            "runtime_id":

                self.runtime_id,

            "scenario":

                self.scenario,

            "portfolio_before":

                self.portfolio_before,

            "portfolio_after":

                self.portfolio_after,

            "pnl":

                self.pnl,

            "pnl_pct":

                self.pnl_pct,

            "volatility_before":

                self.volatility_before,

            "volatility_after":

                self.volatility_after,

            "survivability_score":

                self.survivability_score,

            "passed":

                self.passed,

            "generated_at":

                self.generated_at,

            "metadata":

                self.metadata,

        }


# =============================================================================
# Stress Testing Engine
# =============================================================================

class ForexStressTestingEngine:

    def __init__(

        self,

        db=None,

        portfolio=None,

        tenant_id=None,

        user_id=None,

        portfolio_id=None,

    ):

        self.db = db

        self.portfolio = portfolio

        self.tenant_id = tenant_id

        self.user_id = user_id

        self.portfolio_id = portfolio_id

        self.runtime_id = str(

            uuid.uuid4()

        )

        self.scenarios = {}

        self.results = []

        self.statistics = {

            "runs": 0,

            "passed": 0,

            "failed": 0,

        }

        self._load_default_scenarios()

    # ------------------------------------------------------------------
    # Load Default Scenario Library
    # ------------------------------------------------------------------

    def _load_default_scenarios(self):

        defaults = [

            (

                StressScenario.RATE_SHOCK,

                "Interest Rate Shock",

                "Global rate increase",

                -0.03,

                1.40,

                0.02,

            ),

            (

                StressScenario.USD_SURGE,

                "USD Surge",

                "Rapid USD appreciation",

                -0.05,

                1.80,

                0.05,

            ),

            (

                StressScenario.USD_COLLAPSE,

                "USD Collapse",

                "Rapid USD depreciation",

                0.05,

                1.60,

                0.03,

            ),

            (

                StressScenario.FLASH_CRASH,

                "Flash Crash",

                "Extreme market event",

                -0.12,

                3.20,

                0.20,

            ),

            (

                StressScenario.VOLATILITY_SPIKE,

                "Volatility Spike",

                "Institutional volatility event",

                -0.08,

                2.50,

                0.10,

            ),

            (

                StressScenario.LIQUIDITY_CRISIS,

                "Liquidity Crisis",

                "Market liquidity disappears",

                -0.10,

                2.20,

                0.25,

            ),

        ]

        for item in defaults:

            definition = StressScenarioDefinition(

                scenario=item[0],

                title=item[1],

                description=item[2],

                shock_pct=item[3],

                volatility_multiplier=item[4],

                liquidity_haircut=item[5],

            )

            self.scenarios[

                definition.scenario.value

            ] = definition

    # ------------------------------------------------------------------
    # Register Scenario
    # ------------------------------------------------------------------

    def register_scenario(

        self,

        definition: StressScenarioDefinition,

    ):

        self.scenarios[

            definition.scenario.value

        ] = definition

    # ------------------------------------------------------------------
    # List Scenarios
    # ------------------------------------------------------------------

    def available_scenarios(self):

        return sorted(

            self.scenarios.keys()

        )

    # ------------------------------------------------------------------
    # Get Scenario
    # ------------------------------------------------------------------

    def get_scenario(

        self,

        name,

    ):

        return self.scenarios.get(

            name

        )

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(self):

        return {

            "status": "healthy",

            "runtime_id": self.runtime_id,

            "tenant_id": self.tenant_id,

            "user_id": self.user_id,

            "portfolio_id": self.portfolio_id,

            "scenario_count": len(

                self.scenarios

            ),

            "runs": self.statistics["runs"],

        }

        # =============================================================================
        # File: modules/forex/risk/forex_stress_testing_engine.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-3
        #
        # Build 1.2
        #
        # Continue Immediately After Build 1.1
        #
        # Stress Scenario Execution Engine
        # =============================================================================

        # ------------------------------------------------------------------
        # Portfolio Value
        # ------------------------------------------------------------------

        def portfolio_value(self):

            if self.portfolio is None:
                return 0.0

            if hasattr(

                    self.portfolio,

                    "total_market_value",

            ):
                return float(

                    self.portfolio.total_market_value()

                )

            return float(

                getattr(

                    self.portfolio,

                    "market_value",

                    0.0,

                )

            )

        # ------------------------------------------------------------------
        # Portfolio Volatility
        # ------------------------------------------------------------------

        def portfolio_volatility(self):

            if self.portfolio is None:
                return 0.0

            if hasattr(

                    self.portfolio,

                    "portfolio_volatility",

            ):
                return float(

                    self.portfolio.portfolio_volatility()

                )

            if hasattr(

                    self.portfolio,

                    "volatility",

            ):
                return float(

                    self.portfolio.volatility

                )

            return 0.15

        # ------------------------------------------------------------------
        # Survivability
        # ------------------------------------------------------------------

        def survivability_score(

                self,

                portfolio_after,

        ):

            before = self.portfolio_value()

            if before <= 0:
                return 0.0

            ratio = portfolio_after / before

            score = ratio * 100.0

            score = max(

                0.0,

                min(

                    100.0,

                    score,

                ),

            )

            return round4(score)

        # ------------------------------------------------------------------
        # Apply Scenario
        # ------------------------------------------------------------------

        def apply_scenario(

                self,

                definition: StressScenarioDefinition,

        ) -> StressTestResult:

            before = self.portfolio_value()

            after = before * (

                    1.0 +

                    definition.shock_pct

            )

            pnl = after - before

            pnl_pct = (

                pnl / before

                if before

                else 0.0

            )

            vol_before = (

                self.portfolio_volatility()

            )

            vol_after = (

                    vol_before *

                    definition.volatility_multiplier

            )

            score = self.survivability_score(

                after

            )

            passed = score >= 60.0

            result = StressTestResult(

                runtime_id=self.runtime_id,

                scenario=definition.scenario.value,

                portfolio_before=before,

                portfolio_after=after,

                pnl=pnl,

                pnl_pct=pnl_pct,

                volatility_before=vol_before,

                volatility_after=vol_after,

                survivability_score=score,

                passed=passed,

                generated_at=utc_now_iso(),

                metadata={

                    "title":

                        definition.title,

                    "description":

                        definition.description,

                    "shock_pct":

                        definition.shock_pct,

                    "liquidity_haircut":

                        definition.liquidity_haircut,

                },

            )

            self.results.append(

                result

            )

            self.statistics[

                "runs"

            ] += 1

            if passed:

                self.statistics[

                    "passed"

                ] += 1

            else:

                self.statistics[

                    "failed"

                ] += 1

            return result

        # ------------------------------------------------------------------
        # Execute Scenario
        # ------------------------------------------------------------------

        def execute(

                self,

                scenario_name: str,

        ):

            definition = self.get_scenario(

                scenario_name

            )

            if definition is None:
                raise ValueError(

                    f"Unknown scenario: {scenario_name}"

                )

            return self.apply_scenario(

                definition

            )

        # ------------------------------------------------------------------
        # Execute All
        # ------------------------------------------------------------------

        def execute_all(self):

            results = []

            for scenario in self.available_scenarios():
                results.append(

                    self.execute(

                        scenario

                    )

                )

            return results

        # ------------------------------------------------------------------
        # Results
        # ------------------------------------------------------------------

        def latest_results(self):

            return [

                r.to_dict()

                for r in self.results

            ]

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------

        def summary(self):

            if not self.results:
                self.execute_all()

            worst = min(

                self.results,

                key=lambda x: x.pnl_pct,

            )

            best = max(

                self.results,

                key=lambda x: x.pnl_pct,

            )

            return {

                "runtime_id":

                    self.runtime_id,

                "scenario_count":

                    len(

                        self.results

                    ),

                "passed":

                    self.statistics[

                        "passed"

                    ],

                "failed":

                    self.statistics[

                        "failed"

                    ],

                "worst_case":

                    worst.to_dict(),

                "best_case":

                    best.to_dict(),

                "generated_at":

                    utc_now_iso(),

            }