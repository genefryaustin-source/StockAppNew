# modules/forex/forex_autonomous_trader.py

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from modules.forex.forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
        ForexService,
        get_forex_service,
    )

    from modules.forex.forex_alpha_model import (
        ForexAlphaModel,
        get_forex_alpha_model,
    )

    from modules.forex.forex_portfolio_optimizer import (
        ForexPortfolioOptimizer,
        get_forex_portfolio_optimizer,
    )

    from modules.forex.forex_strategy_lab import (
        ForexStrategyLab,
        get_forex_strategy_lab,
    )

    from modules.forex.forex_trading_engine import (
        ForexTradingEngine,
        get_forex_trading_engine,
    )

    from modules.forex.forex_trade_management_engine import (
        ForexTradeManagementEngine,
        get_forex_trade_management_engine,
    )

    from modules.forex.forex_risk_dashboard import (
        render_forex_risk_dashboard,
    )

except Exception:

    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
        ForexService,
        get_forex_service,
    )

    from forex_alpha_model import (
        ForexAlphaModel,
        get_forex_alpha_model,
    )

    from forex_portfolio_optimizer import (
        ForexPortfolioOptimizer,
        get_forex_portfolio_optimizer,
    )

    from forex_strategy_lab import (
        ForexStrategyLab,
        get_forex_strategy_lab,
    )

    from forex_trading_engine import (
        ForexTradingEngine,
        get_forex_trading_engine,
    )

    from forex_trade_management_engine import (
        ForexTradeManagementEngine,
        get_forex_trade_management_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


@dataclass
class ForexAutonomousDecision:
    decision_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair: str

    alpha_score: float
    strategy_score: float
    optimizer_weight: float
    confidence_score: float
    risk_score: float

    action: str
    side: str
    order_type: str
    suggested_units: float
    target_weight: float

    entry_price: float
    stop_price: float
    target_price: float

    decision_status: str
    execution_status: str

    rationale: str
    warnings: str

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class ForexAutonomousRun:
    run_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair_count: int

    buy_count: int
    sell_count: int
    hold_count: int
    rejected_count: int
    executed_count: int

    mode: str
    status: str

    decisions: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


class ForexAutonomousTrader:
    """
    Forex Autonomous Trader

    Decision and execution orchestration layer.

    Safety defaults:
    - Paper mode by default
    - Requires explicit auto_execute=True to submit orders
    - Uses tenant/user/portfolio explicit state
    - No global runtime state
    """

    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        db: Any = None,
        forex_service: Optional[ForexService] = None,
        alpha_model: Optional[ForexAlphaModel] = None,
        optimizer: Optional[ForexPortfolioOptimizer] = None,
        strategy_lab: Optional[ForexStrategyLab] = None,
        trading_engine: Optional[ForexTradingEngine] = None,
        trade_management_engine: Optional[ForexTradeManagementEngine] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id
        self.db = db

        self.forex_service = (
            forex_service
            or get_forex_service(
                tenant_id=tenant_id,
                user_id=user_id,
                db=db,
            )
        )

        self.alpha_model = (
            alpha_model
            or get_forex_alpha_model(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

        self.optimizer = (
            optimizer
            or get_forex_portfolio_optimizer(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

        self.strategy_lab = (
            strategy_lab
            or get_forex_strategy_lab(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

        self.trading_engine = (
            trading_engine
            or get_forex_trading_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

        self.trade_management_engine = (
            trade_management_engine
            or get_forex_trade_management_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

    # =====================================================
    # Database
    # =====================================================

    def ensure_tables(self) -> None:
        if self.db is None:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_autonomous_decisions (
                decision_id VARCHAR(64) PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair VARCHAR(20),

                alpha_score DOUBLE PRECISION,
                strategy_score DOUBLE PRECISION,
                optimizer_weight DOUBLE PRECISION,
                confidence_score DOUBLE PRECISION,
                risk_score DOUBLE PRECISION,

                action VARCHAR(40),
                side VARCHAR(20),
                order_type VARCHAR(40),
                suggested_units DOUBLE PRECISION,
                target_weight DOUBLE PRECISION,

                entry_price DOUBLE PRECISION,
                stop_price DOUBLE PRECISION,
                target_price DOUBLE PRECISION,

                decision_status VARCHAR(60),
                execution_status VARCHAR(60),

                rationale TEXT,
                warnings TEXT,

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_autonomous_runs (
                run_id VARCHAR(64) PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair_count INTEGER,

                buy_count INTEGER,
                sell_count INTEGER,
                hold_count INTEGER,
                rejected_count INTEGER,
                executed_count INTEGER,

                mode VARCHAR(40),
                status VARCHAR(60),

                payload JSONB,

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_auto_decisions_tenant_created
            ON forex_autonomous_decisions(tenant_id, created_at DESC)
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_auto_runs_tenant_created
            ON forex_autonomous_runs(tenant_id, created_at DESC)
            """
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    # =====================================================
    # Helpers
    # =====================================================

    def _safe_float(
        self,
        value: Any,
        default: float = 0.0,
    ) -> float:
        try:
            if value is None:
                return default

            result = float(value)

            if math.isnan(result) or math.isinf(result):
                return default

            return result

        except Exception:
            return default

    def _clip(
        self,
        value: float,
        low: float = 0.0,
        high: float = 100.0,
    ) -> float:
        return max(low, min(high, float(value)))

    def _quote_price(
        self,
        pair: str,
    ) -> float:
        try:
            quote = self.forex_service.get_quote(pair)
            return self._safe_float(
                getattr(quote, "price", None),
                1.0,
            )
        except Exception:
            return 1.0

    def _side_from_bias(
        self,
        bias: str,
    ) -> str:
        value = str(bias or "").upper()

        if value in {"SHORT", "SELL", "BEARISH"}:
            return "SELL"

        if value in {"LONG", "BUY", "BULLISH"}:
            return "BUY"

        return "HOLD"

    def _risk_prices(
        self,
        *,
        side: str,
        price: float,
        stop_pct: float,
        target_pct: float,
    ) -> tuple[float, float]:
        if price <= 0:
            return 0.0, 0.0

        if side == "BUY":
            return (
                price * (1.0 - stop_pct),
                price * (1.0 + target_pct),
            )

        if side == "SELL":
            return (
                price * (1.0 + stop_pct),
                price * (1.0 - target_pct),
            )

        return (0.0, 0.0)

    def _suggested_units(
        self,
        *,
        target_weight: float,
        account_equity: float,
        price: float,
        leverage: float,
    ) -> float:
        if price <= 0 or account_equity <= 0:
            return 0.0

        notional = (
            account_equity
            * (target_weight / 100.0)
            * max(leverage, 1.0)
        )

        return max(
            0.0,
            notional / price,
        )

    def _decision_action(
        self,
        *,
        alpha_signal: str,
        strategy_signal: str,
        optimizer_weight: float,
        risk_score: float,
        min_weight: float,
    ) -> str:
        if risk_score >= 70:
            return "REJECT"

        if optimizer_weight < min_weight:
            return "HOLD"

        if alpha_signal in {"ALPHA_LONG", "LONG_WATCH"} and strategy_signal in {
            "DEPLOY_LONG_STRATEGY",
            "LONG_STRATEGY_WATCH",
        }:
            return "BUY"

        if alpha_signal in {"ALPHA_SHORT", "SHORT_WATCH"} and strategy_signal in {
            "DEPLOY_SHORT_STRATEGY",
            "SHORT_STRATEGY_WATCH",
        }:
            return "SELL"

        if alpha_signal in {"ALPHA_MONITOR"}:
            return "HOLD"

        return "HOLD"

    def _warnings(
        self,
        *,
        risk_score: float,
        optimizer_weight: float,
        confidence_score: float,
        auto_execute: bool,
    ) -> str:
        warnings: List[str] = []

        if risk_score >= 70:
            warnings.append(
                "Risk score exceeded autonomous trading threshold."
            )

        if optimizer_weight <= 0:
            warnings.append(
                "Optimizer did not assign target weight."
            )

        if confidence_score < 65:
            warnings.append(
                "Confidence below preferred execution threshold."
            )

        if not auto_execute:
            warnings.append(
                "Decision generated in review-only mode; no order submitted."
            )

        return " ".join(warnings)

    # =====================================================
    # Decision
    # =====================================================

    def evaluate_pair(
        self,
        pair: str,
        *,
        account_equity: float = 100000.0,
        leverage: float = 1.0,
        min_weight: float = 0.50,
        stop_pct: float = 0.005,
        target_pct: float = 0.010,
        auto_execute: bool = False,
        broker: str = "paper",
        save: bool = True,
    ) -> ForexAutonomousDecision:
        alpha = self.alpha_model.analyze_pair(
            pair,
            save=False,
        )

        strategy = self.strategy_lab.analyze_strategy(
            pair,
            save=False,
        )

        optimizer_run = self.optimizer.optimize_portfolio(
            pairs=[pair],
            save=False,
        )

        allocation = (
            optimizer_run.allocations[0]
            if optimizer_run.allocations
            else {}
        )

        if not isinstance(allocation, dict):
            allocation = allocation.to_dict()

        alpha_score = self._safe_float(
            getattr(alpha, "alpha_score", None),
            0.0,
        )

        alpha_signal = str(
            getattr(alpha, "alpha_signal", "")
        ).upper()

        position_bias = str(
            getattr(alpha, "position_bias", "FLAT")
        ).upper()

        strategy_score = self._safe_float(
            getattr(strategy, "risk_adjusted_score", None),
            0.0,
        )

        strategy_signal = str(
            getattr(strategy, "strategy_signal", "")
        ).upper()

        optimizer_weight = self._safe_float(
            allocation.get("optimized_weight"),
            0.0,
        )

        confidence_score = self._safe_float(
            getattr(alpha, "confidence_score", None),
            0.0,
        )

        risk_score = self._clip(
            self._safe_float(
                getattr(strategy, "risk_score", None),
                50.0,
            )
        )

        action = self._decision_action(
            alpha_signal=alpha_signal,
            strategy_signal=strategy_signal,
            optimizer_weight=optimizer_weight,
            risk_score=risk_score,
            min_weight=min_weight,
        )

        side = self._side_from_bias(
            position_bias
            if action not in {"BUY", "SELL"}
            else action,
        )

        if action in {"HOLD", "REJECT"}:
            side = "HOLD"

        price = self._quote_price(
            pair,
        )

        stop_price, target_price = self._risk_prices(
            side=side,
            price=price,
            stop_pct=stop_pct,
            target_pct=target_pct,
        )

        units = (
            self._suggested_units(
                target_weight=optimizer_weight,
                account_equity=account_equity,
                price=price,
                leverage=leverage,
            )
            if action in {"BUY", "SELL"}
            else 0.0
        )

        execution_status = "NOT_SUBMITTED"

        if auto_execute and action in {"BUY", "SELL"} and units > 0:
            try:
                if hasattr(
                    self.trading_engine,
                    "submit_order",
                ):
                    response = self.trading_engine.submit_order(
                        pair=pair,
                        side=side.lower(),
                        qty=units,
                        order_type="market",
                        broker=broker,
                    )
                elif hasattr(
                    self.trading_engine,
                    "place_order",
                ):
                    response = self.trading_engine.place_order(
                        pair=pair,
                        side=side.lower(),
                        units=units,
                        order_type="market",
                        broker=broker,
                    )
                else:
                    response = None

                execution_status = (
                    "SUBMITTED"
                    if response is not None
                    else "ENGINE_UNAVAILABLE"
                )

            except Exception as exc:
                execution_status = (
                    f"FAILED: {exc}"
                )

        decision_status = (
            "APPROVED"
            if action in {"BUY", "SELL"}
            else action
        )

        warnings = self._warnings(
            risk_score=risk_score,
            optimizer_weight=optimizer_weight,
            confidence_score=confidence_score,
            auto_execute=auto_execute,
        )

        rationale = (
            f"Autonomous decision {action} for {pair}: "
            f"alpha {round(alpha_score, 2)}, strategy {round(strategy_score, 2)}, "
            f"optimizer weight {round(optimizer_weight, 4)}%, "
            f"confidence {round(confidence_score, 2)}, "
            f"risk {round(risk_score, 2)}."
        )

        decision = ForexAutonomousDecision(
            decision_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair=pair,

            alpha_score=round(alpha_score, 2),
            strategy_score=round(strategy_score, 2),
            optimizer_weight=round(optimizer_weight, 4),
            confidence_score=round(confidence_score, 2),
            risk_score=round(risk_score, 2),

            action=action,
            side=side,
            order_type="market",
            suggested_units=round(units, 4),
            target_weight=round(optimizer_weight, 4),

            entry_price=round(price, 6),
            stop_price=round(stop_price, 6),
            target_price=round(target_price, 6),

            decision_status=decision_status,
            execution_status=execution_status,

            rationale=rationale,
            warnings=warnings,

            created_at=datetime.now(timezone.utc),
        )

        if save:
            self.save_decision(decision)

        return decision

    # =====================================================
    # Run
    # =====================================================

    def run_autonomous_cycle(
        self,
        pairs: Optional[List[str]] = None,
        *,
        account_equity: float = 100000.0,
        leverage: float = 1.0,
        min_weight: float = 0.50,
        stop_pct: float = 0.005,
        target_pct: float = 0.010,
        auto_execute: bool = False,
        broker: str = "paper",
        save: bool = True,
    ) -> ForexAutonomousRun:
        pairs = pairs or DEFAULT_PAIRS

        decisions: List[ForexAutonomousDecision] = []

        for pair in pairs:
            try:
                decisions.append(
                    self.evaluate_pair(
                        pair,
                        account_equity=account_equity,
                        leverage=leverage,
                        min_weight=min_weight,
                        stop_pct=stop_pct,
                        target_pct=target_pct,
                        auto_execute=auto_execute,
                        broker=broker,
                        save=save,
                    )
                )
            except Exception:
                continue

        buy_count = len(
            [
                item
                for item in decisions
                if item.action == "BUY"
            ]
        )

        sell_count = len(
            [
                item
                for item in decisions
                if item.action == "SELL"
            ]
        )

        hold_count = len(
            [
                item
                for item in decisions
                if item.action == "HOLD"
            ]
        )

        rejected_count = len(
            [
                item
                for item in decisions
                if item.action == "REJECT"
            ]
        )

        executed_count = len(
            [
                item
                for item in decisions
                if item.execution_status
                == "SUBMITTED"
            ]
        )

        status = (
            "EXECUTED"
            if executed_count > 0
            else "REVIEW_ONLY"
            if not auto_execute
            else "NO_EXECUTIONS"
        )

        run = ForexAutonomousRun(
            run_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair_count=len(decisions),

            buy_count=buy_count,
            sell_count=sell_count,
            hold_count=hold_count,
            rejected_count=rejected_count,
            executed_count=executed_count,

            mode=(
                "AUTO_EXECUTE"
                if auto_execute
                else "REVIEW_ONLY"
            ),

            status=status,

            decisions=[
                item.to_dict()
                for item in decisions
            ],

            created_at=datetime.now(timezone.utc),
        )

        if save:
            self.save_run(run)

        return run

    # =====================================================
    # Persistence
    # =====================================================

    def save_decision(
        self,
        decision: ForexAutonomousDecision,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO forex_autonomous_decisions (
                decision_id,

                tenant_id,
                user_id,
                portfolio_id,

                pair,

                alpha_score,
                strategy_score,
                optimizer_weight,
                confidence_score,
                risk_score,

                action,
                side,
                order_type,
                suggested_units,
                target_weight,

                entry_price,
                stop_price,
                target_price,

                decision_status,
                execution_status,

                rationale,
                warnings,

                created_at
            )
            VALUES (
                :decision_id,

                :tenant_id,
                :user_id,
                :portfolio_id,

                :pair,

                :alpha_score,
                :strategy_score,
                :optimizer_weight,
                :confidence_score,
                :risk_score,

                :action,
                :side,
                :order_type,
                :suggested_units,
                :target_weight,

                :entry_price,
                :stop_price,
                :target_price,

                :decision_status,
                :execution_status,

                :rationale,
                :warnings,

                :created_at
            )
            """,
            decision.to_dict(),
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def save_run(
        self,
        run: ForexAutonomousRun,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        payload = run.to_dict()

        self.db.execute(
            """
            INSERT INTO forex_autonomous_runs (
                run_id,

                tenant_id,
                user_id,
                portfolio_id,

                pair_count,

                buy_count,
                sell_count,
                hold_count,
                rejected_count,
                executed_count,

                mode,
                status,

                payload,

                created_at
            )
            VALUES (
                :run_id,

                :tenant_id,
                :user_id,
                :portfolio_id,

                :pair_count,

                :buy_count,
                :sell_count,
                :hold_count,
                :rejected_count,
                :executed_count,

                :mode,
                :status,

                :payload,

                :created_at
            )
            """,
            {
                **payload,
                "payload": payload,
            },
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    # =====================================================
    # History
    # =====================================================

    def load_decisions(
        self,
        *,
        pair: Optional[str] = None,
        action: str = "ALL",
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        self.ensure_tables()

        sql = """
        SELECT *
        FROM forex_autonomous_decisions
        WHERE tenant_id = :tenant_id
        """

        params: Dict[str, Any] = {
            "tenant_id": self.tenant_id,
        }

        if pair:
            sql += """
            AND pair = :pair
            """
            params["pair"] = pair

        if action and action.upper() != "ALL":
            sql += """
            AND action = :action
            """
            params["action"] = action.upper()

        sql += """
        ORDER BY created_at DESC
        LIMIT :limit
        """

        params["limit"] = int(limit)

        rows = (
            self.db.execute(
                sql,
                params,
            )
            .mappings()
            .all()
        )

        return [
            dict(row)
            for row in rows
        ]

    def load_runs(
        self,
        *,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        self.ensure_tables()

        rows = (
            self.db.execute(
                """
                SELECT *
                FROM forex_autonomous_runs
                WHERE tenant_id = :tenant_id
                ORDER BY created_at DESC
                LIMIT :limit
                """,
                {
                    "tenant_id": self.tenant_id,
                    "limit": int(limit),
                },
            )
            .mappings()
            .all()
        )

        return [
            dict(row)
            for row in rows
        ]


def get_forex_autonomous_trader(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> ForexAutonomousTrader:
    return ForexAutonomousTrader(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )