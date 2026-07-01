# =============================================================================
# File: modules/forex/risk/forex_var_engine.py
#
# Sprint 30
# Phase 4C-3-3-2-1
#
# Build 1.1
#
# Institutional Value-at-Risk Engine
#
# Foundation
# =============================================================================

from __future__ import annotations

import json
import logging
import math
import statistics
import uuid

from collections import defaultdict
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from enum import Enum

from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple

import numpy as np
import pandas as pd

from sqlalchemy import text

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

DEFAULT_CONFIDENCE = 0.95

DEFAULT_LOOKBACK_DAYS = 252

DEFAULT_TRADING_DAYS = 252

DEFAULT_MONTE_CARLO_RUNS = 10000

DEFAULT_DECIMAL_PRECISION = 4

VAR_95 = 0.95

VAR_97 = 0.975

VAR_99 = 0.99


# =============================================================================
# Enumerations
# =============================================================================

class VaRMethod(str, Enum):

    PARAMETRIC = "parametric"

    HISTORICAL = "historical"

    MONTE_CARLO = "monte_carlo"


class StressScenario(str, Enum):

    NORMAL = "normal"

    RATE_SHOCK = "rate_shock"

    USD_SURGE = "usd_surge"

    USD_COLLAPSE = "usd_collapse"

    FLASH_CRASH = "flash_crash"

    CENTRAL_BANK = "central_bank"

    LIQUIDITY = "liquidity"

    VOLATILITY = "volatility"


class PositionDirection(str, Enum):

    LONG = "long"

    SHORT = "short"


# =============================================================================
# Helper Functions
# =============================================================================

def utc_now():

    return datetime.now(
        timezone.utc
    )


def utc_now_iso():

    return utc_now().isoformat()


def safe_float(

    value,

    default=0.0,

):

    try:

        if value is None:

            return default

        return float(value)

    except Exception:

        return default


def safe_int(

    value,

    default=0,

):

    try:

        if value is None:

            return default

        return int(value)

    except Exception:

        return default


def round4(value):

    return round(

        safe_float(value),

        DEFAULT_DECIMAL_PRECISION,

    )


def percentile(

    values,

    pct,

):

    if not values:

        return 0.0

    arr = np.array(values)

    return float(

        np.percentile(

            arr,

            pct,

        )

    )


def standard_deviation(

    values,

):

    if len(values) < 2:

        return 0.0

    return statistics.stdev(

        values

    )


def variance(

    values,

):

    if len(values) < 2:

        return 0.0

    return statistics.variance(

        values

    )


def covariance(

    series_a,

    series_b,

):

    if len(series_a) != len(series_b):

        return 0.0

    if len(series_a) < 2:

        return 0.0

    return float(

        np.cov(

            series_a,

            series_b,

        )[0][1]

    )


def correlation(

    series_a,

    series_b,

):

    if len(series_a) != len(series_b):

        return 0.0

    if len(series_a) < 2:

        return 0.0

    return float(

        np.corrcoef(

            series_a,

            series_b,

        )[0][1]

    )


# =============================================================================
# Configuration
# =============================================================================

@dataclass(slots=True)
class VaRConfiguration:

    confidence: float = DEFAULT_CONFIDENCE

    lookback_days: int = DEFAULT_LOOKBACK_DAYS

    monte_carlo_runs: int = DEFAULT_MONTE_CARLO_RUNS

    trading_days: int = DEFAULT_TRADING_DAYS

    precision: int = DEFAULT_DECIMAL_PRECISION

    persist_history: bool = True

    enable_cache: bool = True

    enable_stress_testing: bool = True

    enable_expected_shortfall: bool = True

    enable_runtime_history: bool = True

    created_at: str = field(
        default_factory=utc_now_iso
    )

    def to_dict(self):

        return asdict(self)


# =============================================================================
# Engine Metadata
# =============================================================================

ENGINE_NAME = "Forex Institutional VaR Engine"

ENGINE_VERSION = "1.0"

ENGINE_BUILD = "Sprint30-Phase4C-3-3-2-1"

ENGINE_AUTHOR = "StockApp Forex Risk Module"
# =============================================================================
# File: modules/forex/risk/forex_var_engine.py
#
# Sprint 30
# Phase 4C-3-3-2-1
#
# Build 1.2
#
# Continue Immediately After Build 1.1
# =============================================================================


# =============================================================================
# Portfolio Models
# =============================================================================

@dataclass(slots=True)
class ForexRiskPosition:

    symbol: str

    base_currency: str

    quote_currency: str

    direction: PositionDirection

    quantity: float

    entry_price: float

    current_price: float

    market_value: float

    notional_value: float

    unrealized_pnl: float = 0.0

    realized_pnl: float = 0.0

    leverage: float = 1.0

    weight: float = 0.0

    beta: float = 1.0

    volatility: float = 0.0

    daily_return: float = 0.0

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def exposure(self) -> float:

        return abs(self.notional_value)

    def total_pnl(self) -> float:

        return (

            self.unrealized_pnl

            +

            self.realized_pnl

        )

    def to_dict(self):

        return asdict(self)


# =============================================================================
# Portfolio
# =============================================================================

@dataclass(slots=True)
class ForexPortfolio:

    portfolio_id: str

    tenant_id: Optional[str]

    user_id: Optional[str]

    account_currency: str = "USD"

    positions: List[
        ForexRiskPosition
    ] = field(
        default_factory=list
    )

    cash: float = 0.0

    equity: float = 0.0

    buying_power: float = 0.0

    margin_used: float = 0.0

    margin_available: float = 0.0

    created_at: str = field(
        default_factory=utc_now_iso
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    # ------------------------------------------------------------------

    def add_position(

        self,

        position: ForexRiskPosition,

    ):

        self.positions.append(position)

        self.recalculate_weights()

    # ------------------------------------------------------------------

    def remove_position(

        self,

        symbol: str,

    ):

        self.positions = [

            p

            for p in self.positions

            if p.symbol != symbol

        ]

        self.recalculate_weights()

    # ------------------------------------------------------------------

    def total_market_value(self):

        return sum(

            p.market_value

            for p in self.positions

        )

    # ------------------------------------------------------------------

    def total_notional(self):

        return sum(

            p.notional_value

            for p in self.positions

        )

    # ------------------------------------------------------------------

    def total_exposure(self):

        return sum(

            p.exposure()

            for p in self.positions

        )

    # ------------------------------------------------------------------

    def total_unrealized_pnl(self):

        return sum(

            p.unrealized_pnl

            for p in self.positions

        )

    # ------------------------------------------------------------------

    def total_realized_pnl(self):

        return sum(

            p.realized_pnl

            for p in self.positions

        )

    # ------------------------------------------------------------------

    def total_pnl(self):

        return (

            self.total_unrealized_pnl()

            +

            self.total_realized_pnl()

        )

    # ------------------------------------------------------------------

    def portfolio_leverage(self):

        if self.equity == 0:

            return 0.0

        return (

            self.total_notional()

            /

            self.equity

        )

    # ------------------------------------------------------------------

    def position_count(self):

        return len(

            self.positions

        )

    # ------------------------------------------------------------------

    def long_positions(self):

        return [

            p

            for p in self.positions

            if p.direction == PositionDirection.LONG

        ]

    # ------------------------------------------------------------------

    def short_positions(self):

        return [

            p

            for p in self.positions

            if p.direction == PositionDirection.SHORT

        ]

    # ------------------------------------------------------------------

    def recalculate_weights(self):

        total = self.total_market_value()

        if total <= 0:

            return

        for position in self.positions:

            position.weight = (

                position.market_value

                /

                total

            )

    # ------------------------------------------------------------------

    def symbols(self):

        return [

            p.symbol

            for p in self.positions

        ]

    # ------------------------------------------------------------------

    def currencies(self):

        currencies = set()

        for p in self.positions:

            currencies.add(

                p.base_currency

            )

            currencies.add(

                p.quote_currency

            )

        return sorted(

            currencies

        )

    # ------------------------------------------------------------------

    def to_dict(self):

        return {

            "portfolio_id":

                self.portfolio_id,

            "tenant_id":

                self.tenant_id,

            "user_id":

                self.user_id,

            "account_currency":

                self.account_currency,

            "cash":

                self.cash,

            "equity":

                self.equity,

            "buying_power":

                self.buying_power,

            "margin_used":

                self.margin_used,

            "margin_available":

                self.margin_available,

            "market_value":

                self.total_market_value(),

            "notional":

                self.total_notional(),

            "exposure":

                self.total_exposure(),

            "leverage":

                self.portfolio_leverage(),

            "position_count":

                self.position_count(),

            "positions":[

                p.to_dict()

                for p in self.positions

            ],

            "created_at":

                self.created_at,

            "metadata":

                dict(self.metadata),

        }


# =============================================================================
# Portfolio Factory
# =============================================================================

def create_empty_portfolio(

    tenant_id=None,

    user_id=None,

    portfolio_id=None,

):

    return ForexPortfolio(

        portfolio_id=

            portfolio_id

            or str(uuid.uuid4()),

        tenant_id=

            tenant_id,

        user_id=

            user_id,

    )
# =============================================================================
# File: modules/forex/risk/forex_var_engine.py
#
# Sprint 30
# Phase 4C-3-3-2-1
#
# Build 1.3
#
# Continue Immediately After Build 1.2
# =============================================================================


# =============================================================================
# Value at Risk Result Models
# =============================================================================

@dataclass(slots=True)
class VaRResult:

    portfolio_id: str

    tenant_id: Optional[str]

    user_id: Optional[str]

    method: VaRMethod

    confidence_level: float

    lookback_days: int

    portfolio_value: float

    portfolio_volatility: float

    daily_var: float

    weekly_var: float

    monthly_var: float

    annualized_volatility: float

    generated_at: str = field(
        default_factory=utc_now_iso
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self):

        return asdict(self)


# =============================================================================
# Expected Shortfall
# =============================================================================

@dataclass(slots=True)
class ExpectedShortfallResult:

    portfolio_id: str

    confidence_level: float

    expected_shortfall: float

    tail_observations: int

    worst_loss: float

    average_tail_loss: float

    generated_at: str = field(
        default_factory=utc_now_iso
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self):

        return asdict(self)


# =============================================================================
# Stress Scenario Result
# =============================================================================

@dataclass(slots=True)
class StressScenarioResult:

    scenario: StressScenario

    portfolio_before: float

    portfolio_after: float

    pnl_change: float

    pnl_percent: float

    passed: bool

    notes: str = ""

    generated_at: str = field(
        default_factory=utc_now_iso
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self):

        return asdict(self)


# =============================================================================
# Portfolio Risk Statistics
# =============================================================================

@dataclass(slots=True)
class PortfolioRiskStatistics:

    portfolio_id: str

    total_positions: int

    total_market_value: float

    total_notional: float

    total_exposure: float

    leverage: float

    gross_exposure: float

    net_exposure: float

    unrealized_pnl: float

    realized_pnl: float

    average_position_size: float

    largest_position: float

    smallest_position: float

    average_daily_return: float

    return_volatility: float

    variance: float

    standard_deviation: float

    beta: float

    generated_at: str = field(
        default_factory=utc_now_iso
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self):

        return asdict(self)


# =============================================================================
# Historical VaR Record
# =============================================================================

@dataclass(slots=True)
class VaRHistoryRecord:

    runtime_id: str

    portfolio_id: str

    tenant_id: Optional[str]

    user_id: Optional[str]

    var_95: float

    var_99: float

    expected_shortfall: float

    portfolio_value: float

    volatility: float

    method: str

    generated_at: str

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self):

        return asdict(self)


# =============================================================================
# Portfolio Analytics Snapshot
# =============================================================================

@dataclass(slots=True)
class PortfolioAnalyticsSnapshot:

    snapshot_id: str

    portfolio_id: str

    timestamp: str

    equity: float

    exposure: float

    leverage: float

    margin_used: float

    margin_available: float

    portfolio_return: float

    drawdown: float

    volatility: float

    var95: float

    var99: float

    expected_shortfall: float

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self):

        return asdict(self)


# =============================================================================
# Monte Carlo Simulation Result
# =============================================================================

@dataclass(slots=True)
class MonteCarloSimulation:

    runs: int

    confidence_level: float

    mean_return: float

    median_return: float

    best_case: float

    worst_case: float

    percentile_95: float

    percentile_99: float

    expected_shortfall: float

    generated_at: str = field(
        default_factory=utc_now_iso
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self):

        return asdict(self)


# =============================================================================
# Historical Return Series
# =============================================================================

@dataclass(slots=True)
class HistoricalReturnSeries:

    symbol: str

    returns: List[float] = field(
        default_factory=list
    )

    dates: List[str] = field(
        default_factory=list
    )

    source: str = "market"

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def mean(self):

        if not self.returns:
            return 0.0

        return statistics.mean(
            self.returns
        )

    def volatility(self):

        if len(self.returns) < 2:
            return 0.0

        return statistics.stdev(
            self.returns
        )

    def variance(self):

        if len(self.returns) < 2:
            return 0.0

        return statistics.variance(
            self.returns
        )

    def minimum(self):

        if not self.returns:
            return 0.0

        return min(
            self.returns
        )

    def maximum(self):

        if not self.returns:
            return 0.0

        return max(
            self.returns
        )

    def to_dict(self):

        return asdict(self)

    # =============================================================================
    # File: modules/forex/risk/forex_var_engine.py
    #
    # Sprint 30
    # Phase 4C-3-3-2-1
    #
    # Build 1.4
    #
    # Continue Immediately After Build 1.3
    # =============================================================================

    # =============================================================================
    # Forex Institutional VaR Engine
    # =============================================================================

    class ForexVaREngine:

        """
        Institutional Value-at-Risk Engine

        Responsibilities

            • Portfolio Statistics
            • Historical Returns
            • Covariance Matrix
            • Parametric VaR
            • Historical VaR
            • Expected Shortfall
            • Monte Carlo Simulation
            • Stress Testing
            • Runtime History
            • Dashboard Packet
        """

        def __init__(

                self,

                db=None,

                tenant_id=None,

                user_id=None,

                portfolio_id=None,

                configuration: Optional[
                    VaRConfiguration
                ] = None,

        ):
            self.db = db

            self.tenant_id = tenant_id

            self.user_id = user_id

            self.portfolio_id = portfolio_id

            self.configuration = (

                    configuration

                    or

                    VaRConfiguration()

            )

            #
            # Runtime
            #

            self.runtime_id = str(

                uuid.uuid4()

            )

            self.created_at = utc_now_iso()

            #
            # Portfolio
            #

            self.portfolio = create_empty_portfolio(

                tenant_id=tenant_id,

                user_id=user_id,

                portfolio_id=portfolio_id,

            )

            #
            # Historical Returns
            #

            self.return_series: Dict[
                str,
                HistoricalReturnSeries
            ] = {}

            #
            # Covariance Cache
            #

            self.covariance_matrix = None

            self.correlation_matrix = None

            #
            # Latest Calculations
            #

            self.latest_statistics = None

            self.latest_var = None

            self.latest_expected_shortfall = None

            self.latest_monte_carlo = None

            self.latest_stress_results = []

            #
            # Historical Cache
            #

            self.var_history: List[
                VaRHistoryRecord
            ] = []

            self.analytics_history: List[
                PortfolioAnalyticsSnapshot
            ] = []

            #
            # Internal Caches
            #

            self.market_prices = {}

            self.market_returns = {}

            self.fx_rates = {}

            self.symbol_cache = {}

            #
            # Diagnostics
            #

            self.statistics = {

                "calculations": 0,

                "historical_runs": 0,

                "stress_runs": 0,

                "cache_hits": 0,

                "cache_misses": 0,

            }

            logger.info(

                "%s initialized",

                ENGINE_NAME,

            )

        # ------------------------------------------------------------------
        # Identity
        # ------------------------------------------------------------------

        @property
        def identity(self):
            return {

                "runtime_id":

                    self.runtime_id,

                "tenant_id":

                    self.tenant_id,

                "user_id":

                    self.user_id,

                "portfolio_id":

                    self.portfolio_id,

            }

        # ------------------------------------------------------------------
        # Configuration
        # ------------------------------------------------------------------

        def configuration_summary(self):
            return self.configuration.to_dict()

        # ------------------------------------------------------------------
        # Portfolio
        # ------------------------------------------------------------------

        def set_portfolio(

                self,

                portfolio: ForexPortfolio,

        ):
            self.portfolio = portfolio

            return portfolio

        # ------------------------------------------------------------------

        def add_position(

                self,

                position: ForexRiskPosition,

        ):
            self.portfolio.add_position(

                position

            )

        # ------------------------------------------------------------------

        def clear_positions(self):
            self.portfolio.positions.clear()

        # ------------------------------------------------------------------

        def position_count(self):
            return self.portfolio.position_count()

        # ------------------------------------------------------------------
        # Historical Returns
        # ------------------------------------------------------------------

        def add_return_series(

                self,

                symbol,

                series,

        ):
            if isinstance(

                    series,

                    HistoricalReturnSeries,

            ):
                self.return_series[

                    symbol

                ] = series

                return

            self.return_series[

                symbol

            ] = HistoricalReturnSeries(

                symbol=symbol,

                returns=list(series),

            )

        # ------------------------------------------------------------------

        def get_return_series(

                self,

                symbol,

        ):
            return self.return_series.get(

                symbol

            )

        # ------------------------------------------------------------------

        def available_symbols(self):
            return sorted(

                self.return_series.keys()

            )

        # ------------------------------------------------------------------
        # Cache
        # ------------------------------------------------------------------

        def clear_cache(self):
            self.covariance_matrix = None

            self.correlation_matrix = None

            self.market_prices.clear()

            self.market_returns.clear()

            self.fx_rates.clear()

            self.symbol_cache.clear()

        # ------------------------------------------------------------------

        def reset(self):
            self.clear_cache()

            self.return_series.clear()

            self.var_history.clear()

            self.analytics_history.clear()

            self.latest_statistics = None

            self.latest_var = None

            self.latest_expected_shortfall = None

            self.latest_monte_carlo = None

            self.latest_stress_results.clear()

        # ------------------------------------------------------------------
        # Status
        # ------------------------------------------------------------------

        def status(self):
            return {

                "engine":

                    ENGINE_NAME,

                "version":

                    ENGINE_VERSION,

                "runtime":

                    self.runtime_id,

                "portfolio":

                    self.portfolio.portfolio_id,

                "symbols":

                    len(

                        self.return_series

                    ),

                "positions":

                    self.position_count(),

                "history":

                    len(

                        self.var_history

                    ),

                "statistics":

                    dict(

                        self.statistics

                    ),

                "created_at":

                    self.created_at,

            }

        # =============================================================================
        # File: modules/forex/risk/forex_var_engine.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-1
        #
        # Build 2.1
        #
        # Continue Immediately After Build 1.4
        #
        # Portfolio Statistics & Covariance Foundation
        # =============================================================================

        # ------------------------------------------------------------------
        # Portfolio Statistics
        # ------------------------------------------------------------------

        def build_portfolio_statistics(
                self,
        ) -> PortfolioRiskStatistics:

            positions = self.portfolio.positions

            market_values = [
                p.market_value
                for p in positions
            ]

            notionals = [
                p.notional_value
                for p in positions
            ]

            exposures = [
                p.exposure()
                for p in positions
            ]

            returns = [
                p.daily_return
                for p in positions
            ]

            betas = [
                p.beta
                for p in positions
            ]

            statistics_result = PortfolioRiskStatistics(

                portfolio_id=self.portfolio.portfolio_id,

                total_positions=len(positions),

                total_market_value=sum(market_values),

                total_notional=sum(notionals),

                total_exposure=sum(exposures),

                leverage=self.portfolio.portfolio_leverage(),

                gross_exposure=sum(exposures),

                net_exposure=sum(notionals),

                unrealized_pnl=
                self.portfolio.total_unrealized_pnl(),

                realized_pnl=
                self.portfolio.total_realized_pnl(),

                average_position_size=
                statistics.mean(
                    market_values
                )
                if market_values
                else 0.0,

                largest_position=
                max(market_values)
                if market_values
                else 0.0,

                smallest_position=
                min(market_values)
                if market_values
                else 0.0,

                average_daily_return=
                statistics.mean(
                    returns
                )
                if returns
                else 0.0,

                return_volatility=
                standard_deviation(
                    returns
                ),

                variance=
                variance(
                    returns
                ),

                standard_deviation=
                standard_deviation(
                    returns
                ),

                beta=
                statistics.mean(
                    betas
                )
                if betas
                else 1.0,

            )

            self.latest_statistics = statistics_result

            return statistics_result

        # ------------------------------------------------------------------
        # Portfolio Return Vector
        # ------------------------------------------------------------------

        def portfolio_return_vector(
                self,
        ) -> np.ndarray:

            returns = []

            for position in self.portfolio.positions:
                returns.append(
                    safe_float(
                        position.daily_return
                    )
                )

            return np.array(
                returns,
                dtype=float,
            )

        # ------------------------------------------------------------------
        # Historical Matrix
        # ------------------------------------------------------------------

        def historical_return_matrix(
                self,
        ) -> np.ndarray:

            symbols = self.available_symbols()

            if not symbols:
                return np.array([])

            matrix = []

            for symbol in symbols:
                history = self.get_return_series(
                    symbol
                )

                matrix.append(
                    history.returns
                )

            return np.array(
                matrix,
                dtype=float,
            )

        # ------------------------------------------------------------------
        # Covariance Matrix
        # ------------------------------------------------------------------

        def covariance_matrix_dataframe(
                self,
                rebuild=False,
        ):

            if (

                    self.covariance_matrix is not None

                    and

                    not rebuild

            ):
                self.statistics[
                    "cache_hits"
                ] += 1

                return self.covariance_matrix

            matrix = self.historical_return_matrix()

            if matrix.size == 0:
                self.covariance_matrix = (
                    pd.DataFrame()
                )

                return self.covariance_matrix

            covariance = np.cov(
                matrix
            )

            self.covariance_matrix = pd.DataFrame(

                covariance,

                index=self.available_symbols(),

                columns=self.available_symbols(),

            )

            self.statistics[
                "cache_misses"
            ] += 1

            return self.covariance_matrix

        # ------------------------------------------------------------------
        # Correlation Matrix
        # ------------------------------------------------------------------

        def correlation_matrix_dataframe(
                self,
                rebuild=False,
        ):

            if (

                    self.correlation_matrix is not None

                    and

                    not rebuild

            ):
                return self.correlation_matrix

            matrix = self.historical_return_matrix()

            if matrix.size == 0:
                self.correlation_matrix = (
                    pd.DataFrame()
                )

                return self.correlation_matrix

            correlations = np.corrcoef(
                matrix
            )

            self.correlation_matrix = pd.DataFrame(

                correlations,

                index=self.available_symbols(),

                columns=self.available_symbols(),

            )

            return self.correlation_matrix

        # ------------------------------------------------------------------
        # Portfolio Volatility
        # ------------------------------------------------------------------

        def portfolio_volatility(
                self,
        ) -> float:

            stats = self.build_portfolio_statistics()

            return stats.standard_deviation

        # ------------------------------------------------------------------
        # Annualized Volatility
        # ------------------------------------------------------------------

        def annualized_volatility(
                self,
        ) -> float:

            return (

                    self.portfolio_volatility()

                    *

                    math.sqrt(

                        self.configuration.trading_days

                    )

            )

        # ------------------------------------------------------------------
        # Covariance Lookup
        # ------------------------------------------------------------------

        def covariance(
                self,
                symbol_a,
                symbol_b,
        ):

            matrix = self.covariance_matrix_dataframe()

            if matrix.empty:
                return 0.0

            if symbol_a not in matrix.index:
                return 0.0

            if symbol_b not in matrix.columns:
                return 0.0

            return float(

                matrix.loc[
                    symbol_a,
                    symbol_b,
                ]

            )

        # ------------------------------------------------------------------
        # Correlation Lookup
        # ------------------------------------------------------------------

        def correlation(
                self,
                symbol_a,
                symbol_b,
        ):

            matrix = self.correlation_matrix_dataframe()

            if matrix.empty:
                return 0.0

            if symbol_a not in matrix.index:
                return 0.0

            if symbol_b not in matrix.columns:
                return 0.0

            return float(

                matrix.loc[
                    symbol_a,
                    symbol_b,
                ]

            )

        # =============================================================================
        # File: modules/forex/risk/forex_var_engine.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-1
        #
        # Build 2.2
        #
        # Continue Immediately After Build 2.1
        #
        # Institutional Portfolio Risk Mathematics
        # =============================================================================

        # ------------------------------------------------------------------
        # Position Volatility
        # ------------------------------------------------------------------

        def position_volatility(
                self,
                symbol: str,
        ) -> float:

            history = self.get_return_series(
                symbol
            )

            if history is None:
                return 0.0

            return history.volatility()

        # ------------------------------------------------------------------
        # Position Variance
        # ------------------------------------------------------------------

        def position_variance(
                self,
                symbol: str,
        ) -> float:

            history = self.get_return_series(
                symbol
            )

            if history is None:
                return 0.0

            return history.variance()

        # ------------------------------------------------------------------
        # Portfolio Variance
        # ------------------------------------------------------------------

        def portfolio_variance(
                self,
        ) -> float:

            covariance = self.covariance_matrix_dataframe()

            if covariance.empty:
                return 0.0

            weights = np.array(

                [

                    p.weight

                    for p in self.portfolio.positions

                ],

                dtype=float,

            )

            matrix = covariance.values

            variance = (

                    weights.T

                    @

                    matrix

                    @

                    weights

            )

            return float(variance)

        # ------------------------------------------------------------------
        # Portfolio Standard Deviation
        # ------------------------------------------------------------------

        def portfolio_standard_deviation(
                self,
        ) -> float:

            return math.sqrt(

                max(

                    self.portfolio_variance(),

                    0.0,

                )

            )

        # ------------------------------------------------------------------
        # Diversification Ratio
        # ------------------------------------------------------------------

        def diversification_ratio(
                self,
        ) -> float:

            positions = self.portfolio.positions

            if not positions:
                return 0.0

            weighted = 0.0

            for position in positions:
                weighted += (

                        position.weight

                        *

                        max(

                            position.volatility,

                            0.0,

                        )

                )

            portfolio_vol = self.portfolio_standard_deviation()

            if portfolio_vol <= 0:
                return 0.0

            return weighted / portfolio_vol

        # ------------------------------------------------------------------
        # Risk Contribution
        # ------------------------------------------------------------------

        def risk_contribution(
                self,
        ) -> List[Dict[str, Any]]:

            portfolio_vol = self.portfolio_standard_deviation()

            if portfolio_vol == 0:
                return []

            rows = []

            covariance = self.covariance_matrix_dataframe()

            weights = np.array(

                [

                    p.weight

                    for p in self.portfolio.positions

                ]

            )

            matrix = covariance.values

            marginal = matrix @ weights

            contribution = (

                                   weights

                                   *

                                   marginal

                           ) / portfolio_vol

            for idx, position in enumerate(

                    self.portfolio.positions

            ):
                rows.append(

                    {

                        "symbol":

                            position.symbol,

                        "weight":

                            round4(

                                position.weight

                            ),

                        "volatility":

                            round4(

                                position.volatility

                            ),

                        "risk_contribution":

                            round4(

                                contribution[idx]

                            ),

                        "percentage":

                            round4(

                                contribution[idx]

                                /

                                portfolio_vol

                            ),

                    }

                )

            rows.sort(

                key=lambda x:

                x["risk_contribution"],

                reverse=True,

            )

            return rows

        # ------------------------------------------------------------------
        # Largest Risk Contributors
        # ------------------------------------------------------------------

        def largest_risk_positions(

                self,

                limit=10,

        ):

            return self.risk_contribution()[

                :limit

            ]

        # ------------------------------------------------------------------
        # Concentration
        # ------------------------------------------------------------------

        def concentration_index(
                self,
        ) -> float:

            weights = [

                p.weight

                for p in self.portfolio.positions

            ]

            if not weights:
                return 0.0

            hhi = sum(

                w ** 2

                for w in weights

            )

            return hhi

        # ------------------------------------------------------------------
        # Effective Number of Positions
        # ------------------------------------------------------------------

        def effective_positions(
                self,
        ) -> float:

            concentration = self.concentration_index()

            if concentration == 0:
                return 0.0

            return 1.0 / concentration

        # ------------------------------------------------------------------
        # Gross Exposure
        # ------------------------------------------------------------------

        def gross_exposure(
                self,
        ):

            return sum(

                abs(

                    p.notional_value

                )

                for p in self.portfolio.positions

            )

        # ------------------------------------------------------------------
        # Net Exposure
        # ------------------------------------------------------------------

        def net_exposure(
                self,
        ):

            return sum(

                p.notional_value

                for p in self.portfolio.positions

            )

        # ------------------------------------------------------------------
        # Exposure by Currency
        # ------------------------------------------------------------------

        def currency_exposure(
                self,
        ) -> Dict[str, float]:

            exposure = defaultdict(float)

            for position in self.portfolio.positions:
                exposure[

                    position.base_currency

                ] += position.notional_value

                exposure[

                    position.quote_currency

                ] -= position.notional_value

            return dict(

                sorted(

                    exposure.items()

                )

            )

        # ------------------------------------------------------------------
        # Exposure by Direction
        # ------------------------------------------------------------------

        def directional_exposure(
                self,
        ):

            long_value = 0.0

            short_value = 0.0

            for position in self.portfolio.positions:

                if (

                        position.direction

                        ==

                        PositionDirection.LONG

                ):

                    long_value += (

                        position.notional_value

                    )

                else:

                    short_value += (

                        abs(

                            position.notional_value

                        )

                    )

            return {

                "long":

                    long_value,

                "short":

                    short_value,

                "net":

                    long_value - short_value,

            }

        # ------------------------------------------------------------------
        # Portfolio Summary
        # ------------------------------------------------------------------

        def portfolio_summary(
                self,
        ):

            return {

                "portfolio":

                    self.portfolio.to_dict(),

                "statistics":

                    self.build_portfolio_statistics().to_dict(),

                "gross_exposure":

                    self.gross_exposure(),

                "net_exposure":

                    self.net_exposure(),

                "currency_exposure":

                    self.currency_exposure(),

                "directional":

                    self.directional_exposure(),

                "effective_positions":

                    round4(

                        self.effective_positions()

                    ),

                "diversification_ratio":

                    round4(

                        self.diversification_ratio()

                    ),

            }

        # =============================================================================
        # File: modules/forex/risk/forex_var_engine.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-1
        #
        # Build 3.1
        #
        # Continue Immediately After Build 2.2
        #
        # Parametric VaR Foundation
        # =============================================================================

        # ------------------------------------------------------------------
        # Z Score Lookup
        # ------------------------------------------------------------------

        def z_score(
                self,
                confidence: float,
        ) -> float:

            lookup = {

                0.90: 1.28155,

                0.95: 1.64485,

                0.975: 1.95996,

                0.99: 2.32635,

                0.995: 2.57583,

            }

            return lookup.get(

                round(confidence, 3),

                1.64485,

            )

        # ------------------------------------------------------------------
        # Parametric Daily VaR
        # ------------------------------------------------------------------

        def parametric_var(

                self,

                confidence=None,

        ) -> float:

            if confidence is None:
                confidence = (

                    self.configuration.confidence

                )

            portfolio_value = (

                self.portfolio.total_market_value()

            )

            if portfolio_value <= 0:
                return 0.0

            sigma = (

                self.portfolio_standard_deviation()

            )

            z = self.z_score(

                confidence

            )

            var = (

                    z

                    *

                    sigma

                    *

                    portfolio_value

            )

            return float(

                abs(var)

            )

        # ------------------------------------------------------------------
        # Multi-Horizon VaR
        # ------------------------------------------------------------------

        def horizon_var(

                self,

                days: int,

                confidence=None,

        ) -> float:

            if days <= 0:
                return 0.0

            return (

                    self.parametric_var(

                        confidence

                    )

                    *

                    math.sqrt(

                        days

                    )

            )

        # ------------------------------------------------------------------
        # Daily
        # ------------------------------------------------------------------

        def daily_var(

                self,

                confidence=None,

        ):

            return self.horizon_var(

                1,

                confidence,

            )

        # ------------------------------------------------------------------
        # Weekly
        # ------------------------------------------------------------------

        def weekly_var(

                self,

                confidence=None,

        ):

            return self.horizon_var(

                5,

                confidence,

            )

        # ------------------------------------------------------------------
        # Monthly
        # ------------------------------------------------------------------

        def monthly_var(

                self,

                confidence=None,

        ):

            return self.horizon_var(

                21,

                confidence,

            )

        # ------------------------------------------------------------------
        # Annual
        # ------------------------------------------------------------------

        def annual_var(

                self,

                confidence=None,

        ):

            return self.horizon_var(

                self.configuration.trading_days,

                confidence,

            )

        # ------------------------------------------------------------------
        # Confidence Set
        # ------------------------------------------------------------------

        def confidence_levels(self):

            return {

                "95":

                    self.daily_var(

                        VAR_95

                    ),

                "97.5":

                    self.daily_var(

                        VAR_97

                    ),

                "99":

                    self.daily_var(

                        VAR_99

                    ),

            }

        # ------------------------------------------------------------------
        # Position VaR
        # ------------------------------------------------------------------

        def position_var(

                self,

                position: ForexRiskPosition,

                confidence=None,

        ):

            if confidence is None:
                confidence = (

                    self.configuration.confidence

                )

            sigma = max(

                position.volatility,

                0.0,

            )

            z = self.z_score(

                confidence

            )

            return abs(

                z

                *

                sigma

                *

                position.market_value

            )

        # ------------------------------------------------------------------
        # All Positions
        # ------------------------------------------------------------------

        def position_var_table(

                self,

                confidence=None,

        ):

            rows = []

            for position in self.portfolio.positions:
                rows.append(

                    {

                        "symbol":

                            position.symbol,

                        "direction":

                            position.direction.value,

                        "market_value":

                            position.market_value,

                        "weight":

                            round4(

                                position.weight

                            ),

                        "volatility":

                            round4(

                                position.volatility

                            ),

                        "daily_var":

                            round4(

                                self.position_var(

                                    position,

                                    confidence,

                                )

                            ),

                    }

                )

            rows.sort(

                key=lambda x:

                x["daily_var"],

                reverse=True,

            )

            return rows

        # ------------------------------------------------------------------
        # Portfolio VaR Result
        # ------------------------------------------------------------------

        def calculate_parametric_var(

                self,

                confidence=None,

        ) -> VaRResult:

            if confidence is None:
                confidence = (

                    self.configuration.confidence

                )

            result = VaRResult(

                portfolio_id=

                self.portfolio.portfolio_id,

                tenant_id=

                self.tenant_id,

                user_id=

                self.user_id,

                method=

                VaRMethod.PARAMETRIC,

                confidence_level=

                confidence,

                lookback_days=

                self.configuration.lookback_days,

                portfolio_value=

                self.portfolio.total_market_value(),

                portfolio_volatility=

                self.portfolio_standard_deviation(),

                daily_var=

                self.daily_var(

                    confidence

                ),

                weekly_var=

                self.weekly_var(

                    confidence

                ),

                monthly_var=

                self.monthly_var(

                    confidence

                ),

                annualized_volatility=

                self.annualized_volatility(),

            )

            self.latest_var = result

            self.statistics[

                "calculations"

            ] += 1

            return result

        # =============================================================================
        # File: modules/forex/risk/forex_var_engine.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-1
        #
        # Build 3.2
        #
        # Continue Immediately After Build 3.1
        #
        # Institutional Parametric VaR Analytics
        # =============================================================================

        # ------------------------------------------------------------------
        # Marginal VaR
        # ------------------------------------------------------------------

        def marginal_var(
                self,
                confidence=None,
        ):

            if confidence is None:
                confidence = self.configuration.confidence

            portfolio_var = self.daily_var(
                confidence
            )

            portfolio_value = (
                self.portfolio.total_market_value()
            )

            rows = []

            if portfolio_value <= 0:
                return rows

            for position in self.portfolio.positions:
                contribution = (

                        position.weight

                        *

                        portfolio_var

                )

                rows.append(

                    {

                        "symbol":
                            position.symbol,

                        "weight":
                            round4(
                                position.weight
                            ),

                        "marginal_var":
                            round4(
                                contribution
                            ),

                    }

                )

            rows.sort(

                key=lambda x:

                x["marginal_var"],

                reverse=True,

            )

            return rows

        # ------------------------------------------------------------------
        # Component VaR
        # ------------------------------------------------------------------

        def component_var(
                self,
                confidence=None,
        ):

            if confidence is None:
                confidence = (
                    self.configuration.confidence
                )

            portfolio_var = self.daily_var(
                confidence
            )

            rows = []

            for position in self.portfolio.positions:

                contribution = (

                        portfolio_var

                        *

                        position.weight

                )

                pct = 0.0

                if portfolio_var > 0:
                    pct = (

                            contribution

                            /

                            portfolio_var

                    )

                rows.append(

                    {

                        "symbol":
                            position.symbol,

                        "component_var":
                            round4(
                                contribution
                            ),

                        "percentage":
                            round4(
                                pct
                            ),

                    }

                )

            rows.sort(

                key=lambda x:

                x["component_var"],

                reverse=True,

            )

            return rows

        # ------------------------------------------------------------------
        # Incremental VaR
        # ------------------------------------------------------------------

        def incremental_var(
                self,
                confidence=None,
        ):

            if confidence is None:
                confidence = (
                    self.configuration.confidence
                )

            original = self.daily_var(
                confidence
            )

            rows = []

            for index, position in enumerate(

                    list(
                        self.portfolio.positions
                    )

            ):
                removed = self.portfolio.positions.pop(
                    index
                )

                self.clear_cache()

                reduced = self.daily_var(
                    confidence
                )

                self.portfolio.positions.insert(
                    index,
                    removed,
                )

                self.clear_cache()

                rows.append(

                    {

                        "symbol":
                            position.symbol,

                        "portfolio_var":
                            round4(original),

                        "without_position":
                            round4(reduced),

                        "incremental_var":
                            round4(
                                original - reduced
                            ),

                    }

                )

            rows.sort(

                key=lambda x:

                x["incremental_var"],

                reverse=True,

            )

            return rows

        # ------------------------------------------------------------------
        # Diversification Benefit
        # ------------------------------------------------------------------

        def diversification_benefit(
                self,
                confidence=None,
        ):

            if confidence is None:
                confidence = (
                    self.configuration.confidence
                )

            standalone = 0.0

            for position in self.portfolio.positions:
                standalone += self.position_var(

                    position,

                    confidence,

                )

            portfolio = self.daily_var(
                confidence
            )

            benefit = standalone - portfolio

            ratio = 0.0

            if standalone > 0:
                ratio = benefit / standalone

            return {

                "standalone_var":
                    round4(standalone),

                "portfolio_var":
                    round4(portfolio),

                "benefit":
                    round4(benefit),

                "benefit_ratio":
                    round4(ratio),

            }

        # ------------------------------------------------------------------
        # VaR By Currency
        # ------------------------------------------------------------------

        def currency_var(
                self,
                confidence=None,
        ):

            if confidence is None:
                confidence = (
                    self.configuration.confidence
                )

            exposure = defaultdict(float)

            for position in self.portfolio.positions:
                value = self.position_var(

                    position,

                    confidence,

                )

                exposure[
                    position.base_currency
                ] += value

            rows = []

            for currency, value in exposure.items():
                rows.append(

                    {

                        "currency":
                            currency,

                        "var":
                            round4(value),

                    }

                )

            rows.sort(

                key=lambda x:

                x["var"],

                reverse=True,

            )

            return rows

        # ------------------------------------------------------------------
        # Executive VaR Summary
        # ------------------------------------------------------------------

        def executive_var_summary(
                self,
        ):

            latest = self.calculate_parametric_var()

            return {

                "runtime_id":
                    self.runtime_id,

                "portfolio_id":
                    self.portfolio.portfolio_id,

                "tenant_id":
                    self.tenant_id,

                "user_id":
                    self.user_id,

                "portfolio_value":
                    round4(
                        latest.portfolio_value
                    ),

                "daily_var":
                    round4(
                        latest.daily_var
                    ),

                "weekly_var":
                    round4(
                        latest.weekly_var
                    ),

                "monthly_var":
                    round4(
                        latest.monthly_var
                    ),

                "annualized_volatility":
                    round4(
                        latest.annualized_volatility
                    ),

                "diversification":
                    self.diversification_benefit(),

                "largest_positions":
                    self.position_var_table()[:10],

                "largest_component_var":
                    self.component_var()[:10],

                "currency_var":
                    self.currency_var(),

                "generated_at":
                    utc_now_iso(),

            }

        # =============================================================================
        # File: modules/forex/risk/forex_var_engine.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-1
        #
        # Build 3.3
        #
        # Continue Immediately After Build 3.2
        #
        # Historical VaR Foundation
        # =============================================================================

        # ------------------------------------------------------------------
        # Historical Portfolio Returns
        # ------------------------------------------------------------------

        def historical_portfolio_returns(
                self,
        ) -> List[float]:

            positions = self.portfolio.positions

            if not positions:
                return []

            symbols = []

            for position in positions:

                history = self.get_return_series(
                    position.symbol
                )

                if history is None:
                    continue

                symbols.append(
                    (
                        position,
                        history,
                    )
                )

            if not symbols:
                return []

            observations = min(

                len(history.returns)

                for _, history in symbols

            )

            portfolio_returns = []

            for idx in range(observations):

                daily_return = 0.0

                for position, history in symbols:
                    daily_return += (

                            position.weight

                            *

                            history.returns[idx]

                    )

                portfolio_returns.append(
                    daily_return
                )

            return portfolio_returns

        # ------------------------------------------------------------------
        # Historical Loss Distribution
        # ------------------------------------------------------------------

        def historical_losses(
                self,
        ) -> List[float]:

            portfolio_value = (
                self.portfolio.total_market_value()
            )

            losses = []

            for r in self.historical_portfolio_returns():
                losses.append(

                    -r

                    *

                    portfolio_value

                )

            losses.sort()

            return losses

        # ------------------------------------------------------------------
        # Historical Daily VaR
        # ------------------------------------------------------------------

        def historical_var(
                self,
                confidence=None,
        ) -> float:

            if confidence is None:
                confidence = (
                    self.configuration.confidence
                )

            losses = self.historical_losses()

            if not losses:
                return 0.0

            percentile_index = int(

                len(losses)

                *

                confidence

            )

            percentile_index = min(

                percentile_index,

                len(losses) - 1,

            )

            return abs(

                float(

                    losses[

                        percentile_index

                    ]

                )

            )

        # ------------------------------------------------------------------
        # Historical Weekly VaR
        # ------------------------------------------------------------------

        def historical_weekly_var(
                self,
                confidence=None,
        ):

            return (

                    self.historical_var(

                        confidence

                    )

                    *

                    math.sqrt(5)

            )

        # ------------------------------------------------------------------
        # Historical Monthly VaR
        # ------------------------------------------------------------------

        def historical_monthly_var(
                self,
                confidence=None,
        ):

            return (

                    self.historical_var(

                        confidence

                    )

                    *

                    math.sqrt(21)

            )

        # ------------------------------------------------------------------
        # Rolling Historical VaR
        # ------------------------------------------------------------------

        def rolling_historical_var(
                self,
                window=60,
                confidence=None,
        ):

            if confidence is None:
                confidence = (
                    self.configuration.confidence
                )

            returns = self.historical_portfolio_returns()

            if len(returns) < window:
                return []

            portfolio_value = (
                self.portfolio.total_market_value()
            )

            series = []

            for start in range(

                    0,

                    len(returns) - window + 1,

            ):
                sample = returns[
                    start:start + window
                ]

                losses = [

                    -r * portfolio_value

                    for r in sample

                ]

                losses.sort()

                idx = int(

                    len(losses)

                    *

                    confidence

                )

                idx = min(

                    idx,

                    len(losses) - 1,

                )

                series.append(

                    abs(

                        losses[idx]

                    )

                )

            return series

        # ------------------------------------------------------------------
        # Historical Distribution Statistics
        # ------------------------------------------------------------------

        def historical_statistics(
                self,
        ):

            returns = self.historical_portfolio_returns()

            if not returns:
                return {}

            losses = self.historical_losses()

            return {

                "observations":

                    len(returns),

                "average_return":

                    round4(

                        statistics.mean(

                            returns

                        )

                    ),

                "volatility":

                    round4(

                        statistics.stdev(

                            returns

                        )

                    )

                    if len(returns) > 1

                    else 0.0,

                "best_return":

                    round4(

                        max(

                            returns

                        )

                    ),

                "worst_return":

                    round4(

                        min(

                            returns

                        )

                    ),

                "largest_loss":

                    round4(

                        max(

                            losses

                        )

                    ),

                "smallest_loss":

                    round4(

                        min(

                            losses

                        )

                    ),

            }

        # ------------------------------------------------------------------
        # Historical VaR Result
        # ------------------------------------------------------------------

        def calculate_historical_var(
                self,
                confidence=None,
        ) -> VaRResult:

            if confidence is None:
                confidence = (
                    self.configuration.confidence
                )

            result = VaRResult(

                portfolio_id=
                self.portfolio.portfolio_id,

                tenant_id=
                self.tenant_id,

                user_id=
                self.user_id,

                method=
                VaRMethod.HISTORICAL,

                confidence_level=
                confidence,

                lookback_days=
                self.configuration.lookback_days,

                portfolio_value=
                self.portfolio.total_market_value(),

                portfolio_volatility=
                self.portfolio_standard_deviation(),

                daily_var=
                self.historical_var(
                    confidence
                ),

                weekly_var=
                self.historical_weekly_var(
                    confidence
                ),

                monthly_var=
                self.historical_monthly_var(
                    confidence
                ),

                annualized_volatility=
                self.annualized_volatility(),

            )

            self.latest_var = result

            self.statistics[
                "historical_runs"
            ] += 1

            return result

        # =============================================================================
        # File: modules/forex/risk/forex_var_engine.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-1
        #
        # Build 3.4
        #
        # Continue Immediately After Build 3.3
        #
        # Expected Shortfall (CVaR)
        # Tail Risk Analytics
        # =============================================================================

        # ------------------------------------------------------------------
        # Tail Losses
        # ------------------------------------------------------------------

        def tail_losses(
                self,
                confidence=None,
        ) -> List[float]:

            if confidence is None:
                confidence = self.configuration.confidence

            losses = self.historical_losses()

            if not losses:
                return []

            cutoff = self.historical_var(
                confidence
            )

            tail = [

                loss

                for loss in losses

                if loss >= cutoff

            ]

            return sorted(tail)

        # ------------------------------------------------------------------
        # Expected Shortfall
        # ------------------------------------------------------------------

        def expected_shortfall(
                self,
                confidence=None,
        ) -> float:

            tail = self.tail_losses(
                confidence
            )

            if not tail:
                return 0.0

            return float(

                statistics.mean(
                    tail
                )

            )

        # ------------------------------------------------------------------
        # Conditional VaR
        # ------------------------------------------------------------------

        def conditional_var(
                self,
                confidence=None,
        ) -> float:

            return self.expected_shortfall(
                confidence
            )

        # ------------------------------------------------------------------
        # Worst Historical Loss
        # ------------------------------------------------------------------

        def worst_loss(
                self,
        ) -> float:

            losses = self.historical_losses()

            if not losses:
                return 0.0

            return max(losses)

        # ------------------------------------------------------------------
        # Average Tail Loss
        # ------------------------------------------------------------------

        def average_tail_loss(
                self,
                confidence=None,
        ) -> float:

            tail = self.tail_losses(
                confidence
            )

            if not tail:
                return 0.0

            return statistics.mean(
                tail
            )

        # ------------------------------------------------------------------
        # Tail Observation Count
        # ------------------------------------------------------------------

        def tail_observation_count(
                self,
                confidence=None,
        ) -> int:

            return len(

                self.tail_losses(
                    confidence
                )

            )

        # ------------------------------------------------------------------
        # Expected Shortfall Result
        # ------------------------------------------------------------------

        def calculate_expected_shortfall(
                self,
                confidence=None,
        ) -> ExpectedShortfallResult:

            if confidence is None:
                confidence = (
                    self.configuration.confidence
                )

            result = ExpectedShortfallResult(

                portfolio_id=
                self.portfolio.portfolio_id,

                confidence_level=
                confidence,

                expected_shortfall=
                self.expected_shortfall(
                    confidence
                ),

                tail_observations=
                self.tail_observation_count(
                    confidence
                ),

                worst_loss=
                self.worst_loss(),

                average_tail_loss=
                self.average_tail_loss(
                    confidence
                ),

            )

            self.latest_expected_shortfall = result

            return result

        # ------------------------------------------------------------------
        # Tail Distribution
        # ------------------------------------------------------------------

        def tail_distribution(
                self,
                confidence=None,
        ):

            rows = []

            for idx, loss in enumerate(

                    self.tail_losses(
                        confidence
                    )

            ):
                rows.append(

                    {

                        "rank":

                            idx + 1,

                        "loss":

                            round4(loss),

                    }

                )

            return rows

        # ------------------------------------------------------------------
        # Parametric vs Historical
        # ------------------------------------------------------------------

        def var_comparison(
                self,
                confidence=None,
        ):

            if confidence is None:
                confidence = self.configuration.confidence

            parametric = self.daily_var(
                confidence
            )

            historical = self.historical_var(
                confidence
            )

            expected = self.expected_shortfall(
                confidence
            )

            difference = (

                    historical

                    -

                    parametric

            )

            return {

                "confidence":

                    confidence,

                "parametric":

                    round4(parametric),

                "historical":

                    round4(historical),

                "expected_shortfall":

                    round4(expected),

                "difference":

                    round4(difference),

                "difference_pct":

                    round4(

                        (

                                difference

                                /

                                parametric

                        )

                        if parametric

                        else 0.0

                    ),

            }

        # ------------------------------------------------------------------
        # Historical Risk Summary
        # ------------------------------------------------------------------

        def historical_risk_summary(
                self,
        ):

            stats = self.historical_statistics()

            comparison = self.var_comparison()

            return {

                "portfolio_id":

                    self.portfolio.portfolio_id,

                "tenant_id":

                    self.tenant_id,

                "user_id":

                    self.user_id,

                "statistics":

                    stats,

                "comparison":

                    comparison,

                "tail_observations":

                    self.tail_observation_count(),

                "worst_loss":

                    round4(

                        self.worst_loss()

                    ),

                "expected_shortfall":

                    round4(

                        self.expected_shortfall()

                    ),

                "generated_at":

                    utc_now_iso(),

            }

        # ------------------------------------------------------------------
        # Dashboard Packet
        # ------------------------------------------------------------------

        def historical_dashboard_packet(
                self,
        ):

            return {

                "status":

                    "success",

                "generated_at":

                    utc_now_iso(),

                "historical_var":

                    self.calculate_historical_var().to_dict(),

                "expected_shortfall":

                    self.calculate_expected_shortfall().to_dict(),

                "summary":

                    self.historical_risk_summary(),

                "tail_distribution":

                    self.tail_distribution(),

                "rolling_var":

                    self.rolling_historical_var(),

            }

        # =============================================================================
        # File: modules/forex/risk/forex_var_engine.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-1
        #
        # Build 3.5
        #
        # Continue Immediately After Build 3.4
        #
        # Monte Carlo VaR Engine
        # =============================================================================

        # ------------------------------------------------------------------
        # Random Return Generator
        # ------------------------------------------------------------------

        def simulated_returns(
                self,
                runs=None,
        ):

            if runs is None:
                runs = self.configuration.monte_carlo_runs

            portfolio_returns = self.historical_portfolio_returns()

            if len(portfolio_returns) < 2:
                return np.array([])

            mu = np.mean(portfolio_returns)

            sigma = np.std(
                portfolio_returns,
                ddof=1,
            )

            return np.random.normal(
                loc=mu,
                scale=sigma,
                size=runs,
            )

        # ------------------------------------------------------------------
        # Simulated Portfolio Values
        # ------------------------------------------------------------------

        def simulated_portfolio_values(
                self,
                runs=None,
        ):

            values = []

            initial_value = (
                self.portfolio.total_market_value()
            )

            simulated = self.simulated_returns(
                runs
            )

            for daily_return in simulated:
                values.append(

                    initial_value

                    *

                    (

                            1.0

                            +

                            daily_return

                    )

                )

            return values

        # ------------------------------------------------------------------
        # Simulated Loss Distribution
        # ------------------------------------------------------------------

        def simulated_losses(
                self,
                runs=None,
        ):

            initial_value = (
                self.portfolio.total_market_value()
            )

            losses = []

            for value in self.simulated_portfolio_values(
                    runs
            ):
                losses.append(

                    initial_value

                    -

                    value

                )

            losses.sort()

            return losses

        # ------------------------------------------------------------------
        # Monte Carlo VaR
        # ------------------------------------------------------------------

        def monte_carlo_var(
                self,
                confidence=None,
                runs=None,
        ):

            if confidence is None:
                confidence = (
                    self.configuration.confidence
                )

            losses = self.simulated_losses(
                runs
            )

            if not losses:
                return 0.0

            index = int(

                confidence

                *

                len(losses)

            )

            index = min(
                index,
                len(losses) - 1,
            )

            return abs(

                losses[index]

            )

        # ------------------------------------------------------------------
        # Monte Carlo Expected Shortfall
        # ------------------------------------------------------------------

        def monte_carlo_expected_shortfall(
                self,
                confidence=None,
                runs=None,
        ):

            if confidence is None:
                confidence = (
                    self.configuration.confidence
                )

            cutoff = self.monte_carlo_var(
                confidence,
                runs,
            )

            tail = [

                x

                for x in self.simulated_losses(
                    runs
                )

                if x >= cutoff

            ]

            if not tail:
                return 0.0

            return statistics.mean(
                tail
            )

        # ------------------------------------------------------------------
        # Monte Carlo Summary
        # ------------------------------------------------------------------

        def monte_carlo_summary(
                self,
                runs=None,
        ):

            values = self.simulated_portfolio_values(
                runs
            )

            if not values:
                return {}

            return {

                "minimum":

                    round4(
                        min(values)
                    ),

                "maximum":

                    round4(
                        max(values)
                    ),

                "average":

                    round4(
                        statistics.mean(values)
                    ),

                "median":

                    round4(
                        statistics.median(values)
                    ),

                "std_dev":

                    round4(
                        statistics.stdev(values)
                    )
                    if len(values) > 1
                    else 0.0,

            }

        # ------------------------------------------------------------------
        # Monte Carlo Percentiles
        # ------------------------------------------------------------------

        def monte_carlo_percentiles(
                self,
                runs=None,
        ):

            values = self.simulated_portfolio_values(
                runs
            )

            if not values:
                return {}

            arr = np.array(values)

            return {

                "1":

                    round4(
                        np.percentile(arr, 1)
                    ),

                "5":

                    round4(
                        np.percentile(arr, 5)
                    ),

                "25":

                    round4(
                        np.percentile(arr, 25)
                    ),

                "50":

                    round4(
                        np.percentile(arr, 50)
                    ),

                "75":

                    round4(
                        np.percentile(arr, 75)
                    ),

                "95":

                    round4(
                        np.percentile(arr, 95)
                    ),

                "99":

                    round4(
                        np.percentile(arr, 99)
                    ),

            }

        # ------------------------------------------------------------------
        # Calculate Monte Carlo
        # ------------------------------------------------------------------

        def calculate_monte_carlo(
                self,
                confidence=None,
                runs=None,
        ):

            if confidence is None:
                confidence = (
                    self.configuration.confidence
                )

            if runs is None:
                runs = (
                    self.configuration.monte_carlo_runs
                )

            values = self.simulated_portfolio_values(
                runs
            )

            result = MonteCarloSimulation(

                runs=runs,

                confidence_level=confidence,

                mean_return=

                statistics.mean(values)
                if values
                else 0.0,

                median_return=

                statistics.median(values)
                if values
                else 0.0,

                best_case=

                max(values)
                if values
                else 0.0,

                worst_case=

                min(values)
                if values
                else 0.0,

                percentile_95=

                self.monte_carlo_var(
                    VAR_95,
                    runs,
                ),

                percentile_99=

                self.monte_carlo_var(
                    VAR_99,
                    runs,
                ),

                expected_shortfall=

                self.monte_carlo_expected_shortfall(
                    confidence,
                    runs,
                ),

            )

            self.latest_monte_carlo = result

            self.statistics[
                "calculations"
            ] += 1

            return result

        # ------------------------------------------------------------------
        # Dashboard Packet
        # ------------------------------------------------------------------

        def monte_carlo_dashboard_packet(
                self,
        ):

            result = self.calculate_monte_carlo()

            return {

                "status":

                    "success",

                "generated_at":

                    utc_now_iso(),

                "simulation":

                    result.to_dict(),

                "summary":

                    self.monte_carlo_summary(),

                "percentiles":

                    self.monte_carlo_percentiles(),

            }

        # =============================================================================
        # File: modules/forex/risk/forex_var_engine.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-1
        #
        # Build 4.1
        #
        # Continue Immediately After Build 3.5
        #
        # Institutional Stress Testing Engine
        # =============================================================================

        # =============================================================================
        # Stress Test Framework
        # =============================================================================

        # ------------------------------------------------------------------
        # Register Scenario
        # ------------------------------------------------------------------

        def register_scenario(
                self,
                scenario: StressScenario,
                shock_pct: float,
                description: str,
        ):

            if not hasattr(self, "_stress_library"):
                self._stress_library = {}

            self._stress_library[
                scenario.value
            ] = {

                "scenario": scenario,

                "shock_pct": shock_pct,

                "description": description,

            }

        # ------------------------------------------------------------------
        # Load Default Scenarios
        # ------------------------------------------------------------------

        def load_default_scenarios(
                self,
        ):

            self.register_scenario(

                StressScenario.RATE_SHOCK,

                -0.020,

                "Interest Rate Shock",

            )

            self.register_scenario(

                StressScenario.USD_SURGE,

                -0.050,

                "USD Appreciates 5%",

            )

            self.register_scenario(

                StressScenario.USD_COLLAPSE,

                0.050,

                "USD Weakens 5%",

            )

            self.register_scenario(

                StressScenario.FLASH_CRASH,

                -0.100,

                "Flash Crash",

            )

            self.register_scenario(

                StressScenario.VOLATILITY,

                -0.075,

                "Volatility Spike",

            )

            self.register_scenario(

                StressScenario.LIQUIDITY,

                -0.035,

                "Liquidity Event",

            )

            self.register_scenario(

                StressScenario.CENTRAL_BANK,

                -0.060,

                "Central Bank Intervention",

            )

        # ------------------------------------------------------------------
        # Scenario Library
        # ------------------------------------------------------------------

        def scenarios(self):

            if not hasattr(

                    self,

                    "_stress_library",

            ):
                self.load_default_scenarios()

            return self._stress_library

        # ------------------------------------------------------------------
        # Apply Portfolio Shock
        # ------------------------------------------------------------------

        def apply_portfolio_shock(

                self,

                shock_pct,

        ):

            before = self.portfolio.total_market_value()

            after = before * (

                    1.0 + shock_pct

            )

            pnl = after - before

            pnl_pct = (

                pnl / before

                if before

                else 0.0

            )

            return before, after, pnl, pnl_pct

        # ------------------------------------------------------------------
        # Execute Scenario
        # ------------------------------------------------------------------

        def execute_scenario(

                self,

                scenario_name,

        ):

            library = self.scenarios()

            if scenario_name not in library:
                raise ValueError(

                    f"Unknown scenario: {scenario_name}"

                )

            scenario = library[

                scenario_name

            ]

            before, after, pnl, pct = (

                self.apply_portfolio_shock(

                    scenario["shock_pct"]

                )

            )

            passed = abs(

                pct

            ) < 0.10

            result = StressScenarioResult(

                scenario=scenario["scenario"],

                portfolio_before=before,

                portfolio_after=after,

                pnl_change=pnl,

                pnl_percent=pct,

                passed=passed,

                notes=scenario["description"],

                metadata={

                    "shock_pct":

                        scenario["shock_pct"]

                },

            )

            self.latest_stress_results.append(

                result

            )

            self.statistics[

                "stress_runs"

            ] += 1

            return result

        # ------------------------------------------------------------------
        # Execute All Scenarios
        # ------------------------------------------------------------------

        def execute_all_scenarios(
                self,
        ):

            results = []

            for scenario in self.scenarios():
                results.append(

                    self.execute_scenario(

                        scenario

                    )

                )

            return results

        # ------------------------------------------------------------------
        # Scenario Summary
        # ------------------------------------------------------------------

        def stress_summary(
                self,
        ):

            results = self.execute_all_scenarios()

            passed = sum(

                1

                for r in results

                if r.passed

            )

            failed = len(results) - passed

            return {

                "total":

                    len(results),

                "passed":

                    passed,

                "failed":

                    failed,

                "worst_case":

                    min(

                        (

                            r.pnl_percent

                            for r in results

                        ),

                        default=0.0,

                    ),

                "best_case":

                    max(

                        (

                            r.pnl_percent

                            for r in results

                        ),

                        default=0.0,

                    ),

            }

        # ------------------------------------------------------------------
        # Stress Table
        # ------------------------------------------------------------------

        def stress_table(
                self,
        ):

            rows = []

            for result in self.execute_all_scenarios():
                rows.append({

                    "scenario":

                        result.scenario.value,

                    "before":

                        round4(

                            result.portfolio_before

                        ),

                    "after":

                        round4(

                            result.portfolio_after

                        ),

                    "pnl":

                        round4(

                            result.pnl_change

                        ),

                    "pnl_pct":

                        round4(

                            result.pnl_percent

                        ),

                    "passed":

                        result.passed,

                })

            rows.sort(

                key=lambda x:

                x["pnl_pct"]

            )

            return rows

        # =============================================================================
        # File: modules/forex/risk/forex_var_engine.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-1
        #
        # Build 4.2
        #
        # Continue Immediately After Build 4.1
        #
        # Advanced Institutional Stress Testing
        # =============================================================================

        # ------------------------------------------------------------------
        # Currency Shock
        # ------------------------------------------------------------------

        def currency_shock(

                self,

                currency: str,

                shock_pct: float,

        ):

            before = self.portfolio.total_market_value()

            impact = 0.0

            affected_positions = 0

            for position in self.portfolio.positions:

                if (

                        position.base_currency == currency

                        or

                        position.quote_currency == currency

                ):
                    affected_positions += 1

                    impact += (

                            position.market_value

                            * shock_pct

                            * position.weight

                    )

            after = before + impact

            return {

                "currency": currency,

                "shock_pct": shock_pct,

                "affected_positions": affected_positions,

                "portfolio_before": before,

                "portfolio_after": after,

                "portfolio_change": impact,

                "portfolio_change_pct":

                    impact / before if before else 0.0,

            }

        # ------------------------------------------------------------------
        # FX Pair Shock
        # ------------------------------------------------------------------

        def pair_shock(

                self,

                symbol: str,

                shock_pct: float,

        ):

            before = self.portfolio.total_market_value()

            impact = 0.0

            affected = 0

            for position in self.portfolio.positions:

                if position.symbol != symbol:
                    continue

                affected += 1

                impact += (

                        position.market_value

                        * shock_pct

                )

            after = before + impact

            return {

                "symbol": symbol,

                "shock_pct": shock_pct,

                "affected_positions": affected,

                "portfolio_before": before,

                "portfolio_after": after,

                "change": impact,

                "change_pct":

                    impact / before if before else 0.0,

            }

        # ------------------------------------------------------------------
        # Correlation Breakdown
        # ------------------------------------------------------------------

        def correlation_breakdown_scenario(

                self,

                reduction=0.50,

        ):

            matrix = self.correlation_matrix_dataframe()

            if matrix.empty:
                return {}

            shocked = matrix.copy()

            for row in shocked.index:

                for col in shocked.columns:

                    if row == col:
                        continue

                    shocked.loc[row, col] *= (

                            1.0 - reduction

                    )

            average_before = (

                matrix.values.mean()

            )

            average_after = (

                shocked.values.mean()

            )

            return {

                "reduction":

                    reduction,

                "average_before":

                    round4(average_before),

                "average_after":

                    round4(average_after),

                "delta":

                    round4(

                        average_after

                        - average_before

                    ),

            }

        # ------------------------------------------------------------------
        # Volatility Shock
        # ------------------------------------------------------------------

        def volatility_shock(

                self,

                multiplier=1.50,

        ):

            rows = []

            for position in self.portfolio.positions:
                original = position.volatility

                shocked = (

                        original

                        * multiplier

                )

                rows.append({

                    "symbol":

                        position.symbol,

                    "original":

                        round4(original),

                    "shocked":

                        round4(shocked),

                    "change_pct":

                        round4(

                            multiplier - 1.0

                        ),

                })

            return rows

        # ------------------------------------------------------------------
        # Margin Stress
        # ------------------------------------------------------------------

        def margin_stress(

                self,

                increase_pct=0.25,

        ):

            current = self.portfolio.margin_used

            stressed = (

                    current

                    * (1.0 + increase_pct)

            )

            available = max(

                self.portfolio.margin_available

                - (stressed - current),

                0.0,

            )

            return {

                "margin_used":

                    round4(current),

                "stressed_margin":

                    round4(stressed),

                "remaining_margin":

                    round4(available),

                "increase_pct":

                    round4(increase_pct),

            }

        # ------------------------------------------------------------------
        # Liquidity Stress
        # ------------------------------------------------------------------

        def liquidity_stress(

                self,

                haircut=0.15,

        ):

            before = self.portfolio.total_market_value()

            after = before * (

                    1.0 - haircut

            )

            return {

                "portfolio_before":

                    round4(before),

                "portfolio_after":

                    round4(after),

                "haircut":

                    haircut,

                "loss":

                    round4(before - after),

            }

        # ------------------------------------------------------------------
        # Survivability Score
        # ------------------------------------------------------------------

        def survivability_score(

                self,

        ):

            leverage = self.portfolio.portfolio_leverage()

            exposure = self.portfolio.total_exposure()

            equity = max(

                self.portfolio.equity,

                1.0,

            )

            exposure_ratio = (

                    exposure

                    / equity

            )

            score = 100.0

            score -= leverage * 8.0

            score -= exposure_ratio * 2.0

            score -= (

                             self.daily_var()

                             /

                             equity

                     ) * 100.0

            score = max(

                0.0,

                min(

                    100.0,

                    score,

                ),

            )

            if score >= 85:

                rating = "Excellent"

            elif score >= 70:

                rating = "Strong"

            elif score >= 55:

                rating = "Moderate"

            elif score >= 40:

                rating = "Weak"

            else:

                rating = "Critical"

            return {

                "score":

                    round4(score),

                "rating":

                    rating,

                "leverage":

                    round4(leverage),

                "exposure_ratio":

                    round4(exposure_ratio),

            }

        # ------------------------------------------------------------------
        # Stress Ranking
        # ------------------------------------------------------------------

        def stress_ranking(

                self,

        ):

            rankings = []

            for scenario in self.scenarios():
                result = self.execute_scenario(

                    scenario

                )

                rankings.append({

                    "scenario":

                        result.scenario.value,

                    "portfolio_change":

                        round4(

                            result.pnl_change

                        ),

                    "portfolio_change_pct":

                        round4(

                            result.pnl_percent

                        ),

                    "passed":

                        result.passed,

                })

            rankings.sort(

                key=lambda row:

                row["portfolio_change_pct"]

            )

            return rankings

        # =============================================================================
        # File: modules/forex/risk/forex_var_engine.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-1
        #
        # Build 4.3
        #
        # Continue Immediately After Build 4.2
        #
        # Executive Stress Intelligence
        # =============================================================================

        # ------------------------------------------------------------------
        # Historical Crisis Library
        # ------------------------------------------------------------------

        def historical_crisis_library(self):

            return [

                {
                    "name": "Global Financial Crisis",
                    "year": 2008,
                    "equity_shock": -0.42,
                    "volatility_multiplier": 3.20,
                    "fx_shock": -0.15,
                    "liquidity_haircut": 0.30,
                },

                {
                    "name": "Swiss Franc Unpeg",
                    "year": 2015,
                    "equity_shock": -0.18,
                    "volatility_multiplier": 4.50,
                    "fx_shock": -0.30,
                    "liquidity_haircut": 0.20,
                },

                {
                    "name": "Brexit Referendum",
                    "year": 2016,
                    "equity_shock": -0.11,
                    "volatility_multiplier": 2.00,
                    "fx_shock": -0.12,
                    "liquidity_haircut": 0.10,
                },

                {
                    "name": "COVID Market Crash",
                    "year": 2020,
                    "equity_shock": -0.35,
                    "volatility_multiplier": 3.80,
                    "fx_shock": -0.18,
                    "liquidity_haircut": 0.25,
                },

                {
                    "name": "UK Flash Crash",
                    "year": 2016,
                    "equity_shock": -0.08,
                    "volatility_multiplier": 2.80,
                    "fx_shock": -0.11,
                    "liquidity_haircut": 0.12,
                },

            ]

        # ------------------------------------------------------------------
        # Replay Historical Crisis
        # ------------------------------------------------------------------

        def replay_crisis(
                self,
                crisis_name: str,
        ):

            portfolio = self.portfolio.total_market_value()

            for crisis in self.historical_crisis_library():

                if crisis["name"] != crisis_name:
                    continue

                after = portfolio * (
                        1.0 + crisis["equity_shock"]
                )

                return {

                    "crisis":
                        crisis,

                    "portfolio_before":
                        portfolio,

                    "portfolio_after":
                        after,

                    "loss":
                        portfolio - after,

                    "loss_pct":
                        -crisis["equity_shock"],

                }

            return {}

        # ------------------------------------------------------------------
        # Composite Stress Score
        # ------------------------------------------------------------------

        def composite_stress_score(self):

            score = 100.0

            leverage = self.portfolio.portfolio_leverage()

            exposure = self.portfolio.total_exposure()

            equity = max(
                self.portfolio.equity,
                1.0,
            )

            score -= leverage * 8.0

            score -= (
                             exposure / equity
                     ) * 1.50

            score -= (

                             self.daily_var()

                             / equity

                     ) * 100.0

            score -= (

                             self.expected_shortfall()

                             / equity

                     ) * 100.0

            score = max(
                0.0,
                min(
                    100.0,
                    score,
                ),
            )

            return round4(score)

        # ------------------------------------------------------------------
        # Traffic Light Rating
        # ------------------------------------------------------------------

        def traffic_light_rating(self):

            score = self.composite_stress_score()

            if score >= 80:
                return {

                    "status": "GREEN",

                    "message":
                        "Portfolio operating within normal institutional limits.",

                }

            if score >= 60:
                return {

                    "status": "YELLOW",

                    "message":
                        "Moderate stress detected. Increased monitoring recommended.",

                }

            if score >= 40:
                return {

                    "status": "ORANGE",

                    "message":
                        "Elevated portfolio risk. Consider reducing exposure.",

                }

            return {

                "status": "RED",

                "message":
                    "Critical portfolio stress. Immediate review recommended.",

            }

        # ------------------------------------------------------------------
        # Executive Stress Scorecard
        # ------------------------------------------------------------------

        def executive_stress_scorecard(self):

            return {

                "portfolio":

                    self.portfolio.portfolio_id,

                "tenant":

                    self.tenant_id,

                "user":

                    self.user_id,

                "generated":

                    utc_now_iso(),

                "daily_var":

                    round4(
                        self.daily_var()
                    ),

                "historical_var":

                    round4(
                        self.historical_var()
                    ),

                "expected_shortfall":

                    round4(
                        self.expected_shortfall()
                    ),

                "stress_score":

                    self.composite_stress_score(),

                "traffic":

                    self.traffic_light_rating(),

                "survivability":

                    self.survivability_score(),

                "diversification":

                    self.diversification_benefit(),

                "currency_exposure":

                    self.currency_exposure(),

                "largest_risk_positions":

                    self.largest_risk_positions(5),

            }

        # ------------------------------------------------------------------
        # Stress Dashboard Packet
        # ------------------------------------------------------------------

        def stress_dashboard_packet(self):

            return {

                "status":

                    "success",

                "generated_at":

                    utc_now_iso(),

                "summary":

                    self.stress_summary(),

                "executive":

                    self.executive_stress_scorecard(),

                "traffic":

                    self.traffic_light_rating(),

                "ranking":

                    self.stress_ranking(),

                "scenarios":

                    self.stress_table(),

                "survivability":

                    self.survivability_score(),

            }

        # ------------------------------------------------------------------
        # Persist Stress History
        # ------------------------------------------------------------------

        def persist_stress_history(self):

            if self.db is None:
                return

            try:

                payload = json.dumps(
                    self.stress_dashboard_packet()
                )

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

                            self.portfolio.portfolio_id,

                        "runtime":

                            self.runtime_id,

                        "generated":

                            utc_now(),

                        "payload":

                            payload,

                    },

                )

                if hasattr(self.db, "commit"):
                    self.db.commit()

            except Exception as exc:

                logger.warning(

                    "Unable to persist stress history: %s",

                    exc,

                )

        # ------------------------------------------------------------------
        # Public Stress API
        # ------------------------------------------------------------------

        def run_full_stress_suite(self):

            packet = self.stress_dashboard_packet()

            self.persist_stress_history()

            return packet

        # =============================================================================
        # File: modules/forex/risk/forex_var_engine.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-1
        #
        # Build 5.1
        #
        # Continue Immediately After Build 4.3
        #
        # Runtime History
        # Persistence
        # Dashboard Integration
        # =============================================================================

        # ------------------------------------------------------------------
        # Record VaR History
        # ------------------------------------------------------------------

        def record_var_history(

                self,

                result: Optional[VaRResult] = None,

        ) -> VaRHistoryRecord:

            if result is None:

                if self.latest_var is None:

                    result = self.calculate_parametric_var()

                else:

                    result = self.latest_var

            expected = self.calculate_expected_shortfall()

            record = VaRHistoryRecord(

                runtime_id=self.runtime_id,

                portfolio_id=self.portfolio.portfolio_id,

                tenant_id=self.tenant_id,

                user_id=self.user_id,

                var_95=self.daily_var(VAR_95),

                var_99=self.daily_var(VAR_99),

                expected_shortfall=expected.expected_shortfall,

                portfolio_value=result.portfolio_value,

                volatility=result.portfolio_volatility,

                method=result.method.value,

                generated_at=utc_now_iso(),

            )

            self.var_history.append(record)

            return record

        # ------------------------------------------------------------------
        # Record Analytics Snapshot
        # ------------------------------------------------------------------

        def record_snapshot(self):

            snapshot = PortfolioAnalyticsSnapshot(

                snapshot_id=str(uuid.uuid4()),

                portfolio_id=self.portfolio.portfolio_id,

                timestamp=utc_now_iso(),

                equity=self.portfolio.equity,

                exposure=self.portfolio.total_exposure(),

                leverage=self.portfolio.portfolio_leverage(),

                margin_used=self.portfolio.margin_used,

                margin_available=self.portfolio.margin_available,

                portfolio_return=self.latest_statistics.average_daily_return
                if self.latest_statistics
                else 0.0,

                drawdown=self.worst_loss(),

                volatility=self.portfolio_standard_deviation(),

                var95=self.daily_var(VAR_95),

                var99=self.daily_var(VAR_99),

                expected_shortfall=self.expected_shortfall(),

            )

            self.analytics_history.append(

                snapshot

            )

            return snapshot

        # ------------------------------------------------------------------
        # Historical Trend
        # ------------------------------------------------------------------

        def historical_trend(self):

            rows = []

            for record in self.var_history:
                rows.append(

                    {

                        "runtime":

                            record.runtime_id,

                        "generated":

                            record.generated_at,

                        "var95":

                            record.var_95,

                        "var99":

                            record.var_99,

                        "expected_shortfall":

                            record.expected_shortfall,

                        "portfolio_value":

                            record.portfolio_value,

                        "volatility":

                            record.volatility,

                        "method":

                            record.method,

                    }

                )

            return rows

        # ------------------------------------------------------------------
        # Persist History
        # ------------------------------------------------------------------

        def persist_history(

                self,

                record: Optional[VaRHistoryRecord] = None,

        ):

            if self.db is None:
                return

            if record is None:
                record = self.record_var_history()

            try:

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

                            record.tenant_id,

                        "user":

                            record.user_id,

                        "portfolio":

                            record.portfolio_id,

                        "runtime":

                            record.runtime_id,

                        "method":

                            record.method,

                        "var95":

                            record.var_95,

                        "var99":

                            record.var_99,

                        "es":

                            record.expected_shortfall,

                        "vol":

                            record.volatility,

                        "value":

                            record.portfolio_value,

                        "generated":

                            utc_now(),

                        "payload":

                            json.dumps(

                                record.to_dict()

                            ),

                    },

                )

                if hasattr(

                        self.db,

                        "commit",

                ):
                    self.db.commit()

            except Exception as exc:

                logger.warning(

                    "Unable to persist VaR history: %s",

                    exc,

                )

        # ------------------------------------------------------------------
        # Dashboard Packet
        # ------------------------------------------------------------------

        def dashboard_packet(self):

            var = self.calculate_parametric_var()

            historical = self.calculate_historical_var()

            expected = self.calculate_expected_shortfall()

            monte = self.calculate_monte_carlo()

            return {

                "status":

                    "success",

                "generated_at":

                    utc_now_iso(),

                "runtime_id":

                    self.runtime_id,

                "identity":

                    self.identity,

                "portfolio":

                    self.portfolio_summary(),

                "statistics":

                    self.build_portfolio_statistics().to_dict(),

                "parametric":

                    var.to_dict(),

                "historical":

                    historical.to_dict(),

                "expected_shortfall":

                    expected.to_dict(),

                "monte_carlo":

                    monte.to_dict(),

                "stress":

                    self.stress_dashboard_packet(),

                "history":

                    self.historical_trend(),

            }

        # ------------------------------------------------------------------
        # Export
        # ------------------------------------------------------------------

        def export_json(self):

            return json.dumps(

                self.dashboard_packet(),

                indent=2,

            )

        # ------------------------------------------------------------------
        # Export Dictionary
        # ------------------------------------------------------------------

        def to_dict(self):

            return self.dashboard_packet()

    # =============================================================================
    # Singleton
    # =============================================================================

    _VAR_ENGINE = None

    def get_forex_var_engine(

            db=None,

            tenant_id=None,

            user_id=None,

            portfolio_id=None,

    ):

        global _VAR_ENGINE

        if (

                _VAR_ENGINE is None

                or _VAR_ENGINE.db is not db

                or _VAR_ENGINE.tenant_id != tenant_id

                or _VAR_ENGINE.user_id != user_id

                or _VAR_ENGINE.portfolio_id != portfolio_id

        ):
            _VAR_ENGINE = ForexVaREngine(

                db=db,

                tenant_id=tenant_id,

                user_id=user_id,

                portfolio_id=portfolio_id,

            )

        return _VAR_ENGINE