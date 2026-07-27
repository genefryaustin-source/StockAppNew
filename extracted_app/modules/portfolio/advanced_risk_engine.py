"""
modules/portfolio/advanced_risk_engine.py

Optional upgrade path for modules.portfolio.risk_analytics_service's VaR /
Expected Shortfall / volatility calculations, using two well-established
open-source libraries instead of hand-rolled formulas:

  - arch (https://github.com/bashtage/arch): GARCH(1,1) volatility
    forecasting. Our own volatility_regime() is a naive realized
    volatility (std of daily returns * sqrt(252)) -- it treats every day
    equally and has no concept of volatility clustering or mean
    reversion, which is part of why a single bad data point can distort
    it badly. GARCH models the conditional variance directly and weights
    recent shocks more than old ones.

  - Riskfolio-Lib (https://github.com/dcajasn/Riskfolio-Lib, BSD-3-Clause):
    adds Entropic VaR (EVaR) and Conditional VaR (CVaR) using its own
    tested implementations, alongside our simple historical quantile
    approach. EVaR in particular is a more conservative, "coherent" risk
    measure that accounts for tail thickness rather than just the empirical
    quantile.

Both are optional dependencies -- everything here degrades to
{"available": False, "reason": ...} rather than raising if the packages
aren't installed or there isn't enough return history to fit a model, so
modules.risk_layer never breaks because of this. These are cross-checks
alongside the existing simple methods, not replacements for them.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MIN_OBS_FOR_GARCH = 50
MIN_OBS_FOR_TAIL_RISK = 30


def advanced_risk_status() -> dict:
    missing = []
    for pkg in ("arch", "riskfolio"):
        try:
            __import__(pkg)
        except Exception:
            missing.append(pkg)
    return {"available": len(missing) == 0, "missing_packages": missing}


def garch_volatility_forecast(returns: pd.Series) -> dict:
    """
    Fits a GARCH(1,1) model to a daily return series and forecasts the
    next day's conditional volatility, annualized the same way
    RiskAnalyticsService.volatility_regime() does (daily_vol * sqrt(252))
    so the two are directly comparable.
    """
    rets = pd.Series(returns).dropna()
    if len(rets) < MIN_OBS_FOR_GARCH:
        return {"available": False, "reason": f"Need at least {MIN_OBS_FOR_GARCH} return observations "
                                               f"(have {len(rets)})."}
    try:
        from arch import arch_model
    except ImportError:
        return {"available": False, "reason": "The 'arch' package isn't installed."}

    try:
        # arch works best with returns scaled to roughly O(1) percent, not
        # raw decimals -- rescale in and back out rather than change units.
        am = arch_model(rets * 100, vol="Garch", p=1, q=1, dist="normal", mean="Zero")
        res = am.fit(disp="off", show_warning=False)
        fcast = res.forecast(horizon=1, reindex=False)
        variance_pct2 = float(fcast.variance.values[-1, 0])
        daily_vol = (variance_pct2 ** 0.5) / 100.0
        annualized_vol = daily_vol * (252 ** 0.5)
        return {
            "available": True,
            "method": "GARCH(1,1)",
            "daily_vol": daily_vol,
            "annualized_vol": annualized_vol,
        }
    except Exception as e:
        return {"available": False, "reason": f"GARCH fit failed: {e}"}


def riskfolio_tail_risk(returns: pd.Series, confidence: float = 0.95) -> dict:
    """
    Computes VaR, CVaR, and EVaR via Riskfolio-Lib's own tested
    implementations (VaR_Hist / CVaR_Hist / EVaR_Hist), as a cross-check
    on RiskAnalyticsService's hand-rolled historical_var/expected_shortfall.
    All three are returned as positive loss fractions (e.g. 0.02 = 2%),
    same convention as RiskAnalyticsService.
    """
    rets = pd.Series(returns).dropna()
    if len(rets) < MIN_OBS_FOR_TAIL_RISK:
        return {"available": False, "reason": f"Need at least {MIN_OBS_FOR_TAIL_RISK} return observations "
                                               f"(have {len(rets)})."}
    try:
        import riskfolio as rp
    except ImportError:
        return {"available": False, "reason": "The 'riskfolio-lib' package isn't installed."}

    alpha = 1.0 - confidence
    try:
        x = rets.to_numpy()
        var = float(rp.VaR_Hist(x, alpha=alpha))
        cvar = float(rp.CVaR_Hist(x, alpha=alpha))
        evar, _z = rp.EVaR_Hist(x, alpha=alpha)
        return {
            "available": True,
            "method": "Riskfolio-Lib",
            "var": var,
            "cvar": cvar,
            "evar": float(evar),
        }
    except Exception as e:
        return {"available": False, "reason": f"Riskfolio-Lib tail risk calc failed: {e}"}
