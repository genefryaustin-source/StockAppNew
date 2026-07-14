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

_INITIALIZED = False
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

        global _INITIALIZED

        if _INITIALIZED:
            return

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

        CREATE TABLE IF NOT EXISTS forex_var_history(

            {id_column},

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

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        );

        """))

        self.db.execute(text(f"""

        CREATE TABLE IF NOT EXISTS forex_var_stress_history(

            {id_column},

            tenant_id VARCHAR(120),

            user_id VARCHAR(120),

            portfolio_id VARCHAR(120),

            runtime_id VARCHAR(120),

            generated_at TIMESTAMP,

            payload JSONB,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        );

        """))

        if hasattr(self.db, "commit"):

            self.db.commit()
            _INITIALIZED = True

    # ------------------------------------------------------------------
    # Save VaR Result
    # ------------------------------------------------------------------

    def save_var(

        self,

        result,

    ):

        if self.db is None:

            return

        #self.ensure_tables()

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

        #self.ensure_tables()

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
