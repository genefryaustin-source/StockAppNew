# =============================================================================
# File: modules/forex/risk/forex_var_repository.py
#
# Sprint 30
# Phase 4C-3-3-2-2
#
# Build 1.1
#
# Institutional VaR Repository
#
# Persistence Layer
# =============================================================================

from __future__ import annotations

import json
import logging
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)


# =============================================================================
# Helpers
# =============================================================================

def utc_now():

    return datetime.now(timezone.utc)


def utc_now_iso():

    return utc_now().isoformat()


def json_payload(value):

    try:

        return json.dumps(value)

    except Exception:

        return "{}"


# =============================================================================
# Repository
# =============================================================================

class ForexVaRRepository:

    def __init__(

        self,

        db=None,

        tenant_id=None,

        user_id=None,

        portfolio_id=None,

    ):

        self.db = db

        self.tenant_id = tenant_id

        self.user_id = user_id

        self.portfolio_id = portfolio_id

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def ensure_tables(self):

        if self.db is None:

            return

        self.db.execute(text("""

        CREATE TABLE IF NOT EXISTS forex_var_history(

            id SERIAL PRIMARY KEY,

            tenant_id VARCHAR(120),

            user_id VARCHAR(120),

            portfolio_id VARCHAR(120),

            runtime_id VARCHAR(120),

            method VARCHAR(40),

            var95 DOUBLE PRECISION,

            var99 DOUBLE PRECISION,

            expected_shortfall DOUBLE PRECISION,

            volatility DOUBLE PRECISION,

            portfolio_value DOUBLE PRECISION,

            generated_at TIMESTAMP,

            payload JSONB,

            created_at TIMESTAMP DEFAULT NOW()

        );

        """))

        self.db.execute(text("""

        CREATE TABLE IF NOT EXISTS forex_var_stress_history(

            id SERIAL PRIMARY KEY,

            tenant_id VARCHAR(120),

            user_id VARCHAR(120),

            portfolio_id VARCHAR(120),

            runtime_id VARCHAR(120),

            generated_at TIMESTAMP,

            payload JSONB,

            created_at TIMESTAMP DEFAULT NOW()

        );

        """))

        if hasattr(self.db, "commit"):

            self.db.commit()

    # ------------------------------------------------------------------
    # Save VaR Result
    # ------------------------------------------------------------------

    def save_var(

        self,

        result,

    ):

        if self.db is None:

            return

        self.ensure_tables()

        self.db.execute(

            text("""

            INSERT INTO forex_var_history(

                tenant_id,

                user_id,

                portfolio_id,

                runtime_id,

                method,

                var95,

                var99,

                expected_shortfall,

                volatility,

                portfolio_value,

                generated_at,

                payload

            )

            VALUES(

                :tenant,

                :user,

                :portfolio,

                :runtime,

                :method,

                :var95,

                :var99,

                :es,

                :vol,

                :value,

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

                "method":

                    result.method,

                "var95":

                    result.var_95,

                "var99":

                    result.var_99,

                "es":

                    result.expected_shortfall,

                "vol":

                    result.volatility,

                "value":

                    result.portfolio_value,

                "generated":

                    utc_now(),

                "payload":

                    json_payload(

                        result.to_dict()

                    ),

            },

        )

        if hasattr(self.db, "commit"):

            self.db.commit()

    # ------------------------------------------------------------------
    # Save Stress Packet
    # ------------------------------------------------------------------

    def save_stress(

        self,

        runtime_id,

        packet,

    ):

        if self.db is None:

            return

        self.ensure_tables()

        self.db.execute(

            text("""

            INSERT INTO forex_var_stress_history(

                tenant_id,

                user_id,

                portfolio_id,

                runtime_id,

                generated_at,

                payload

            )

            VALUES(

                :tenant,

                :user,

                :portfolio,

                :runtime,

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

                    runtime_id,

                "generated":

                    utc_now(),

                "payload":

                    json_payload(

                        packet

                    ),

            },

        )

        if hasattr(self.db, "commit"):

            self.db.commit()

            # =============================================================================
            # File: modules/forex/risk/forex_var_repository.py
            #
            # Sprint 30
            # Phase 4C-3-3-2-2
            #
            # Build 1.2
            #
            # Continue Immediately After Build 1.1
            #
            # Historical Queries
            # Trend Analytics
            # =============================================================================

            # ------------------------------------------------------------------
            # Latest VaR
            # ------------------------------------------------------------------

            def latest_var(self):

                if self.db is None:
                    return None

                row = self.db.execute(

                    text("""

                    SELECT *

                    FROM forex_var_history

                    WHERE tenant_id=:tenant

                    AND user_id=:user

                    AND portfolio_id=:portfolio

                    ORDER BY generated_at DESC

                    LIMIT 1

                    """),

                    {

                        "tenant": self.tenant_id,

                        "user": self.user_id,

                        "portfolio": self.portfolio_id,

                    },

                ).mappings().first()

                return dict(row) if row else None

            # ------------------------------------------------------------------
            # VaR History
            # ------------------------------------------------------------------

            def var_history(

                    self,

                    limit: int = 500,

            ) -> List[Dict[str, Any]]:

                if self.db is None:
                    return []

                rows = self.db.execute(

                    text("""

                    SELECT *

                    FROM forex_var_history

                    WHERE tenant_id=:tenant

                    AND user_id=:user

                    AND portfolio_id=:portfolio

                    ORDER BY generated_at DESC

                    LIMIT :limit

                    """),

                    {

                        "tenant": self.tenant_id,

                        "user": self.user_id,

                        "portfolio": self.portfolio_id,

                        "limit": limit,

                    },

                ).mappings().all()

                return [

                    dict(r)

                    for r in rows

                ]

            # ------------------------------------------------------------------
            # Stress History
            # ------------------------------------------------------------------

            def stress_history(

                    self,

                    limit: int = 250,

            ) -> List[Dict[str, Any]]:

                if self.db is None:
                    return []

                rows = self.db.execute(

                    text("""

                    SELECT *

                    FROM forex_var_stress_history

                    WHERE tenant_id=:tenant

                    AND user_id=:user

                    AND portfolio_id=:portfolio

                    ORDER BY generated_at DESC

                    LIMIT :limit

                    """),

                    {

                        "tenant": self.tenant_id,

                        "user": self.user_id,

                        "portfolio": self.portfolio_id,

                        "limit": limit,

                    },

                ).mappings().all()

                return [

                    dict(r)

                    for r in rows

                ]

            # ------------------------------------------------------------------
            # Runtime History
            # ------------------------------------------------------------------

            def runtime_history(self):

                history = self.var_history(

                    limit=1000

                )

                runtimes = []

                for row in history:
                    runtimes.append(

                        {

                            "runtime_id":

                                row.get(

                                    "runtime_id"

                                ),

                            "generated_at":

                                row.get(

                                    "generated_at"

                                ),

                            "method":

                                row.get(

                                    "method"

                                ),

                            "portfolio_value":

                                row.get(

                                    "portfolio_value"

                                ),

                        }

                    )

                return runtimes

            # ------------------------------------------------------------------
            # VaR Trend
            # ------------------------------------------------------------------

            def var_trend(

                    self,

                    limit=250,

            ):

                history = self.var_history(

                    limit

                )

                trend = []

                for row in reversed(history):
                    trend.append(

                        {

                            "generated_at":

                                row.get(

                                    "generated_at"

                                ),

                            "var95":

                                row.get(

                                    "var95"

                                ),

                            "var99":

                                row.get(

                                    "var99"

                                ),

                            "expected_shortfall":

                                row.get(

                                    "expected_shortfall"

                                ),

                            "volatility":

                                row.get(

                                    "volatility"

                                ),

                            "portfolio_value":

                                row.get(

                                    "portfolio_value"

                                ),

                        }

                    )

                return trend

            # ------------------------------------------------------------------
            # Average VaR
            # ------------------------------------------------------------------

            def average_var(

                    self,

            ):

                history = self.var_history(

                    1000

                )

                if not history:
                    return 0.0

                return sum(

                    row["var95"]

                    for row in history

                ) / len(history)

            # ------------------------------------------------------------------
            # Maximum VaR
            # ------------------------------------------------------------------

            def maximum_var(

                    self,

            ):

                history = self.var_history(

                    1000

                )

                if not history:
                    return 0.0

                return max(

                    row["var95"]

                    for row in history

                )

            # ------------------------------------------------------------------
            # Minimum VaR
            # ------------------------------------------------------------------

            def minimum_var(

                    self,

            ):

                history = self.var_history(

                    1000

                )

                if not history:
                    return 0.0

                return min(

                    row["var95"]

                    for row in history

                )

            # ------------------------------------------------------------------
            # Trend Summary
            # ------------------------------------------------------------------

            def trend_summary(self):

                return {

                    "records":

                        len(

                            self.var_history()

                        ),

                    "average_var":

                        self.average_var(),

                    "maximum_var":

                        self.maximum_var(),

                    "minimum_var":

                        self.minimum_var(),

                    "latest":

                        self.latest_var(),

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

        # =============================================================================
        # File: modules/forex/risk/forex_stress_testing_engine.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-3
        #
        # Build 1.3
        #
        # Continue Immediately After Build 1.2
        #
        # Multi-Factor Institutional Stress Engine
        # =============================================================================

        # ------------------------------------------------------------------
        # Apply Multiple Scenarios
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Correlation Breakdown Scenario
        # ------------------------------------------------------------------

        def correlation_breakdown(self):

            return self.apply_multi_factor(

                [

                    StressScenario.VOLATILITY_SPIKE.value,

                    StressScenario.CORRELATION_BREAKDOWN.value,

                ]

            )

        # ------------------------------------------------------------------
        # Central Bank Crisis
        # ------------------------------------------------------------------

        def central_bank_crisis(self):

            return self.apply_multi_factor(

                [

                    StressScenario.CENTRAL_BANK.value,

                    StressScenario.USD_SURGE.value,

                    StressScenario.VOLATILITY_SPIKE.value,

                ]

            )

        # ------------------------------------------------------------------
        # Carry Trade Unwind
        # ------------------------------------------------------------------

        def carry_trade_unwind(self):

            return self.apply_multi_factor(

                [

                    StressScenario.CARRY_UNWIND.value,

                    StressScenario.USD_SURGE.value,

                    StressScenario.LIQUIDITY_CRISIS.value,

                ]

            )

        # ------------------------------------------------------------------
        # Inflation Shock
        # ------------------------------------------------------------------

        def inflation_crisis(self):

            return self.apply_multi_factor(

                [

                    StressScenario.INFLATION.value,

                    StressScenario.RATE_SHOCK.value,

                ]

            )

        # ------------------------------------------------------------------
        # Recession Scenario
        # ------------------------------------------------------------------

        def recession_scenario(self):

            return self.apply_multi_factor(

                [

                    StressScenario.RECESSION.value,

                    StressScenario.LIQUIDITY_CRISIS.value,

                    StressScenario.VOLATILITY_SPIKE.value,

                ]

            )

        # ------------------------------------------------------------------
        # Institutional Crisis
        # ------------------------------------------------------------------

        def institutional_crisis(self):

            return self.apply_multi_factor(

                [

                    StressScenario.FLASH_CRASH.value,

                    StressScenario.LIQUIDITY_CRISIS.value,

                    StressScenario.VOLATILITY_SPIKE.value,

                    StressScenario.CORRELATION_BREAKDOWN.value,

                ]

            )

        # ------------------------------------------------------------------
        # Crisis Suite
        # ------------------------------------------------------------------

        def execute_crisis_suite(self):

            return [

                self.central_bank_crisis(),

                self.carry_trade_unwind(),

                self.inflation_crisis(),

                self.recession_scenario(),

                self.institutional_crisis(),

            ]

        # ------------------------------------------------------------------
        # Crisis Ranking
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Composite Institutional Score
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Institutional Summary
        # ------------------------------------------------------------------

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

        # =============================================================================
        # File: modules/forex/risk/forex_stress_testing_engine.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-3
        #
        # Build 1.4
        #
        # Continue Immediately After Build 1.3
        #
        # Historical Crisis Replay Engine
        # =============================================================================

        # ------------------------------------------------------------------
        # Historical Crisis Library
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Replay Crisis
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Replay Entire Library
        # ------------------------------------------------------------------

        def replay_all_crises(self):

            results = []

            for crisis in self.historical_crises():
                results.append(

                    self.replay_crisis(

                        crisis["name"]

                    )

                )

            return results

        # ------------------------------------------------------------------
        # Crisis Statistics
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Crisis Ranking
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Historical Dashboard Packet
        # ------------------------------------------------------------------

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

        # =============================================================================
        # File: modules/forex/risk/forex_stress_testing_engine.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-3
        #
        # Build 2.1
        #
        # Continue Immediately After Build 1.4
        #
        # Stress History Persistence
        # Runtime Analytics
        # =============================================================================

        # ------------------------------------------------------------------
        # Ensure Tables
        # ------------------------------------------------------------------

        def ensure_tables(self):

            if self.db is None:
                return

            self.db.execute(text("""

            CREATE TABLE IF NOT EXISTS forex_stress_test_history(

                id SERIAL PRIMARY KEY,

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

                created_at TIMESTAMP DEFAULT NOW()

            );

            """))

            if hasattr(self.db, "commit"):
                self.db.commit()

        # ------------------------------------------------------------------
        # Persist Result
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Persist All Results
        # ------------------------------------------------------------------

        def persist_all_results(self):

            for result in self.results:
                self.persist_result(

                    result

                )

        # ------------------------------------------------------------------
        # History
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Runtime Analytics
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # History Trend
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Dashboard Packet
        # ------------------------------------------------------------------

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

        # =============================================================================
        # File: modules/forex/risk/forex_stress_testing_engine.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-3
        #
        # Build 2.2
        #
        # Continue Immediately After Build 2.1
        #
        # Executive Reporting
        # Export Services
        # Health Monitoring
        # =============================================================================

        # ------------------------------------------------------------------
        # Executive Scorecard
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Executive Risk Rating
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Traffic Light
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Export JSON
        # ------------------------------------------------------------------

        def export_json(self):

            return json.dumps(

                self.dashboard_packet(),

                indent=2,

                default=str,

            )

        # ------------------------------------------------------------------
        # Export Dictionary
        # ------------------------------------------------------------------

        def to_dict(self):

            return self.dashboard_packet()

        # ------------------------------------------------------------------
        # Export Summary
        # ------------------------------------------------------------------

        def export_summary(self):

            return {

                "executive":

                    self.executive_scorecard(),

                "traffic":

                    self.traffic_light(),

                "rating":

                    self.executive_rating(),

            }

        # ------------------------------------------------------------------
        # Reset Runtime
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Engine Status
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Health Check
        # ------------------------------------------------------------------

        def health(self):

            return {

                "status":

                    "healthy",

                "engine":

                    "ForexStressTestingEngine",

                "runtime":

                    self.status(),

                "traffic_light":

                    self.traffic_light(),

                "executive_rating":

                    self.executive_rating(),

            }

    # =============================================================================
    # Singleton
    # =============================================================================

    _STRESS_ENGINE = None

    def get_forex_stress_testing_engine(

            db=None,

            portfolio=None,

            tenant_id=None,

            user_id=None,

            portfolio_id=None,

    ):

        global _STRESS_ENGINE

        if (

                _STRESS_ENGINE is None

                or _STRESS_ENGINE.db is not db

                or _STRESS_ENGINE.portfolio is not portfolio

                or _STRESS_ENGINE.tenant_id != tenant_id

                or _STRESS_ENGINE.user_id != user_id

                or _STRESS_ENGINE.portfolio_id != portfolio_id

        ):
            _STRESS_ENGINE = ForexStressTestingEngine(

                db=db,

                portfolio=portfolio,

                tenant_id=tenant_id,

                user_id=user_id,

                portfolio_id=portfolio_id,

            )

        return _STRESS_ENGINE