"""
modules/forex/forex_strategy_backtester.py

Phase 14D - Strategy backtester.

Runs a real bar-by-bar simulation against live historical daily closes
(forex_history_service -> provider router), replacing the previous
implementation which derived trades/win_rate/profit_factor/max_drawdown/
sharpe entirely from hash(strategy_name) % 1000 -- numbers that varied by
strategy name but had no relationship to any real price data.

Methodology (documented here since it drives forex_walk_forward.py and
forex_monte_carlo.py too):
- Entry/exit rules are parsed from strategy["entry"] / strategy["exit"]
  (e.g. "composite_factor_score > 65" / "factor_score < 50 or stop"). The
  comparison operator determines direction: ">" => long bias, "<" => short
  bias (score below threshold treated as a bearish signal).
- The "factor score" evaluated against those thresholds is a rolling 0-100
  composite built from the same components ForexQuantResearchEngine uses
  cross-sectionally (momentum, mean reversion, breakout, trend quality),
  computed per-bar using only data available up to that bar (no lookahead).
  Carry and cross-pair correlation-risk are excluded here because a
  single-pair rolling backtest doesn't have a full multi-pair panel at every
  historical timestamp; the remaining weights are renormalized to sum to 1.0.
- strategy["risk"] (e.g. "1% per trade") sets a stop-loss distance from
  entry price.
- No transaction costs or slippage are modeled. This is a real, if simple,
  rule-based backtest -- not an institutional-grade execution simulator.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from modules.forex.forex_quant_research_engine import _clip, _score_from_z

DEFAULT_PAIR = "EUR/USD"
DEFAULT_LOOKBACK_DAYS = 730
MIN_BARS = 40


def _fetch_price_series(pair: str, lookback_days: int):
    """Real historical daily closes for `pair` as a pandas Series indexed by date."""
    import pandas as pd
    from modules.forex.forex_history_service import get_forex_history_service

    history_service = get_forex_history_service()
    start = history_service.default_start(days=lookback_days)
    end = history_service.default_end()
    payload = history_service.fetch_from_router(pair, start_date=start, end_date=end, interval="1day")

    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not rows:
        return None

    df = pd.DataFrame(rows)
    if "asof" not in df.columns or "close" not in df.columns:
        return None

    df["asof"] = pd.to_datetime(df["asof"], errors="coerce")
    df = df.dropna(subset=["asof", "close"]).sort_values("asof")
    if df.empty:
        return None

    series = pd.Series(
        pd.to_numeric(df["close"], errors="coerce").values,
        index=df["asof"].values,
        name=pair,
    )
    return series.dropna()


def _rolling_factor_score(closes) -> "Any":
    """Rolling 0-100 composite factor score per bar (see module docstring)."""
    import pandas as pd

    closes = closes.astype(float)

    ret20 = closes.pct_change(20, fill_method=None)
    baseline = ret20.rolling(120, min_periods=30)
    momentum_z = (ret20 - baseline.mean()) / baseline.std(ddof=0)
    momentum_score = momentum_z.apply(_score_from_z)

    ma20 = closes.rolling(20, min_periods=20).mean()
    std20 = closes.rolling(20, min_periods=20).std(ddof=0)
    z_px = (closes - ma20) / std20
    mean_reversion_score = z_px.apply(lambda z: _score_from_z(z, inverse=True))

    high20 = closes.rolling(20, min_periods=20).max()
    low20 = closes.rolling(20, min_periods=20).min()
    breakout_score = pd.Series(50.0, index=closes.index)
    breakout_score[closes >= high20] = 80.0
    breakout_score[closes <= low20] = 20.0
    breakout_score[ma20.isna()] = 50.0

    ma10 = closes.rolling(10, min_periods=10).mean()
    ma30 = closes.rolling(30, min_periods=30).mean()
    trend_quality_score = pd.Series(50.0, index=closes.index)
    trend_quality_score[ma10 > ma30] = 65.0
    trend_quality_score[ma10 < ma30] = 35.0
    trend_quality_score[ma30.isna()] = 50.0

    score = (
        momentum_score * 0.333
        + mean_reversion_score * 0.200
        + breakout_score * 0.200
        + trend_quality_score * 0.267
    )
    return score.clip(lower=0.0, upper=100.0)


def _parse_condition(text: Optional[str], default_op: str, default_threshold: float) -> tuple:
    if not text:
        return default_op, default_threshold
    match = re.search(r"([<>]=?)\s*(\d+(?:\.\d+)?)", str(text))
    if not match:
        return default_op, default_threshold
    op = match.group(1)[0]
    return op, float(match.group(2))


def _parse_risk_pct(text: Optional[str], default: float = 0.01) -> float:
    if not text:
        return default
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", str(text))
    if not match:
        return default
    return float(match.group(1)) / 100.0


def run_single_backtest(strategy: Dict[str, Any], closes, scores) -> Dict[str, Any]:
    """
    Bar-by-bar simulation over `closes`/`scores` (both real, already
    time-aligned). Returns the raw trade list and equity curve so callers
    (walk-forward, Monte Carlo) can reuse this on arbitrary slices.
    """
    import pandas as pd

    entry_op, entry_threshold = _parse_condition(strategy.get("entry"), ">", 65.0)
    exit_op, exit_threshold = _parse_condition(strategy.get("exit"), "<", 50.0)
    risk_pct = _parse_risk_pct(strategy.get("risk"), 0.01)

    side = "LONG" if entry_op == ">" else "SHORT"

    in_position = False
    entry_price: Optional[float] = None
    entry_date = None
    trades: List[Dict[str, Any]] = []
    equity = 1.0
    equity_curve: List[Dict[str, Any]] = []
    prev_close: Optional[float] = None

    dates = closes.index
    n = len(dates)

    for i in range(n):
        date = dates[i]
        price = float(closes.iloc[i])
        score = scores.iloc[i] if i < len(scores) else None

        if in_position and prev_close is not None and prev_close > 0:
            day_ret = (price / prev_close) - 1.0
            if side == "SHORT":
                day_ret = -day_ret
            equity *= (1.0 + day_ret)

        equity_curve.append({"date": date, "equity": round(equity, 6)})

        has_score = score is not None and pd.notna(score)

        if has_score:
            if not in_position:
                enter = (score > entry_threshold) if side == "LONG" else (score < entry_threshold)
                if enter:
                    in_position = True
                    entry_price = price
                    entry_date = date
            else:
                stop_hit = (
                    price <= entry_price * (1 - risk_pct)
                    if side == "LONG"
                    else price >= entry_price * (1 + risk_pct)
                )
                exit_signal = (score < exit_threshold) if side == "LONG" else (score > exit_threshold)

                if stop_hit or exit_signal or i == n - 1:
                    trade_return = (
                        (price / entry_price - 1.0) if side == "LONG" else (entry_price / price - 1.0)
                    )
                    trades.append({
                        "entry_date": str(getattr(entry_date, "date", lambda: entry_date)()),
                        "exit_date": str(getattr(date, "date", lambda: date)()),
                        "side": side,
                        "entry_price": round(entry_price, 5),
                        "exit_price": round(price, 5),
                        "return_pct": round(trade_return * 100, 3),
                        "reason": "stop_loss" if stop_hit else ("signal_exit" if exit_signal else "end_of_period"),
                    })
                    in_position = False
                    entry_price = None
                    entry_date = None

        prev_close = price

    return {
        "side": side,
        "entry_threshold": entry_threshold,
        "exit_threshold": exit_threshold,
        "risk_pct": risk_pct,
        "trades": trades,
        "equity_curve": equity_curve,
    }


def _summarize_run(run: Dict[str, Any]) -> Dict[str, Any]:
    trades = run["trades"]
    equity_curve = run["equity_curve"]

    if not trades:
        return {
            "trades": 0,
            "win_rate": None,
            "profit_factor": None,
            "max_drawdown_pct": None,
            "sharpe": None,
            "total_return_pct": None,
        }

    wins = [t for t in trades if t["return_pct"] > 0]
    losses = [t for t in trades if t["return_pct"] <= 0]
    gross_profit = sum(t["return_pct"] for t in wins)
    gross_loss = abs(sum(t["return_pct"] for t in losses))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None

    equities = [row["equity"] for row in equity_curve]
    total_return_pct = round((equities[-1] / equities[0] - 1.0) * 100, 2) if equities else None

    daily_rets = []
    for i in range(1, len(equities)):
        if equities[i - 1] > 0:
            daily_rets.append(equities[i] / equities[i - 1] - 1.0)

    sharpe = None
    if len(daily_rets) >= 5:
        mean_r = sum(daily_rets) / len(daily_rets)
        var_r = sum((r - mean_r) ** 2 for r in daily_rets) / len(daily_rets)
        std_r = var_r ** 0.5
        if std_r > 0:
            sharpe = round((mean_r / std_r) * (252 ** 0.5), 2)

    peak = equities[0] if equities else 1.0
    max_dd = 0.0
    for e in equities:
        if e > peak:
            peak = e
        dd = (e / peak - 1.0) if peak > 0 else 0.0
        if dd < max_dd:
            max_dd = dd

    return {
        "trades": len(trades),
        "win_rate": round(100 * len(wins) / len(trades), 2),
        "profit_factor": profit_factor,
        "max_drawdown_pct": round(abs(max_dd) * 100, 2),
        "sharpe": sharpe,
        "total_return_pct": total_return_pct,
    }


class ForexStrategyBacktester:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def backtest(
        self,
        strategy: Dict[str, Any],
        pair: Optional[str] = None,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> Dict[str, Any]:
        name = strategy.get("name", "FX Strategy")
        pair = pair or strategy.get("pair") or DEFAULT_PAIR

        try:
            closes = _fetch_price_series(pair, lookback_days)
        except Exception as exc:
            return {"status": "ERROR", "strategy": name, "pair": pair, "error": str(exc)}

        if closes is None or len(closes) < MIN_BARS:
            return {
                "status": "NO_DATA",
                "strategy": name,
                "pair": pair,
                "message": "Not enough live historical data to backtest yet.",
            }

        scores = _rolling_factor_score(closes)
        run = run_single_backtest(strategy, closes, scores)
        summary = _summarize_run(run)

        return {
            "status": "READY",
            "strategy": name,
            "pair": pair,
            "side": run["side"],
            "entry_threshold": run["entry_threshold"],
            "exit_threshold": run["exit_threshold"],
            "risk_pct": round(run["risk_pct"] * 100, 2),
            "lookback_days": lookback_days,
            "bars_analyzed": len(closes),
            **summary,
            "trades_detail": run["trades"][-20:],
            "methodology": (
                "Rule-based long/short backtest on live daily closes. Entry/exit "
                "driven by a rolling composite factor score (momentum, mean "
                "reversion, breakout, trend quality -- carry and cross-pair "
                "correlation are excluded from this single-pair rolling score). "
                "No transaction costs or slippage are modeled."
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_BT = None


def get_forex_strategy_backtester(db: Optional[Any] = None) -> ForexStrategyBacktester:
    global _BT
    if _BT is None or (db is not None and _BT.db is None):
        _BT = ForexStrategyBacktester(db=db)
    return _BT