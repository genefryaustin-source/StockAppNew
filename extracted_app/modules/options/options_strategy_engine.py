"""
modules/options/options_strategy_engine.py

Institutional options strategy analytics engine.

Adds:
- strategy templates
- multi-leg payoff model
- P/L curve engine
- max profit/loss/breakeven extraction
- expected move engine
- options probability approximations
- Greeks aggregation
- volatility intelligence
- screener candidate scoring
- wheel and covered-call candidate analytics
- 0DTE helpers

Pure Python/Pandas/Numpy. No database dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from math import erf, exp, log, sqrt, pi
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd


@dataclass
class OptionLeg:
    action: str                 # buy | sell
    option_type: str            # call | put
    strike: float
    premium: float
    contracts: int = 1
    expiry: str = ""
    dte: int = 0
    iv: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    option_symbol: str = ""

    @property
    def sign(self) -> int:
        return 1 if str(self.action).lower().startswith("buy") else -1

    @property
    def multiplier(self) -> int:
        return 100


@dataclass
class StrategySummary:
    strategy_name: str
    net_debit_credit: float
    max_profit: Any
    max_loss: Any
    breakevens: list[float]
    risk_reward: Optional[float]
    probability_profit: Optional[float]
    expected_value: Optional[float]
    notes: list[str]


# ─────────────────────────────────────────────────────────────
# Normalization helpers
# ─────────────────────────────────────────────────────────────

def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return default
        return float(v)
    except Exception:
        return default


def _mid(row: Any) -> float:
    bid = _to_float(_row_get(row, "bid"), 0.0)
    ask = _to_float(_row_get(row, "ask"), 0.0)
    last = _to_float(_row_get(row, "last"), 0.0)
    last2 = _to_float(_row_get(row, "lastPrice"), 0.0)
    if bid > 0 and ask > 0:
        return round((bid + ask) / 2, 4)
    return last or last2 or 0.01


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    try:
        if isinstance(row, dict):
            return row.get(key, default)
        return row.get(key, default)
    except Exception:
        return default


def _norm_type(value: Any) -> str:
    s = str(value or "").lower()
    if s.startswith("c"):
        return "call"
    if s.startswith("p"):
        return "put"
    return s or "call"


def _nearest_row(df: pd.DataFrame, strike: float) -> Optional[pd.Series]:
    if df is None or df.empty or "strike" not in df.columns:
        return None
    idx = (df["strike"].astype(float) - float(strike)).abs().idxmin()
    return df.loc[idx]


def _chain_frames(chain_data: dict, expiry: Optional[str] = None) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    expirations = chain_data.get("expirations") or []
    if not expiry:
        expiry = expirations[0] if expirations else ""
    chain = (chain_data.get("chain") or chain_data.get("chains") or {}).get(expiry, {})
    calls = chain.get("calls", pd.DataFrame())
    puts = chain.get("puts", pd.DataFrame())
    return calls if isinstance(calls, pd.DataFrame) else pd.DataFrame(calls), puts if isinstance(puts, pd.DataFrame) else pd.DataFrame(puts), expiry


# ─────────────────────────────────────────────────────────────
# Payoff model
# ─────────────────────────────────────────────────────────────

def leg_payoff(leg: OptionLeg, prices: np.ndarray) -> np.ndarray:
    if leg.option_type == "call":
        intrinsic = np.maximum(prices - leg.strike, 0.0)
    else:
        intrinsic = np.maximum(leg.strike - prices, 0.0)

    # Long option = intrinsic minus premium. Short option = premium minus intrinsic.
    pnl_per_share = leg.sign * (intrinsic - leg.premium)
    return pnl_per_share * leg.contracts * leg.multiplier


def strategy_payoff(legs: Iterable[OptionLeg], prices: np.ndarray) -> np.ndarray:
    total = np.zeros_like(prices, dtype=float)
    for leg in legs:
        total += leg_payoff(leg, prices)
    return total


def price_grid(spot: float, span_pct: float = 0.35, points: int = 181) -> np.ndarray:
    low = max(0.01, float(spot) * (1 - span_pct))
    high = float(spot) * (1 + span_pct)
    return np.linspace(low, high, points)


def net_debit_credit(legs: Iterable[OptionLeg]) -> float:
    # Positive = debit paid. Negative = credit received.
    total = 0.0
    for leg in legs:
        total += leg.sign * leg.premium * leg.contracts * leg.multiplier
    return round(total, 2)


def find_breakevens(prices: np.ndarray, pnl: np.ndarray) -> list[float]:
    bes: list[float] = []
    for i in range(1, len(prices)):
        y1, y2 = pnl[i - 1], pnl[i]
        if y1 == 0:
            bes.append(round(float(prices[i - 1]), 2))
        elif (y1 < 0 < y2) or (y1 > 0 > y2):
            # Linear interpolation
            x1, x2 = prices[i - 1], prices[i]
            x = x1 + (0 - y1) * (x2 - x1) / (y2 - y1)
            bes.append(round(float(x), 2))
    # De-duplicate near-identical roots
    unique: list[float] = []
    for b in bes:
        if not unique or abs(unique[-1] - b) > 0.10:
            unique.append(b)
    return unique[:6]


def summarize_strategy(
    strategy_name: str,
    legs: list[OptionLeg],
    spot: float,
    iv: Optional[float] = None,
    dte: Optional[int] = None,
) -> StrategySummary:
    prices = price_grid(spot, span_pct=0.50, points=501)
    pnl = strategy_payoff(legs, prices)
    debit = net_debit_credit(legs)

    max_profit_val = round(float(np.max(pnl)), 2)
    max_loss_val = round(float(np.min(pnl)), 2)
    breakevens = find_breakevens(prices, pnl)

    # If payoff keeps improving at edges, mark unbounded.
    max_profit: Any = max_profit_val
    max_loss: Any = abs(max_loss_val)
    if pnl[-1] == np.max(pnl) and any(l.option_type == "call" and l.sign == 1 for l in legs):
        max_profit = "Unbounded upside"
    if pnl[0] == np.min(pnl) and any(l.option_type == "put" and l.sign == -1 for l in legs):
        max_loss = "Large downside risk"

    rr = None
    try:
        if isinstance(max_profit, (int, float)) and isinstance(max_loss, (int, float)) and max_loss > 0:
            rr = round(float(max_profit) / float(max_loss), 2)
    except Exception:
        rr = None

    prob_profit = probability_profit(spot, breakevens, iv=iv, dte=dte)
    ev = expected_value_from_curve(prices, pnl, spot=spot, iv=iv, dte=dte)

    notes = []
    if debit > 0:
        notes.append(f"Net debit: ${debit:,.2f}.")
    elif debit < 0:
        notes.append(f"Net credit: ${abs(debit):,.2f}.")
    else:
        notes.append("Near-zero net premium.")
    if breakevens:
        notes.append("Breakeven(s): " + ", ".join(f"${b:,.2f}" for b in breakevens))
    if prob_profit is not None:
        notes.append(f"Approx. probability of profit: {prob_profit:.1%}.")

    return StrategySummary(
        strategy_name=strategy_name,
        net_debit_credit=debit,
        max_profit=max_profit,
        max_loss=max_loss,
        breakevens=breakevens,
        risk_reward=rr,
        probability_profit=prob_profit,
        expected_value=ev,
        notes=notes,
    )


# ─────────────────────────────────────────────────────────────
# Black-Scholes helpers
# ─────────────────────────────────────────────────────────────

def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def norm_pdf(x: float) -> float:
    return (1.0 / sqrt(2.0 * pi)) * exp(-0.5 * x * x)


def _d1_d2(spot: float, strike: float, dte: int, iv: float, r: float = 0.045) -> tuple[float, float]:
    t = max(float(dte), 1.0) / 365.0
    iv = max(float(iv or 0.01), 0.01)
    d1 = (log(max(spot, 0.01) / max(strike, 0.01)) + (r + 0.5 * iv * iv) * t) / (iv * sqrt(t))
    return d1, d1 - iv * sqrt(t)


def probability_itm(spot: float, strike: float, option_type: str, iv: Optional[float], dte: Optional[int]) -> Optional[float]:
    if not iv or not dte:
        return None
    d1, d2 = _d1_d2(spot, strike, int(dte), float(iv))
    if _norm_type(option_type) == "call":
        return norm_cdf(d2)
    return norm_cdf(-d2)


def probability_touch(spot: float, strike: float, iv: Optional[float], dte: Optional[int]) -> Optional[float]:
    p_itm_call = probability_itm(spot, strike, "call" if strike >= spot else "put", iv, dte)
    if p_itm_call is None:
        return None
    return min(1.0, max(0.0, 2.0 * p_itm_call))


def probability_profit(spot: float, breakevens: list[float], iv: Optional[float], dte: Optional[int]) -> Optional[float]:
    if not breakevens or not iv or not dte:
        return None
    sigma = float(spot) * float(iv) * sqrt(max(int(dte), 1) / 365.0)
    if sigma <= 0:
        return None
    # Approximate with normal distribution around spot.
    if len(breakevens) == 1:
        be = breakevens[0]
        if be >= spot:
            return 1.0 - norm_cdf((be - spot) / sigma)
        return norm_cdf((be - spot) / sigma)
    low, high = min(breakevens), max(breakevens)
    # For range-bound strategies, profit is usually between breakevens.
    inside = norm_cdf((high - spot) / sigma) - norm_cdf((low - spot) / sigma)
    return max(0.0, min(1.0, inside))


def expected_value_from_curve(prices: np.ndarray, pnl: np.ndarray, spot: float, iv: Optional[float], dte: Optional[int]) -> Optional[float]:
    if not iv or not dte:
        return None
    sigma = float(spot) * float(iv) * sqrt(max(int(dte), 1) / 365.0)
    if sigma <= 0:
        return None
    weights = np.exp(-0.5 * ((prices - spot) / sigma) ** 2)
    weights = weights / max(weights.sum(), 1e-9)
    return round(float(np.sum(weights * pnl)), 2)


def expected_move(spot: float, iv: Optional[float], dte: int) -> dict:
    if not iv:
        return {"error": "IV unavailable"}
    move = float(spot) * float(iv) * sqrt(max(int(dte), 1) / 365.0)
    return {
        "spot": float(spot),
        "iv": float(iv),
        "dte": int(dte),
        "expected_move": round(move, 2),
        "expected_move_pct": round(move / float(spot), 4) if spot else None,
        "low_68": round(float(spot) - move, 2),
        "high_68": round(float(spot) + move, 2),
        "low_95": round(float(spot) - 2 * move, 2),
        "high_95": round(float(spot) + 2 * move, 2),
    }


def atm_straddle_expected_move(calls: pd.DataFrame, puts: pd.DataFrame, spot: float) -> Optional[dict]:
    c = _nearest_row(calls, spot)
    p = _nearest_row(puts, spot)
    if c is None or p is None:
        return None
    c_mid, p_mid = _mid(c), _mid(p)
    move = c_mid + p_mid
    return {
        "atm_strike": _to_float(_row_get(c, "strike")),
        "call_mid": c_mid,
        "put_mid": p_mid,
        "straddle_move": round(move, 2),
        "straddle_move_pct": round(move / spot, 4) if spot else None,
        "low": round(spot - move, 2),
        "high": round(spot + move, 2),
    }


# ─────────────────────────────────────────────────────────────
# Strategy templates
# ─────────────────────────────────────────────────────────────

def build_strategy_from_chain(
    strategy: str,
    chain_data: dict,
    spot: float,
    expiry: Optional[str] = None,
    width: float = 5.0,
) -> list[OptionLeg]:
    calls, puts, expiry = _chain_frames(chain_data, expiry)
    if calls.empty and puts.empty:
        return []

    strategy_key = strategy.lower().strip()
    atm_call = _nearest_row(calls, spot)
    atm_put = _nearest_row(puts, spot)

    def leg(action: str, option_type: str, row: pd.Series) -> OptionLeg:
        return OptionLeg(
            action=action,
            option_type=option_type,
            strike=_to_float(row.get("strike")),
            premium=max(_mid(row), 0.01),
            expiry=expiry,
            dte=int(_to_float(row.get("dte"), 0)),
            iv=row.get("iv", row.get("impliedVolatility", None)),
            delta=row.get("delta", None),
            gamma=row.get("gamma", None),
            theta=row.get("theta", None),
            vega=row.get("vega", None),
            option_symbol=str(row.get("option_symbol", row.get("optionSymbol", ""))),
        )

    legs: list[OptionLeg] = []

    if strategy_key in ("long call", "call"):
        if atm_call is not None:
            legs.append(leg("buy", "call", atm_call))

    elif strategy_key in ("long put", "put"):
        if atm_put is not None:
            legs.append(leg("buy", "put", atm_put))

    elif strategy_key in ("covered call",):
        # Options-only leg. Stock leg represented separately in UI.
        otm = _nearest_row(calls, spot * 1.05)
        if otm is not None:
            legs.append(leg("sell", "call", otm))

    elif strategy_key in ("cash secured put", "short put"):
        otm = _nearest_row(puts, spot * 0.95)
        if otm is not None:
            legs.append(leg("sell", "put", otm))

    elif strategy_key in ("bull call spread", "vertical call spread"):
        long_row = _nearest_row(calls, spot)
        short_row = _nearest_row(calls, spot + width)
        if long_row is not None and short_row is not None:
            legs.extend([leg("buy", "call", long_row), leg("sell", "call", short_row)])

    elif strategy_key in ("bear put spread", "vertical put spread"):
        long_row = _nearest_row(puts, spot)
        short_row = _nearest_row(puts, max(0.01, spot - width))
        if long_row is not None and short_row is not None:
            legs.extend([leg("buy", "put", long_row), leg("sell", "put", short_row)])

    elif strategy_key in ("long straddle", "straddle"):
        if atm_call is not None and atm_put is not None:
            legs.extend([leg("buy", "call", atm_call), leg("buy", "put", atm_put)])

    elif strategy_key in ("long strangle", "strangle"):
        c_row = _nearest_row(calls, spot * 1.05)
        p_row = _nearest_row(puts, spot * 0.95)
        if c_row is not None and p_row is not None:
            legs.extend([leg("buy", "call", c_row), leg("buy", "put", p_row)])

    elif strategy_key in ("iron condor",):
        p_short = _nearest_row(puts, spot * 0.95)
        p_long = _nearest_row(puts, spot * 0.90)
        c_short = _nearest_row(calls, spot * 1.05)
        c_long = _nearest_row(calls, spot * 1.10)
        for action, typ, row in [("buy", "put", p_long), ("sell", "put", p_short), ("sell", "call", c_short), ("buy", "call", c_long)]:
            if row is not None:
                legs.append(leg(action, typ, row))

    elif strategy_key in ("butterfly", "call butterfly"):
        low = _nearest_row(calls, spot - width)
        mid = _nearest_row(calls, spot)
        high = _nearest_row(calls, spot + width)
        if low is not None and mid is not None and high is not None:
            legs.extend([leg("buy", "call", low), leg("sell", "call", mid), leg("sell", "call", mid), leg("buy", "call", high)])

    return legs


def strategy_template_catalog() -> pd.DataFrame:
    return pd.DataFrame([
        {"Strategy": "Long Call", "View": "Bullish", "Volatility": "Low/Medium", "Risk": "Debit paid", "Best For": "Directional upside"},
        {"Strategy": "Long Put", "View": "Bearish", "Volatility": "Low/Medium", "Risk": "Debit paid", "Best For": "Directional downside"},
        {"Strategy": "Covered Call", "View": "Neutral/Bullish", "Volatility": "Medium/High", "Risk": "Underlying downside", "Best For": "Income on stock"},
        {"Strategy": "Cash Secured Put", "View": "Neutral/Bullish", "Volatility": "High", "Risk": "Assignment", "Best For": "Get paid to wait"},
        {"Strategy": "Bull Call Spread", "View": "Bullish", "Volatility": "Medium", "Risk": "Defined", "Best For": "Lower-cost upside"},
        {"Strategy": "Bear Put Spread", "View": "Bearish", "Volatility": "Medium", "Risk": "Defined", "Best For": "Lower-cost downside"},
        {"Strategy": "Long Straddle", "View": "Volatile", "Volatility": "Low before move", "Risk": "Debit paid", "Best For": "Large move either way"},
        {"Strategy": "Long Strangle", "View": "Volatile", "Volatility": "Low before move", "Risk": "Debit paid", "Best For": "Cheaper large-move bet"},
        {"Strategy": "Iron Condor", "View": "Neutral", "Volatility": "High and falling", "Risk": "Defined", "Best For": "Range income"},
        {"Strategy": "Butterfly", "View": "Pin/Neutral", "Volatility": "Medium", "Risk": "Defined", "Best For": "Target price pin"},
    ])


# ─────────────────────────────────────────────────────────────
# Greeks / volatility / screener
# ─────────────────────────────────────────────────────────────

def aggregate_greeks(positions: Iterable[dict]) -> dict:
    totals = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    rows = []
    for p in positions or []:
        qty = _to_float(p.get("qty"), 0.0)
        mult = 100.0
        for greek in totals:
            totals[greek] += _to_float(p.get(greek), 0.0) * qty * mult
        rows.append({**p, **{f"${k}": round(v, 2) for k, v in totals.items()}})
    return {k: round(v, 2) for k, v in totals.items()}


def volatility_snapshot(chain_data: dict) -> dict:
    all_rows = chain_data.get("all_rows", chain_data.get("raw_df", pd.DataFrame()))
    if all_rows is None or not isinstance(all_rows, pd.DataFrame) or all_rows.empty:
        return {"error": "No chain rows available"}

    iv_col = "iv" if "iv" in all_rows.columns else "impliedVolatility"
    ivs = pd.to_numeric(all_rows.get(iv_col), errors="coerce").dropna()
    if ivs.empty:
        return {"error": "No IV values available"}

    median_iv = float(ivs.median())
    mean_iv = float(ivs.mean())
    high_iv = float(ivs.quantile(0.90))
    low_iv = float(ivs.quantile(0.10))
    iv_rank_proxy = (median_iv - low_iv) / max(high_iv - low_iv, 1e-9)

    return {
        "median_iv": round(median_iv, 4),
        "mean_iv": round(mean_iv, 4),
        "iv_rank_proxy": round(max(0.0, min(1.0, iv_rank_proxy)), 4),
        "iv_10p": round(low_iv, 4),
        "iv_90p": round(high_iv, 4),
        "contracts_with_iv": int(len(ivs)),
    }


def screen_options(chain_data: dict, spot: float, min_volume: int = 100, min_oi: int = 250) -> pd.DataFrame:
    all_rows = chain_data.get("all_rows", chain_data.get("raw_df", pd.DataFrame()))
    if all_rows is None or not isinstance(all_rows, pd.DataFrame) or all_rows.empty:
        return pd.DataFrame()

    df = all_rows.copy()
    for col in ("volume", "open_interest", "strike"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "iv" not in df.columns and "impliedVolatility" in df.columns:
        df["iv"] = pd.to_numeric(df["impliedVolatility"], errors="coerce")
    else:
        df["iv"] = pd.to_numeric(df.get("iv"), errors="coerce")

    df["distance_pct"] = (df["strike"] - float(spot)).abs() / max(float(spot), 0.01)
    df["vol_oi_ratio"] = df["volume"] / df["open_interest"].replace(0, np.nan)
    df["liquidity_score"] = np.log1p(df["volume"]) + np.log1p(df["open_interest"])
    df["iv_score"] = df["iv"].fillna(df["iv"].median())
    df["candidate_score"] = (
        df["liquidity_score"].fillna(0)
        + df["vol_oi_ratio"].fillna(0).clip(0, 5)
        - df["distance_pct"].fillna(1) * 2
    )
    filtered = df[(df["volume"] >= min_volume) & (df["open_interest"] >= min_oi)].copy()
    return filtered.sort_values("candidate_score", ascending=False).head(50)


def covered_call_candidates(chain_data: dict, spot: float, shares: int = 100, expiry: Optional[str] = None) -> pd.DataFrame:
    calls, _, expiry = _chain_frames(chain_data, expiry)
    if calls.empty:
        return pd.DataFrame()
    df = calls.copy()
    df["mid"] = df.apply(_mid, axis=1)
    df["strike"] = pd.to_numeric(df["strike"], errors="coerce")
    df["premium_income"] = df["mid"] * max(int(shares), 100)
    df["assignment_return"] = ((df["strike"] - spot) + df["mid"]) / max(spot, 0.01)
    df["income_yield"] = df["mid"] / max(spot, 0.01)
    df = df[df["strike"] >= spot].copy()
    return df.sort_values(["income_yield", "open_interest", "volume"], ascending=False).head(25)


def cash_secured_put_candidates(chain_data: dict, spot: float, expiry: Optional[str] = None) -> pd.DataFrame:
    _, puts, expiry = _chain_frames(chain_data, expiry)
    if puts.empty:
        return pd.DataFrame()
    df = puts.copy()
    df["mid"] = df.apply(_mid, axis=1)
    df["strike"] = pd.to_numeric(df["strike"], errors="coerce")
    df["cash_required"] = df["strike"] * 100
    df["premium_income"] = df["mid"] * 100
    df["premium_yield"] = df["premium_income"] / df["cash_required"].replace(0, np.nan)
    df = df[df["strike"] <= spot].copy()
    return df.sort_values(["premium_yield", "open_interest", "volume"], ascending=False).head(25)


def zero_dte_candidates(chain_data: dict, spot: float) -> pd.DataFrame:
    all_rows = chain_data.get("all_rows", chain_data.get("raw_df", pd.DataFrame()))
    if all_rows is None or not isinstance(all_rows, pd.DataFrame) or all_rows.empty:
        return pd.DataFrame()
    df = all_rows.copy()
    if "dte" not in df.columns:
        return pd.DataFrame()
    df = df[pd.to_numeric(df["dte"], errors="coerce").fillna(999) <= 1].copy()
    if df.empty:
        return df
    df["mid"] = df.apply(_mid, axis=1)
    df["distance_pct"] = (pd.to_numeric(df["strike"], errors="coerce") - spot).abs() / max(spot, 0.01)
    df["zero_dte_score"] = (
        np.log1p(pd.to_numeric(df.get("volume"), errors="coerce").fillna(0))
        + np.log1p(pd.to_numeric(df.get("open_interest"), errors="coerce").fillna(0))
        - df["distance_pct"] * 8
    )
    return df.sort_values("zero_dte_score", ascending=False).head(50)


def rows_to_legs(rows: list[dict]) -> list[OptionLeg]:
    legs = []
    for r in rows:
        legs.append(OptionLeg(
            action=str(r.get("action", "buy")).lower(),
            option_type=_norm_type(r.get("option_type", r.get("type", "call"))),
            strike=_to_float(r.get("strike")),
            premium=_to_float(r.get("premium", r.get("mid", r.get("last", 0.01))), 0.01),
            contracts=int(_to_float(r.get("contracts", 1), 1)),
            expiry=str(r.get("expiry", "")),
            dte=int(_to_float(r.get("dte", 0), 0)),
            iv=r.get("iv"),
            delta=r.get("delta"),
            gamma=r.get("gamma"),
            theta=r.get("theta"),
            vega=r.get("vega"),
            option_symbol=str(r.get("option_symbol", "")),
        ))
    return legs


def legs_to_frame(legs: list[OptionLeg]) -> pd.DataFrame:
    return pd.DataFrame([asdict(l) for l in legs])
