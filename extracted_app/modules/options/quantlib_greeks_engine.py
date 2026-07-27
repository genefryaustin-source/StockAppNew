"""
modules/options/quantlib_greeks_engine.py

Real options Greeks via QuantLib (https://github.com/lballabio/QuantLib,
BSD license) -- the industry-standard open-source derivatives pricing
library. This closes a gap flagged explicitly in
modules.risk_layer.options_bridge: broker position feeds (e.g. Alpaca's
raw /v2/positions) don't include live Greeks, so the Risk Layer's Options
tab could only report notional/expiry concentration, not real delta/
gamma/theta/vega exposure. This module computes them directly from
Black-Scholes-Merton inputs (spot, strike, expiry, rate, dividend yield,
implied vol) instead.

Units follow standard trading convention, not QuantLib's raw output:
  - delta, gamma: per 1.0 change in the underlying (QuantLib's native units)
  - theta: per CALENDAR DAY (QuantLib returns per year; divided by 365)
  - vega: per 1 percentage point of vol (QuantLib returns per 100%; divided by 100)
  - rho: per 1 percentage point of rate (QuantLib returns per 100%; divided by 100)

Requires an implied volatility input -- this module doesn't estimate IV
from a market price (that's a separate root-finding problem); if you only
have a market price, use `implied_volatility()` below first.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

import QuantLib as ql

DEFAULT_RISK_FREE_RATE = 0.045   # approximate short-term US Treasury yield;
DEFAULT_DIVIDEND_YIELD = 0.0     # override per-underlying where known.


@dataclass
class GreeksResult:
    available: bool
    npv: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None       # per calendar day
    vega: Optional[float] = None        # per 1 vol point
    rho: Optional[float] = None         # per 1 rate point
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "available": self.available, "npv": self.npv, "delta": self.delta,
            "gamma": self.gamma, "theta": self.theta, "vega": self.vega,
            "rho": self.rho, "error": self.error,
        }


def _to_ql_date(d: date) -> ql.Date:
    return ql.Date(d.day, d.month, d.year)


def compute_greeks(
    *,
    spot: float,
    strike: float,
    expiry: date,
    option_type: str,           # "call" or "put"
    implied_vol: float,         # as a decimal, e.g. 0.28 for 28%
    valuation_date: Optional[date] = None,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD,
    is_american: bool = False,
) -> GreeksResult:
    """
    Black-Scholes-Merton Greeks for a single option. American-style
    options use a finite-difference (binomial) engine, since QuantLib's
    fast analytic engine only prices European exercise -- the tradeoff is
    American Greeks cost more to compute but handle early-exercise value.
    """
    try:
        valuation_date = valuation_date or date.today()
        calc_date = _to_ql_date(valuation_date)
        ql.Settings.instance().evaluationDate = calc_date

        expiry_date = _to_ql_date(expiry)
        if expiry_date <= calc_date:
            return GreeksResult(available=False, error="Option has already expired.")
        if implied_vol is None or implied_vol <= 0:
            return GreeksResult(available=False, error="A positive implied volatility is required.")

        opt_type = ql.Option.Call if option_type.lower().startswith("c") else ql.Option.Put
        payoff = ql.PlainVanillaPayoff(opt_type, strike)

        day_count = ql.Actual365Fixed()
        calendar = ql.NullCalendar()
        spot_h = ql.QuoteHandle(ql.SimpleQuote(spot))
        rate_ts = ql.YieldTermStructureHandle(ql.FlatForward(calc_date, risk_free_rate, day_count))
        div_ts = ql.YieldTermStructureHandle(ql.FlatForward(calc_date, dividend_yield, day_count))
        vol_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(calc_date, calendar, implied_vol, day_count)
        )
        process = ql.BlackScholesMertonProcess(spot_h, div_ts, rate_ts, vol_ts)

        if is_american:
            exercise = ql.AmericanExercise(calc_date, expiry_date)
            option = ql.VanillaOption(payoff, exercise)
            steps = 200
            option.setPricingEngine(ql.BinomialVanillaEngine(process, "crr", steps))
            npv = option.NPV()
            delta = option.delta()
            try:
                gamma = option.gamma()
            except RuntimeError:
                gamma = None
            # Theta/vega/rho via date- or vol-bumping a binomial tree is a
            # known QuantLib footgun: term structures built with a fixed
            # reference date (as done above) don't track a bumped global
            # evaluationDate, so a naive finite-difference theta silently
            # returns zero instead of erroring -- worse than just not
            # reporting it. Rather than ship a number that's wrong in a
            # way that's hard to notice, American theta/vega/rho are left
            # unavailable; delta/gamma (computed via QuantLib's built-in
            # spot-bumping, not date-bumping) are unaffected and reliable.
            theta = None
            vega = None
            rho = None
        else:
            exercise = ql.EuropeanExercise(expiry_date)
            option = ql.VanillaOption(payoff, exercise)
            option.setPricingEngine(ql.AnalyticEuropeanEngine(process))
            npv = option.NPV()
            delta = option.delta()
            gamma = option.gamma()
            theta = option.theta() / 365.0
            vega = option.vega() / 100.0
            rho = option.rho() / 100.0

        return GreeksResult(
            available=True, npv=npv, delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho,
        )
    except Exception as e:
        return GreeksResult(available=False, error=f"QuantLib Greeks calculation failed: {e}")


def implied_volatility(
    *,
    market_price: float,
    spot: float,
    strike: float,
    expiry: date,
    option_type: str,
    valuation_date: Optional[date] = None,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD,
) -> Optional[float]:
    """Backs out implied vol from an observed option price -- use this
    first if you have a market price but not a quoted IV, then feed the
    result into compute_greeks()."""
    try:
        valuation_date = valuation_date or date.today()
        calc_date = _to_ql_date(valuation_date)
        ql.Settings.instance().evaluationDate = calc_date

        opt_type = ql.Option.Call if option_type.lower().startswith("c") else ql.Option.Put
        payoff = ql.PlainVanillaPayoff(opt_type, strike)
        exercise = ql.EuropeanExercise(_to_ql_date(expiry))
        option = ql.VanillaOption(payoff, exercise)

        day_count = ql.Actual365Fixed()
        spot_h = ql.QuoteHandle(ql.SimpleQuote(spot))
        rate_ts = ql.YieldTermStructureHandle(ql.FlatForward(calc_date, risk_free_rate, day_count))
        div_ts = ql.YieldTermStructureHandle(ql.FlatForward(calc_date, dividend_yield, day_count))
        vol_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(calc_date, ql.NullCalendar(), 0.20, day_count)
        )
        process = ql.BlackScholesMertonProcess(spot_h, div_ts, rate_ts, vol_ts)
        return option.impliedVolatility(market_price, process)
    except Exception:
        return None
