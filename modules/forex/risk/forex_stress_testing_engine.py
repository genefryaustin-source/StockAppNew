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

        self.ensure_tables()

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

        if not self.results:
            self.execute_all()

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

    # ==========================================================================
    # Methods below were recovered from forex_var_repository.py, where they had
    # been wrongly nested (their own header comment even said
    # 'File: forex_stress_testing_engine.py') instead of living in this class.
    # ==========================================================================

    def apply_multi_factor(

            self,

            scenarios: List[str],

    ) -> StressTestResult:

        portfolio_before = self.portfolio_value()

        portfolio_after = portfolio_before

        volatility = self.portfolio_volatility()

        metadata = {}

        for name in scenarios:

            definition = self.get_scenario(name)

            if definition is None:
                continue

            portfolio_after *= (

                    1.0 +

                    definition.shock_pct

            )

            volatility *= (

                definition.volatility_multiplier

            )

            metadata[name] = {

                "shock":

                    definition.shock_pct,

                "volatility":

                    definition.volatility_multiplier,

            }

        pnl = portfolio_after - portfolio_before

        pnl_pct = (

            pnl / portfolio_before

            if portfolio_before

            else 0.0

        )

        score = self.survivability_score(

            portfolio_after

        )

        result = StressTestResult(

            runtime_id=self.runtime_id,

            scenario="MULTI_FACTOR",

            portfolio_before=portfolio_before,

            portfolio_after=portfolio_after,

            pnl=pnl,

            pnl_pct=pnl_pct,

            volatility_before=self.portfolio_volatility(),

            volatility_after=volatility,

            survivability_score=score,

            passed=score >= 55,

            generated_at=utc_now_iso(),

            metadata=metadata,

        )

        self.results.append(result)

        self.statistics["runs"] += 1

        if result.passed:

            self.statistics["passed"] += 1

        else:

            self.statistics["failed"] += 1

        return result

    def correlation_breakdown(self):

        return self.apply_multi_factor(

            [

                StressScenario.VOLATILITY_SPIKE.value,

                StressScenario.CORRELATION_BREAKDOWN.value,

            ]

        )

    def central_bank_crisis(self):

        return self.apply_multi_factor(

            [

                StressScenario.CENTRAL_BANK.value,

                StressScenario.USD_SURGE.value,

                StressScenario.VOLATILITY_SPIKE.value,

            ]

        )

    def carry_trade_unwind(self):

        return self.apply_multi_factor(

            [

                StressScenario.CARRY_UNWIND.value,

                StressScenario.USD_SURGE.value,

                StressScenario.LIQUIDITY_CRISIS.value,

            ]

        )

    def inflation_crisis(self):

        return self.apply_multi_factor(

            [

                StressScenario.INFLATION.value,

                StressScenario.RATE_SHOCK.value,

            ]

        )

    def recession_scenario(self):

        return self.apply_multi_factor(

            [

                StressScenario.RECESSION.value,

                StressScenario.LIQUIDITY_CRISIS.value,

                StressScenario.VOLATILITY_SPIKE.value,

            ]

        )

    def institutional_crisis(self):

        return self.apply_multi_factor(

            [

                StressScenario.FLASH_CRASH.value,

                StressScenario.LIQUIDITY_CRISIS.value,

                StressScenario.VOLATILITY_SPIKE.value,

                StressScenario.CORRELATION_BREAKDOWN.value,

            ]

        )

    def execute_crisis_suite(self):

        return [

            self.central_bank_crisis(),

            self.carry_trade_unwind(),

            self.inflation_crisis(),

            self.recession_scenario(),

            self.institutional_crisis(),

        ]

    def crisis_ranking(self):

        ranking = []

        for result in self.execute_crisis_suite():
            ranking.append(

                result.to_dict()

            )

        ranking.sort(

            key=lambda x:

            x["pnl_pct"]

        )

        return ranking

    def institutional_score(self):

        ranking = self.crisis_ranking()

        if not ranking:
            return 100.0

        losses = [

            abs(

                r["pnl_pct"]

            )

            for r in ranking

        ]

        score = 100.0 - (

                statistics.mean(losses)

                * 100.0

        )

        return max(

            0.0,

            round4(score),

        )

    def institutional_summary(self):

        return {

            "runtime_id":

                self.runtime_id,

            "score":

                self.institutional_score(),

            "ranking":

                self.crisis_ranking(),

            "generated_at":

                utc_now_iso(),

        }

    def historical_crises(self):

        return [

            {
                "name": "Asian Financial Crisis",
                "year": 1997,
                "shock": -0.18,
                "volatility": 2.60,
                "liquidity": 0.18,
            },

            {
                "name": "Russian Default",
                "year": 1998,
                "shock": -0.21,
                "volatility": 3.10,
                "liquidity": 0.25,
            },

            {
                "name": "Dot-Com Collapse",
                "year": 2000,
                "shock": -0.16,
                "volatility": 2.30,
                "liquidity": 0.12,
            },

            {
                "name": "Global Financial Crisis",
                "year": 2008,
                "shock": -0.42,
                "volatility": 4.20,
                "liquidity": 0.35,
            },

            {
                "name": "Swiss Franc Unpeg",
                "year": 2015,
                "shock": -0.28,
                "volatility": 5.10,
                "liquidity": 0.18,
            },

            {
                "name": "Brexit Referendum",
                "year": 2016,
                "shock": -0.13,
                "volatility": 2.40,
                "liquidity": 0.08,
            },

            {
                "name": "COVID Crash",
                "year": 2020,
                "shock": -0.35,
                "volatility": 3.80,
                "liquidity": 0.28,
            },

            {
                "name": "UK Gilt Crisis",
                "year": 2022,
                "shock": -0.12,
                "volatility": 2.50,
                "liquidity": 0.15,
            },

        ]

    def replay_crisis(

            self,

            crisis_name,

    ):

        before = self.portfolio_value()

        for crisis in self.historical_crises():

            if crisis["name"] != crisis_name:
                continue

            after = before * (

                    1.0 +

                    crisis["shock"]

            )

            pnl = after - before

            pnl_pct = (

                pnl / before

                if before

                else 0.0

            )

            result = StressTestResult(

                runtime_id=self.runtime_id,

                scenario=crisis_name,

                portfolio_before=before,

                portfolio_after=after,

                pnl=pnl,

                pnl_pct=pnl_pct,

                volatility_before=self.portfolio_volatility(),

                volatility_after=(

                        self.portfolio_volatility()

                        * crisis["volatility"]

                ),

                survivability_score=self.survivability_score(

                    after

                ),

                passed=after > before * 0.60,

                generated_at=utc_now_iso(),

                metadata=crisis,

            )

            self.results.append(

                result

            )

            self.statistics["runs"] += 1

            return result

        raise ValueError(

            f"Unknown crisis: {crisis_name}"

        )

    def replay_all_crises(self):

        results = []

        for crisis in self.historical_crises():
            results.append(

                self.replay_crisis(

                    crisis["name"]

                )

            )

        return results

    def crisis_statistics(self):

        results = self.replay_all_crises()

        losses = [

            abs(r.pnl_pct)

            for r in results

        ]

        survivability = [

            r.survivability_score

            for r in results

        ]

        return {

            "crises":

                len(results),

            "average_loss":

                round4(

                    statistics.mean(losses)

                ),

            "maximum_loss":

                round4(

                    max(losses)

                ),

            "minimum_loss":

                round4(

                    min(losses)

                ),

            "average_survivability":

                round4(

                    statistics.mean(

                        survivability

                    )

                ),

        }

    def historical_crisis_ranking(self):

        ranking = []

        for result in self.replay_all_crises():
            ranking.append(

                result.to_dict()

            )

        ranking.sort(

            key=lambda row:

            row["pnl_pct"]

        )

        return ranking

    def historical_dashboard_packet(self):

        return {

            "status":

                "success",

            "generated_at":

                utc_now_iso(),

            "statistics":

                self.crisis_statistics(),

            "ranking":

                self.historical_crisis_ranking(),

            "results":

                [

                    r.to_dict()

                    for r in

                    self.results

                ],

        }

    def ensure_tables(self):

        if self.db is None:
            return

        try:
            bind = getattr(self.db, "bind", None) or getattr(self.db, "get_bind", lambda: None)()
            dialect = bind.dialect.name if bind is not None else "unknown"
        except Exception:
            dialect = "unknown"

        id_column = (
            "id INTEGER PRIMARY KEY AUTOINCREMENT"
            if dialect == "sqlite"
            else "id SERIAL PRIMARY KEY"
        )

        self.db.execute(text(f"""

        CREATE TABLE IF NOT EXISTS forex_stress_test_history(

            {id_column},

            tenant_id VARCHAR(120),

            user_id VARCHAR(120),

            portfolio_id VARCHAR(120),

            runtime_id VARCHAR(120),

            scenario VARCHAR(120),

            survivability_score DOUBLE PRECISION,

            pnl DOUBLE PRECISION,

            pnl_pct DOUBLE PRECISION,

            volatility_before DOUBLE PRECISION,

            volatility_after DOUBLE PRECISION,

            passed BOOLEAN,

            generated_at TIMESTAMP,

            payload JSONB,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        );

        """))

        if hasattr(self.db, "commit"):
            self.db.commit()

    def persist_result(

            self,

            result: StressTestResult,

    ):

        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(

            text("""

            INSERT INTO forex_stress_test_history(

                tenant_id,

                user_id,

                portfolio_id,

                runtime_id,

                scenario,

                survivability_score,

                pnl,

                pnl_pct,

                volatility_before,

                volatility_after,

                passed,

                generated_at,

                payload

            )

            VALUES(

                :tenant,

                :user,

                :portfolio,

                :runtime,

                :scenario,

                :score,

                :pnl,

                :pct,

                :vol_before,

                :vol_after,

                :passed,

                :generated,

                CAST(:payload AS JSONB)

            )

            """),

            {

                "tenant":

                    self.tenant_id,

                "user":

                    self.user_id,

                "portfolio":

                    self.portfolio_id,

                "runtime":

                    result.runtime_id,

                "scenario":

                    result.scenario,

                "score":

                    result.survivability_score,

                "pnl":

                    result.pnl,

                "pct":

                    result.pnl_pct,

                "vol_before":

                    result.volatility_before,

                "vol_after":

                    result.volatility_after,

                "passed":

                    result.passed,

                "generated":

                    utc_now(),

                "payload":

                    json.dumps(

                        result.to_dict()

                    ),

            },

        )

        if hasattr(

                self.db,

                "commit",

        ):
            self.db.commit()

    def persist_all_results(self):

        for result in self.results:
            self.persist_result(

                result

            )

    def history(

            self,

            limit=500,

    ):

        if self.db is None:
            return []

        rows = self.db.execute(

            text("""

            SELECT *

            FROM forex_stress_test_history

            WHERE tenant_id=:tenant

            AND user_id=:user

            AND portfolio_id=:portfolio

            ORDER BY generated_at DESC

            LIMIT :limit

            """),

            {

                "tenant":

                    self.tenant_id,

                "user":

                    self.user_id,

                "portfolio":

                    self.portfolio_id,

                "limit":

                    limit,

            },

        ).mappings().all()

        return [

            dict(

                row

            )

            for row in rows

        ]

    def runtime_statistics(self):

        history = self.history(

            1000

        )

        if not history:
            return {}

        pnl = [

            row["pnl"]

            for row in history

        ]

        survivability = [

            row["survivability_score"]

            for row in history

        ]

        return {

            "executions":

                len(history),

            "average_pnl":

                round4(

                    statistics.mean(

                        pnl

                    )

                ),

            "worst_pnl":

                round4(

                    min(

                        pnl

                    )

                ),

            "best_pnl":

                round4(

                    max(

                        pnl

                    )

                ),

            "average_survivability":

                round4(

                    statistics.mean(

                        survivability

                    )

                ),

        }

    def history_trend(self):

        trend = []

        for row in reversed(

                self.history(

                    500

                )

        ):
            trend.append(

                {

                    "generated_at":

                        row["generated_at"],

                    "scenario":

                        row["scenario"],

                    "pnl_pct":

                        row["pnl_pct"],

                    "survivability":

                        row["survivability_score"],

                }

            )

        return trend

    def dashboard_packet(self):

        return {

            "status":

                "success",

            "generated_at":

                utc_now_iso(),

            "summary":

                self.summary(),

            "institutional":

                self.institutional_summary(),

            "historical":

                self.historical_dashboard_packet(),

            "runtime":

                self.runtime_statistics(),

            "trend":

                self.history_trend(),

            "results":

                self.latest_results(),

        }

    def executive_scorecard(self):

        summary = self.summary()

        institutional = self.institutional_summary()

        runtime = self.runtime_statistics()

        return {

            "runtime_id":

                self.runtime_id,

            "tenant_id":

                self.tenant_id,

            "user_id":

                self.user_id,

            "portfolio_id":

                self.portfolio_id,

            "generated_at":

                utc_now_iso(),

            "summary":

                summary,

            "institutional":

                institutional,

            "runtime":

                runtime,

        }

    def executive_rating(self):

        score = self.institutional_score()

        if score >= 90:

            rating = "AAA"

        elif score >= 80:

            rating = "AA"

        elif score >= 70:

            rating = "A"

        elif score >= 60:

            rating = "BBB"

        elif score >= 50:

            rating = "BB"

        elif score >= 40:

            rating = "B"

        else:

            rating = "CCC"

        return {

            "score":

                score,

            "rating":

                rating,

        }

    def traffic_light(self):

        score = self.institutional_score()

        if score >= 80:

            status = "GREEN"

        elif score >= 60:

            status = "YELLOW"

        elif score >= 40:

            status = "ORANGE"

        else:

            status = "RED"

        return {

            "status":

                status,

            "score":

                score,

        }

    def export_json(self):

        return json.dumps(

            self.dashboard_packet(),

            indent=2,

            default=str,

        )

    def to_dict(self):

        return self.dashboard_packet()

    def export_summary(self):

        return {

            "executive":

                self.executive_scorecard(),

            "traffic":

                self.traffic_light(),

            "rating":

                self.executive_rating(),

        }

    def reset(self):

        self.results.clear()

        self.statistics = {

            "runs": 0,

            "passed": 0,

            "failed": 0,

        }

        self.runtime_id = str(

            uuid.uuid4()

        )

    def status(self):

        return {

            "runtime_id":

                self.runtime_id,

            "tenant_id":

                self.tenant_id,

            "user_id":

                self.user_id,

            "portfolio_id":

                self.portfolio_id,

            "scenario_count":

                len(

                    self.scenarios

                ),

            "results":

                len(

                    self.results

                ),

            "statistics":

                self.statistics,

            "generated_at":

                utc_now_iso(),

        }



_ENGINE = None


def get_forex_stress_testing_engine(
    db=None,
    portfolio=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):
    """
    Singleton factory expected by forex_stress_testing_dashboard.py.
    """
    global _ENGINE
    if (
        _ENGINE is None
        or getattr(_ENGINE, "db", None) is not db
        or getattr(_ENGINE, "tenant_id", None) != tenant_id
        or getattr(_ENGINE, "user_id", None) != user_id
        or getattr(_ENGINE, "portfolio_id", None) != portfolio_id
    ):
        _ENGINE = ForexStressTestingEngine(
            db=db,
            portfolio=portfolio,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )
    return _ENGINE