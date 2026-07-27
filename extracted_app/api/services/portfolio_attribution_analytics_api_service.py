from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from models.trading import Portfolio
from modules.trading_intelligence.trade_attribution_engine import (
    TradeAttributionEngine,
)

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class PortfolioAttributionAnalyticsAPIService:
    """
    Portfolio Attribution Analytics API Service

    This service builds analytics on top of the raw attribution
    information returned by TradeAttributionEngine.

    Responsibilities
    ----------------
    • Validate portfolio ownership
    • Execute TradeAttributionEngine
    • Produce executive analytics
    • Return JSON-safe dictionaries

    NOTE:
    The attribution engine remains the single source of truth.
    No SQL should be duplicated here.
    """

    def __init__(
        self,
        db: Session,
    ):

        self.db = db

    # ==========================================================
    # PUBLIC ENTRY POINT
    # ==========================================================

    def get_analytics(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:

        # This service's db session is cached and reused across every
        # request to this endpoint for the life of the process (see
        # ModuleRegistry._load). If an earlier request left it in a
        # failed-transaction state (Postgres) and didn't roll back,
        # every query below -- including this very first one -- would
        # otherwise fail immediately. Rolling back a clean session is a
        # harmless no-op.
        _safe_rollback(self.db)

        portfolio = self._validate_portfolio(

            tenant_id=tenant_id,

            portfolio_id=portfolio_id,

        )

        if portfolio is None:
            return None

        engine = TradeAttributionEngine(
            self.db,
        )

        logger.info(
            "Building attribution analytics "
            "for portfolio %s",
            portfolio_id,
        )

        try:

            summary = engine.build_summary(
                portfolio_id,
            )

            linkage = engine.load_attribution_table(
                portfolio_id,
            )

            signal = engine.signal_attribution(
                portfolio_id,
            )

            sector = engine.sector_attribution(
                portfolio_id,
            )

            conviction = (
                engine.conviction_band_attribution(
                    portfolio_id,
                )
            )

            exposure = (
                engine.open_recommendation_exposure(
                    portfolio_id,
                )
            )

            linkage_df = self._to_dataframe(
                linkage,
            )

            signal_df = self._to_dataframe(
                signal,
            )

            sector_df = self._to_dataframe(
                sector,
            )

            conviction_df = self._to_dataframe(
                conviction,
            )

            exposure_df = self._to_dataframe(
                exposure,
            )

            return {

                "summary": self._normalize_value(
                    summary,
                ),

                "performance": self._performance_metrics(
                    linkage_df,
                ),

                #
                # Part 2
                #
                "signal_performance": [],

                "sector_performance": [],

                "conviction_performance": [],

                #
                # Part 3
                #
                "holding_periods":
                    self._holding_period_analytics(
                        linkage_df,
                    ),

                "monthly":
                    self._monthly_attribution(
                        linkage_df,
                    ),

                "daily":
                    self._daily_attribution(
                        linkage_df,
                    ),

                "best_trades":
                    self._best_trades(
                        linkage_df,
                        limit=10,
                    ),

                "worst_trades":
                    self._worst_trades(
                        linkage_df,
                        limit=10,
                    ),

                #
                # Part 4
                #
                "best_trades": [],

                "worst_trades": [],

                #
                # Part 5
                #
                "execution_quality":
                    self._execution_quality(
                        linkage_df,
                    ),

                "recommendation_conversion":
                    self._recommendation_conversion(
                        linkage_df,
                        exposure_df,
                    ),

                #
                # Raw tables
                #
                "raw": {

                    "trade_linkage":
                        self._normalize_dataframe(
                            linkage_df,
                        ),

                    "signals":
                        self._normalize_dataframe(
                            signal_df,
                        ),

                    "sectors":
                        self._normalize_dataframe(
                            sector_df,
                        ),

                    "conviction":
                        self._normalize_dataframe(
                            conviction_df,
                        ),

                    "exposure":
                        self._normalize_dataframe(
                            exposure_df,
                        ),

                },

            }

        except Exception:

            logger.exception(
                "Failed building attribution analytics."
            )

            _safe_rollback(self.db)

            raise

    # ==========================================================
    # VALIDATION
    # ==========================================================

    def _validate_portfolio(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ):

        return (

            self.db.query(
                Portfolio,
            )

            .filter(

                Portfolio.id == portfolio_id,

                Portfolio.tenant_id == tenant_id,

            )

            .one_or_none()

        )

    # ==========================================================
    # DATAFRAME HELPERS
    # ==========================================================

    def _to_dataframe(
        self,
        value,
    ) -> pd.DataFrame:

        if value is None:

            return pd.DataFrame()

        if isinstance(
            value,
            pd.DataFrame,
        ):

            return value.copy()

        if isinstance(
            value,
            list,
        ):

            return pd.DataFrame(
                value,
            )

        if isinstance(
            value,
            dict,
        ):

            return pd.DataFrame(
                [value],
            )

        return pd.DataFrame()

    # ==========================================================
    # PART 2 STARTS HERE
    # ==========================================================

    # ==========================================================
    # PERFORMANCE METRICS
    # ==========================================================

    def _performance_metrics(
            self,
            linkage: pd.DataFrame,
    ) -> dict[str, Any]:

        if linkage.empty:
            return {

                "total_trades": 0,

                "closed_trades": 0,

                "open_trades": 0,

                "winning_trades": 0,

                "losing_trades": 0,

                "breakeven_trades": 0,

                "win_rate": 0.0,

                "loss_rate": 0.0,

                "average_winner": 0.0,

                "average_loser": 0.0,

                "largest_winner": 0.0,

                "largest_loser": 0.0,

                "total_net_pnl": 0.0,

                "average_net_pnl": 0.0,

                "profit_factor": 0.0,

                "expectancy": 0.0,

                "average_return_pct": 0.0,

                "average_holding_period_days": 0.0,

            }

        df = linkage.copy()

        # --------------------------------------------------
        # Numeric columns
        # --------------------------------------------------

        numeric_columns = [

            "net_pnl",

            "gross_pnl",

            "return_pct",

            "holding_period_days",

        ]

        for column in numeric_columns:

            if column in df.columns:
                df[column] = pd.to_numeric(

                    df[column],

                    errors="coerce",

                )

        # --------------------------------------------------
        # Closed trades
        # --------------------------------------------------

        if "closed_at" in df.columns:

            closed = df[
                df["closed_at"].notna()
            ].copy()

        elif "outcome" in df.columns:

            closed = df[
                df["outcome"] != "OPEN"
                ].copy()

        else:

            closed = df.copy()

        open_positions = len(df) - len(closed)

        # --------------------------------------------------
        # Winners / Losers
        # --------------------------------------------------

        if "net_pnl" in closed.columns:

            winners = closed[
                closed["net_pnl"] > 0
                ]

            losers = closed[
                closed["net_pnl"] < 0
                ]

            breakeven = closed[
                closed["net_pnl"] == 0
                ]

        else:

            winners = pd.DataFrame()

            losers = pd.DataFrame()

            breakeven = pd.DataFrame()

        closed_count = len(closed)

        winner_count = len(winners)

        loser_count = len(losers)

        breakeven_count = len(breakeven)

        # --------------------------------------------------
        # Win/Loss rates
        # --------------------------------------------------

        if closed_count:

            win_rate = (

                               winner_count /

                               closed_count

                       ) * 100

            loss_rate = (

                                loser_count /

                                closed_count

                        ) * 100

        else:

            win_rate = 0.0

            loss_rate = 0.0

        # --------------------------------------------------
        # Average winners
        # --------------------------------------------------

        if winner_count:

            average_winner = float(

                winners["net_pnl"].mean()

            )

            largest_winner = float(

                winners["net_pnl"].max()

            )

        else:

            average_winner = 0.0

            largest_winner = 0.0

        # --------------------------------------------------
        # Average losers
        # --------------------------------------------------

        if loser_count:

            average_loser = float(

                losers["net_pnl"].mean()

            )

            largest_loser = float(

                losers["net_pnl"].min()

            )

        else:

            average_loser = 0.0

            largest_loser = 0.0

        # --------------------------------------------------
        # Total PnL
        # --------------------------------------------------

        if "net_pnl" in closed.columns:

            total_net = float(

                closed["net_pnl"]

                .fillna(0)

                .sum()

            )

            average_net = float(

                closed["net_pnl"]

                .fillna(0)

                .mean()

            )

        else:

            total_net = 0.0

            average_net = 0.0

        # --------------------------------------------------
        # Profit factor
        # --------------------------------------------------

        gross_profit = float(

            winners["net_pnl"]

            .sum()

        ) if winner_count else 0.0

        gross_loss = abs(float(

            losers["net_pnl"]

            .sum()

        )) if loser_count else 0.0

        if gross_loss > 0:

            profit_factor = (

                    gross_profit /

                    gross_loss

            )

        elif gross_profit > 0:

            profit_factor = gross_profit

        else:

            profit_factor = 0.0

        # --------------------------------------------------
        # Expectancy
        # --------------------------------------------------

        expectancy = average_net

        # --------------------------------------------------
        # Average Return
        # --------------------------------------------------

        if (

                "return_pct" in closed.columns

                and

                not closed["return_pct"].dropna().empty

        ):

            average_return = float(

                closed["return_pct"]

                .mean()

            )

        else:

            average_return = 0.0

        # --------------------------------------------------
        # Holding Period
        # --------------------------------------------------

        if (

                "holding_period_days"

                in closed.columns

                and

                not closed["holding_period_days"]

                        .dropna()

                        .empty

        ):

            average_holding = float(

                closed["holding_period_days"]

                .mean()

            )

        else:

            average_holding = 0.0

        # --------------------------------------------------
        # Result
        # --------------------------------------------------

        return {

            "total_trades": int(

                len(df)

            ),

            "closed_trades": int(

                closed_count

            ),

            "open_trades": int(

                open_positions

            ),

            "winning_trades": int(

                winner_count

            ),

            "losing_trades": int(

                loser_count

            ),

            "breakeven_trades": int(

                breakeven_count

            ),

            "win_rate": round(

                win_rate,

                2,

            ),

            "loss_rate": round(

                loss_rate,

                2,

            ),

            "average_winner": round(

                average_winner,

                2,

            ),

            "average_loser": round(

                average_loser,

                2,

            ),

            "largest_winner": round(

                largest_winner,

                2,

            ),

            "largest_loser": round(

                largest_loser,

                2,

            ),

            "total_net_pnl": round(

                total_net,

                2,

            ),

            "average_net_pnl": round(

                average_net,

                2,

            ),

            "profit_factor": round(

                profit_factor,

                2,

            ),

            "expectancy": round(

                expectancy,

                2,

            ),

            "average_return_pct": round(

                average_return,

                2,

            ),

            "average_holding_period_days": round(

                average_holding,

                2,

            ),

        }

    # ==========================================================
    # SIGNAL PERFORMANCE
    # ==========================================================

    def _signal_performance(
            self,
            linkage: pd.DataFrame,
    ) -> list[dict[str, Any]]:

        if linkage.empty:
            return []

        df = linkage.copy()

        if "signal" not in df.columns:
            return []

        if "net_pnl" in df.columns:
            df["net_pnl"] = pd.to_numeric(
                df["net_pnl"],
                errors="coerce",
            ).fillna(0)

        if "return_pct" in df.columns:
            df["return_pct"] = pd.to_numeric(
                df["return_pct"],
                errors="coerce",
            )

        rows = []

        for signal, group in df.groupby("signal"):
            closed = group[
                group["closed_at"].notna()
            ] if "closed_at" in group.columns else group

            wins = closed[
                closed["net_pnl"] > 0
                ] if "net_pnl" in closed.columns else pd.DataFrame()

            losses = closed[
                closed["net_pnl"] < 0
                ] if "net_pnl" in closed.columns else pd.DataFrame()

            trade_count = len(closed)

            win_rate = (
                (len(wins) / trade_count) * 100
                if trade_count
                else 0.0
            )

            rows.append({

                "signal": signal,

                "trades": trade_count,

                "winning_trades": len(wins),

                "losing_trades": len(losses),

                "win_rate": round(
                    win_rate,
                    2,
                ),

                "average_return_pct": round(

                    float(
                        closed["return_pct"].mean()
                    ) if (
                            trade_count
                            and
                            "return_pct" in closed.columns
                    ) else 0,

                    2,

                ),

                "average_net_pnl": round(

                    float(
                        closed["net_pnl"].mean()
                    ) if (
                            trade_count
                            and
                            "net_pnl" in closed.columns
                    ) else 0,

                    2,

                ),

                "total_net_pnl": round(

                    float(
                        closed["net_pnl"].sum()
                    ) if (
                            trade_count
                            and
                            "net_pnl" in closed.columns
                    ) else 0,

                    2,

                ),

            })

        rows.sort(
            key=lambda x: x["total_net_pnl"],
            reverse=True,
        )

        return rows

    # ==========================================================
    # SECTOR PERFORMANCE
    # ==========================================================

    def _sector_performance(
            self,
            linkage: pd.DataFrame,
    ) -> list[dict[str, Any]]:

        if linkage.empty:
            return []

        if "sector" not in linkage.columns:
            return []

        df = linkage.copy()

        df["net_pnl"] = pd.to_numeric(
            df.get("net_pnl"),
            errors="coerce",
        ).fillna(0)

        if "return_pct" in df.columns:
            df["return_pct"] = pd.to_numeric(
                df["return_pct"],
                errors="coerce",
            )

        rows = []

        for sector, group in df.groupby("sector"):
            closed = group[
                group["closed_at"].notna()
            ] if "closed_at" in group.columns else group

            winners = closed[
                closed["net_pnl"] > 0
                ]

            trade_count = len(closed)

            rows.append({

                "sector": sector,

                "trades": trade_count,

                "win_rate": round(

                    (
                            len(winners)
                            /
                            trade_count
                            *
                            100
                    )

                    if trade_count

                    else 0,

                    2,

                ),

                "average_return_pct": round(

                    float(
                        closed["return_pct"].mean()
                    )

                    if (
                            trade_count
                            and
                            "return_pct"
                            in closed.columns
                    )

                    else 0,

                    2,

                ),

                "total_net_pnl": round(

                    float(
                        closed["net_pnl"].sum()
                    ),

                    2,

                ),

            })

        rows.sort(
            key=lambda x: x["total_net_pnl"],
            reverse=True,
        )

        return rows

    # ==========================================================
    # CONVICTION PERFORMANCE
    # ==========================================================

    def _conviction_performance(
            self,
            linkage: pd.DataFrame,
    ) -> list[dict[str, Any]]:

        if linkage.empty:
            return []

        if "conviction_score" not in linkage.columns:
            return []

        df = linkage.copy()

        df["conviction_score"] = pd.to_numeric(
            df["conviction_score"],
            errors="coerce",
        )

        df["net_pnl"] = pd.to_numeric(
            df.get("net_pnl"),
            errors="coerce",
        ).fillna(0)

        if "return_pct" in df.columns:
            df["return_pct"] = pd.to_numeric(
                df["return_pct"],
                errors="coerce",
            )

        buckets = [

            (70, 75),

            (75, 80),

            (80, 85),

            (85, 90),

            (90, 101),

        ]

        results = []

        for low, high in buckets:
            group = df[

                (df["conviction_score"] >= low)

                &

                (df["conviction_score"] < high)

                ]

            closed = group[
                group["closed_at"].notna()
            ] if "closed_at" in group.columns else group

            winners = closed[
                closed["net_pnl"] > 0
                ]

            trade_count = len(closed)

            results.append({

                "band": f"{low}-{high - 1}",

                "trades": trade_count,

                "win_rate": round(

                    (
                            len(winners)
                            /
                            trade_count
                            *
                            100
                    )

                    if trade_count

                    else 0,

                    2,

                ),

                "average_return_pct": round(

                    float(
                        closed["return_pct"].mean()
                    )

                    if (
                            trade_count
                            and
                            "return_pct"
                            in closed.columns
                    )

                    else 0,

                    2,

                ),

                "average_net_pnl": round(

                    float(
                        closed["net_pnl"].mean()
                    )

                    if trade_count

                    else 0,

                    2,

                ),

                "total_net_pnl": round(

                    float(
                        closed["net_pnl"].sum()
                    )

                    if trade_count

                    else 0,

                    2,

                ),

            })

        return results

    # ==========================================================
    # HOLDING PERIOD ANALYTICS
    # ==========================================================

    def _holding_period_analytics(
            self,
            linkage: pd.DataFrame,
    ) -> list[dict[str, Any]]:

        if linkage.empty:
            return []

        df = linkage.copy()

        if "holding_period_days" not in df.columns:
            df = self._derive_holding_period_days(
                df,
            )

        if "holding_period_days" not in df.columns:
            return []

        df["holding_period_days"] = pd.to_numeric(
            df["holding_period_days"],
            errors="coerce",
        )

        if "net_pnl" in df.columns:

            df["net_pnl"] = pd.to_numeric(
                df["net_pnl"],
                errors="coerce",
            ).fillna(0.0)

        else:

            df["net_pnl"] = 0.0

        if "return_pct" in df.columns:

            df["return_pct"] = pd.to_numeric(
                df["return_pct"],
                errors="coerce",
            )

        else:

            df["return_pct"] = np.nan

        closed = self._closed_trades(
            df,
        )

        closed = closed[
            closed["holding_period_days"].notna()
        ].copy()

        if closed.empty:
            return []

        bins = [
            -0.001,
            1,
            3,
            7,
            14,
            30,
            90,
            float("inf"),
        ]

        labels = [
            "Same Day",
            "1-3 Days",
            "4-7 Days",
            "8-14 Days",
            "15-30 Days",
            "31-90 Days",
            "90+ Days",
        ]

        closed["holding_period_band"] = pd.cut(
            closed["holding_period_days"],
            bins=bins,
            labels=labels,
            include_lowest=True,
            right=True,
        )

        results: list[dict[str, Any]] = []

        for label in labels:

            group = closed[
                closed["holding_period_band"] == label
                ]

            if group.empty:
                continue

            winners = group[
                group["net_pnl"] > 0
                ]

            losers = group[
                group["net_pnl"] < 0
                ]

            trade_count = len(group)

            total_net_pnl = float(
                group["net_pnl"].sum()
            )

            average_net_pnl = float(
                group["net_pnl"].mean()
            )

            average_return_pct = self._safe_mean(
                group["return_pct"],
            )

            average_holding_days = self._safe_mean(
                group["holding_period_days"],
            )

            win_rate = (
                len(winners)
                / trade_count
                * 100
                if trade_count
                else 0.0
            )

            results.append(
                {
                    "holding_period_band": label,
                    "trades": int(trade_count),
                    "winning_trades": int(
                        len(winners)
                    ),
                    "losing_trades": int(
                        len(losers)
                    ),
                    "win_rate": round(
                        win_rate,
                        2,
                    ),
                    "average_holding_period_days": round(
                        average_holding_days,
                        2,
                    ),
                    "average_return_pct": round(
                        average_return_pct,
                        2,
                    ),
                    "average_net_pnl": round(
                        average_net_pnl,
                        2,
                    ),
                    "total_net_pnl": round(
                        total_net_pnl,
                        2,
                    ),
                }
            )

        return results

    # ==========================================================
    # MONTHLY ATTRIBUTION
    # ==========================================================

    def _monthly_attribution(
            self,
            linkage: pd.DataFrame,
    ) -> list[dict[str, Any]]:

        if linkage.empty:
            return []

        df = linkage.copy()

        date_column = self._resolve_date_column(
            df,
            preferred_columns=[
                "closed_at",
                "exit_at",
                "executed_at",
                "filled_at",
                "created_at",
            ],
        )

        if date_column is None:
            return []

        df[date_column] = pd.to_datetime(
            df[date_column],
            errors="coerce",
            utc=True,
        )

        df = df[
            df[date_column].notna()
        ].copy()

        if df.empty:
            return []

        df = self._closed_trades(
            df,
        )

        if df.empty:
            return []

        df["net_pnl"] = pd.to_numeric(
            df.get(
                "net_pnl",
                0.0,
            ),
            errors="coerce",
        ).fillna(0.0)

        if "return_pct" in df.columns:

            df["return_pct"] = pd.to_numeric(
                df["return_pct"],
                errors="coerce",
            )

        else:

            df["return_pct"] = np.nan

        df["month"] = (
            df[date_column]
            .dt.tz_convert(None)
            .dt.to_period("M")
            .astype(str)
        )

        results: list[dict[str, Any]] = []

        for month, group in df.groupby(
                "month",
                sort=True,
        ):
            winners = group[
                group["net_pnl"] > 0
                ]

            losers = group[
                group["net_pnl"] < 0
                ]

            breakeven = group[
                group["net_pnl"] == 0
                ]

            trade_count = len(group)

            gross_profit = float(
                winners["net_pnl"].sum()
            ) if not winners.empty else 0.0

            gross_loss = abs(
                float(
                    losers["net_pnl"].sum()
                )
            ) if not losers.empty else 0.0

            profit_factor = self._profit_factor(
                gross_profit=gross_profit,
                gross_loss=gross_loss,
            )

            results.append(
                {
                    "month": month,
                    "trades": int(
                        trade_count
                    ),
                    "winning_trades": int(
                        len(winners)
                    ),
                    "losing_trades": int(
                        len(losers)
                    ),
                    "breakeven_trades": int(
                        len(breakeven)
                    ),
                    "win_rate": round(
                        (
                                len(winners)
                                / trade_count
                                * 100
                        )
                        if trade_count
                        else 0.0,
                        2,
                    ),
                    "gross_profit": round(
                        gross_profit,
                        2,
                    ),
                    "gross_loss": round(
                        gross_loss,
                        2,
                    ),
                    "profit_factor": round(
                        profit_factor,
                        2,
                    ),
                    "average_return_pct": round(
                        self._safe_mean(
                            group["return_pct"],
                        ),
                        2,
                    ),
                    "average_net_pnl": round(
                        float(
                            group["net_pnl"].mean()
                        ),
                        2,
                    ),
                    "total_net_pnl": round(
                        float(
                            group["net_pnl"].sum()
                        ),
                        2,
                    ),
                }
            )

        return results

    # ==========================================================
    # DAILY ATTRIBUTION
    # ==========================================================

    def _daily_attribution(
            self,
            linkage: pd.DataFrame,
    ) -> list[dict[str, Any]]:

        if linkage.empty:
            return []

        df = linkage.copy()

        date_column = self._resolve_date_column(
            df,
            preferred_columns=[
                "closed_at",
                "exit_at",
                "executed_at",
                "filled_at",
                "created_at",
            ],
        )

        if date_column is None:
            return []

        df[date_column] = pd.to_datetime(
            df[date_column],
            errors="coerce",
            utc=True,
        )

        df = df[
            df[date_column].notna()
        ].copy()

        if df.empty:
            return []

        df = self._closed_trades(
            df,
        )

        if df.empty:
            return []

        df["net_pnl"] = pd.to_numeric(
            df.get(
                "net_pnl",
                0.0,
            ),
            errors="coerce",
        ).fillna(0.0)

        if "return_pct" in df.columns:

            df["return_pct"] = pd.to_numeric(
                df["return_pct"],
                errors="coerce",
            )

        else:

            df["return_pct"] = np.nan

        df["trade_date"] = (
            df[date_column]
            .dt.tz_convert(None)
            .dt.date
        )

        results: list[dict[str, Any]] = []

        for trade_date, group in df.groupby(
                "trade_date",
                sort=True,
        ):
            winners = group[
                group["net_pnl"] > 0
                ]

            losers = group[
                group["net_pnl"] < 0
                ]

            trade_count = len(group)

            results.append(
                {
                    "date": trade_date.isoformat(),
                    "trades": int(
                        trade_count
                    ),
                    "winning_trades": int(
                        len(winners)
                    ),
                    "losing_trades": int(
                        len(losers)
                    ),
                    "win_rate": round(
                        (
                                len(winners)
                                / trade_count
                                * 100
                        )
                        if trade_count
                        else 0.0,
                        2,
                    ),
                    "average_return_pct": round(
                        self._safe_mean(
                            group["return_pct"],
                        ),
                        2,
                    ),
                    "average_net_pnl": round(
                        float(
                            group["net_pnl"].mean()
                        ),
                        2,
                    ),
                    "total_net_pnl": round(
                        float(
                            group["net_pnl"].sum()
                        ),
                        2,
                    ),
                }
            )

        return results

    # ==========================================================
    # BEST TRADES
    # ==========================================================

    def _best_trades(
            self,
            linkage: pd.DataFrame,
            *,
            limit: int = 10,
    ) -> list[dict[str, Any]]:

        return self._ranked_trades(
            linkage,
            ascending=False,
            limit=limit,
        )

    # ==========================================================
    # WORST TRADES
    # ==========================================================

    def _worst_trades(
            self,
            linkage: pd.DataFrame,
            *,
            limit: int = 10,
    ) -> list[dict[str, Any]]:

        return self._ranked_trades(
            linkage,
            ascending=True,
            limit=limit,
        )

    # ==========================================================
    # TRADE RANKING
    # ==========================================================

    def _ranked_trades(
            self,
            linkage: pd.DataFrame,
            *,
            ascending: bool,
            limit: int,
    ) -> list[dict[str, Any]]:

        if linkage.empty:
            return []

        if "net_pnl" not in linkage.columns:
            return []

        df = linkage.copy()

        df["net_pnl"] = pd.to_numeric(
            df["net_pnl"],
            errors="coerce",
        )

        df = self._closed_trades(
            df,
        )

        df = df[
            df["net_pnl"].notna()
        ].copy()

        if df.empty:
            return []

        if "return_pct" in df.columns:
            df["return_pct"] = pd.to_numeric(
                df["return_pct"],
                errors="coerce",
            )

        if "holding_period_days" not in df.columns:
            df = self._derive_holding_period_days(
                df,
            )

        if "holding_period_days" in df.columns:
            df["holding_period_days"] = pd.to_numeric(
                df["holding_period_days"],
                errors="coerce",
            )

        ranked = (
            df.sort_values(
                by="net_pnl",
                ascending=ascending,
                na_position="last",
            )
            .head(
                max(
                    int(limit),
                    0,
                )
            )
        )

        preferred_columns = [
            "trade_id",
            "closed_trade_id",
            "recommendation_id",
            "order_id",
            "position_id",
            "symbol",
            "pair",
            "asset_type",
            "side",
            "recommendation",
            "signal",
            "sector",
            "conviction_score",
            "entry_price",
            "exit_price",
            "quantity",
            "units",
            "gross_pnl",
            "fees",
            "net_pnl",
            "return_pct",
            "holding_period_days",
            "opened_at",
            "entered_at",
            "closed_at",
            "exit_at",
        ]

        available_columns = [
            column
            for column in preferred_columns
            if column in ranked.columns
        ]

        if not available_columns:
            return []

        return self._normalize_dataframe(
            ranked[
                available_columns
            ]
        )

    # ==========================================================
    # CLOSED TRADE FILTER
    # ==========================================================

    def _closed_trades(
            self,
            dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        if dataframe.empty:
            return dataframe.copy()

        df = dataframe.copy()

        date_columns = [
            "closed_at",
            "exit_at",
        ]

        for column in date_columns:

            if column in df.columns:
                parsed = pd.to_datetime(
                    df[column],
                    errors="coerce",
                    utc=True,
                )

                return df[
                    parsed.notna()
                ].copy()

        status_columns = [
            "trade_status",
            "position_status",
            "status",
            "outcome",
        ]

        closed_values = {
            "CLOSED",
            "COMPLETE",
            "COMPLETED",
            "EXITED",
            "FILLED",
            "WIN",
            "LOSS",
            "BREAKEVEN",
        }

        for column in status_columns:

            if column not in df.columns:
                continue

            status = (
                df[column]
                .astype(str)
                .str.strip()
                .str.upper()
            )

            mask = status.isin(
                closed_values
            )

            if mask.any():
                return df[
                    mask
                ].copy()

        return df.copy()

    # ==========================================================
    # HOLDING PERIOD DERIVATION
    # ==========================================================

    def _derive_holding_period_days(
            self,
            dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        df = dataframe.copy()

        opened_column = self._resolve_date_column(
            df,
            preferred_columns=[
                "opened_at",
                "entered_at",
                "entry_at",
                "filled_at",
                "executed_at",
                "created_at",
            ],
        )

        closed_column = self._resolve_date_column(
            df,
            preferred_columns=[
                "closed_at",
                "exit_at",
            ],
        )

        if (
                opened_column is None
                or closed_column is None
        ):
            return df

        opened_at = pd.to_datetime(
            df[opened_column],
            errors="coerce",
            utc=True,
        )

        closed_at = pd.to_datetime(
            df[closed_column],
            errors="coerce",
            utc=True,
        )

        holding_period = (
                                 closed_at
                                 - opened_at
                         ).dt.total_seconds() / 86400.0

        df["holding_period_days"] = (
            holding_period
            .where(
                holding_period >= 0
            )
        )

        return df

    # ==========================================================
    # DATE COLUMN RESOLUTION
    # ==========================================================

    def _resolve_date_column(
            self,
            dataframe: pd.DataFrame,
            *,
            preferred_columns: list[str],
    ) -> str | None:

        for column in preferred_columns:

            if column not in dataframe.columns:
                continue

            parsed = pd.to_datetime(
                dataframe[column],
                errors="coerce",
                utc=True,
            )

            if parsed.notna().any():
                return column

        return None

    # ==========================================================
    # NUMERIC HELPERS
    # ==========================================================

    def _safe_mean(
            self,
            values: pd.Series,
    ) -> float:

        if values is None:
            return 0.0

        numeric = pd.to_numeric(
            values,
            errors="coerce",
        ).dropna()

        if numeric.empty:
            return 0.0

        result = float(
            numeric.mean()
        )

        if not np.isfinite(
                result
        ):
            return 0.0

        return result

    def _profit_factor(
            self,
            *,
            gross_profit: float,
            gross_loss: float,
    ) -> float:

        if gross_loss > 0:
            return (
                    gross_profit
                    / gross_loss
            )

        if gross_profit > 0:
            return gross_profit

        return 0.0

    # ==========================================================
    # EXECUTION QUALITY
    # ==========================================================

    def _execution_quality(
            self,
            linkage: pd.DataFrame,
    ) -> dict[str, Any]:

        if linkage.empty:
            return {

                "linked_recommendations": 0,

                "filled_orders": 0,

                "open_positions": 0,

                "closed_positions": 0,

                "fill_rate": 0.0,

                "close_rate": 0.0,

                "average_holding_period_days": 0.0,

            }

        df = linkage.copy()

        total = len(df)

        # --------------------------------------------------

        filled = total

        # --------------------------------------------------

        closed = len(
            self._closed_trades(df)
        )

        open_positions = max(
            total - closed,
            0,
        )

        fill_rate = (

            filled / total * 100

            if total

            else 0

        )

        close_rate = (

            closed / filled * 100

            if filled

            else 0

        )

        # --------------------------------------------------

        if "holding_period_days" not in df.columns:
            df = self._derive_holding_period_days(
                df,
            )

        average_holding = 0.0

        if "holding_period_days" in df.columns:
            average_holding = self._safe_mean(

                df["holding_period_days"]

            )

        return {

            "linked_recommendations": total,

            "filled_orders": filled,

            "open_positions": open_positions,

            "closed_positions": closed,

            "fill_rate": round(
                fill_rate,
                2,
            ),

            "close_rate": round(
                close_rate,
                2,
            ),

            "average_holding_period_days": round(
                average_holding,
                2,
            ),

        }

    # ==========================================================
    # RECOMMENDATION CONVERSION
    # ==========================================================

    def _recommendation_conversion(
            self,
            linkage: pd.DataFrame,
            exposure: pd.DataFrame,
    ) -> dict[str, Any]:

        # --------------------------------------------------
        # Count unique recommendations
        # --------------------------------------------------

        if "recommendation_id" in linkage.columns:

            recommendations = (

                linkage["recommendation_id"]

                .dropna()

                .nunique()

            )

        else:

            recommendations = len(linkage)

        linked = len(linkage)

        # --------------------------------------------------
        # Count recommendations that generated an order
        # --------------------------------------------------

        converted = 0

        if {

            "recommendation_id",

            "order_id",

        }.issubset(linkage.columns):
            # --------------------------------------------------
            # Count recommendations that actually converted
            # --------------------------------------------------

            converted_ids = set()

            #
            # Method 1
            # executed flag
            #

            if {
                "recommendation_id",
                "executed",
            }.issubset(linkage.columns):
                converted_ids.update(

                    linkage.loc[
                        linkage["executed"] == True,
                        "recommendation_id",
                    ]

                    .dropna()

                    .tolist()

                )

            #
            # Method 2
            # executed_order_id
            #

            if {
                "recommendation_id",
                "executed_order_id",
            }.issubset(linkage.columns):
                converted_ids.update(

                    linkage.loc[
                        linkage["executed_order_id"].notna(),
                        "recommendation_id",
                    ]

                    .dropna()

                    .tolist()

                )

            #
            # Method 3
            # order_id
            #

            if {
                "recommendation_id",
                "order_id",
            }.issubset(linkage.columns):
                converted_ids.update(

                    linkage.loc[
                        linkage["order_id"].notna(),
                        "recommendation_id",
                    ]

                    .dropna()

                    .tolist()

                )

            converted = len(converted_ids)

        open_recommendations = max(
            recommendations - converted,
            0,
        )

        if recommendations > 0:

            conversion_rate = (

                                      converted

                                      / recommendations

                              ) * 100

        else:

            conversion_rate = 0.0

        return {

            "recommendations": recommendations,

            "converted": converted,

            "open": open_recommendations,

            "conversion_rate": round(

                conversion_rate,

                2,

            ),

        }

    # ==========================================================
    # DATAFRAME NORMALIZATION
    # ==========================================================

    def _normalize_dataframe(
            self,
            dataframe: pd.DataFrame,
    ) -> list[dict[str, Any]]:

        if dataframe.empty:
            return []

        records = dataframe.to_dict(
            orient="records",
        )

        return [

            self._normalize_value(
                record,
            )

            for record in records

        ]

    # ==========================================================
    # JSON NORMALIZATION
    # ==========================================================

    def _normalize_value(
            self,
            value: Any,
    ) -> Any:

        if value is None:
            return None

        if isinstance(
                value,
                dict,
        ):
            return {

                str(k): self._normalize_value(v)

                for k, v in value.items()

            }

        if isinstance(
                value,
                list,
        ):
            return [

                self._normalize_value(v)

                for v in value

            ]

        if isinstance(
                value,
                tuple,
        ):
            return [

                self._normalize_value(v)

                for v in value

            ]

        if isinstance(
                value,
                pd.Timestamp,
        ):

            if pd.isna(value):
                return None

            return value.isoformat()

        if isinstance(
                value,
                datetime,
        ):
            return value.isoformat()

        if isinstance(
                value,
                np.integer,
        ):
            return int(value)

        if isinstance(
                value,
                np.floating,
        ):

            if np.isnan(value):
                return None

            return float(value)

        if isinstance(
                value,
                np.bool_,
        ):
            return bool(value)

        if isinstance(
                value,
                float,
        ):

            if np.isnan(value):
                return None

            return value

        if pd.isna(value):
            return None

        return value