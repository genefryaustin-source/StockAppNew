"""
modules/risk_layer/engine.py

The orchestrator: pulls positions from the Portfolio module, quant risk
metrics from RiskAnalyticsService, regime context from the Regime Engine,
scanner flags from the AI Scanner, valuation flags from Valuation, options
context from the options bridge, a survival score + defense directive from
the autonomous defense engine, and this tenant's own configured limits --
and merges all of it into one RiskSnapshot dict the UI (and, later, any
automation) can render or act on.
"""

from __future__ import annotations

from typing import Optional

from modules.portfolio.risk_analytics_service import RiskAnalyticsService
from modules.risk.autonomous_defense_engine import (
    portfolio_survival_score,
    generate_defense_directive,
)

from modules.risk_layer.positions import get_positions_df, get_returns_df, portfolio_equity, portfolio_cash
from modules.risk_layer.regime_bridge import get_market_regime, regime_risk_multiplier
from modules.risk_layer.scanner_bridge import scan_positions
from modules.risk_layer.valuation_bridge import valuation_flags
from modules.risk_layer.options_bridge import options_risk_summary
from modules.risk_layer.limits import get_limits, check_breaches
from modules.risk_providers.provider_settings import enabled_providers_for_tenant
from modules.risk_providers.registry import get_risk_provider
from modules.risk_providers.base import RiskProviderRequest


def compute_risk_snapshot(
    db,
    tenant_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    include_scanner: bool = True,
    include_valuation: bool = True,
    include_options: bool = True,
    include_external_providers: bool = True,
) -> dict:
    positions_df = get_positions_df(db, tenant_id=tenant_id, portfolio_id=portfolio_id)
    returns_df = get_returns_df(db, tenant_id=tenant_id, portfolio_id=portfolio_id)
    equity = portfolio_equity(db, tenant_id=tenant_id, portfolio_id=portfolio_id)
    cash = portfolio_cash(db, tenant_id=tenant_id, portfolio_id=portfolio_id)

    data_quality_warnings = list(getattr(positions_df, "attrs", {}).get("data_quality_warnings", [])) + \
        list(getattr(returns_df, "attrs", {}).get("data_quality_warnings", []))

    # ── Quant risk (reuses the existing portfolio risk analytics engine) ──
    analytics = RiskAnalyticsService(returns_df=returns_df, positions_df=positions_df)
    var_95 = analytics.historical_var(confidence=0.95) * equity if equity else 0.0
    es_95 = analytics.expected_shortfall(confidence=0.95) * equity if equity else 0.0
    concentration = analytics.concentration_risk()
    stress = analytics.stress_test()
    drawdown = analytics.drawdown_alert()
    vol_regime = analytics.volatility_regime()
    advanced_risk = analytics.advanced_risk_cross_check(confidence=0.95)
    if advanced_risk.get("riskfolio", {}).get("available") and equity:
        rf = advanced_risk["riskfolio"]
        rf["var_dollar"] = rf["var"] * equity
        rf["cvar_dollar"] = rf["cvar"] * equity
        rf["evar_dollar"] = rf["evar"] * equity

    # ── Exposure by asset class ──────────────────────────────────────────
    exposure_by_class = {}
    if not positions_df.empty:
        exposure_by_class = (
            positions_df.groupby("Asset Class")["Market Value"]
            .apply(lambda s: float(s.abs().sum()))
            .to_dict()
        )
    gross_exposure = sum(exposure_by_class.values())

    # ── Regime context (shared with the Regime Engine page) ─────────────
    regime = get_market_regime(db)
    regime_mult = regime_risk_multiplier(regime["label"])

    # ── Tenant risk limits + breach check ────────────────────────────────
    limits = get_limits(db, tenant_id)
    breaches = check_breaches(
        positions_df, equity, limits, gross_exposure, var_95,
        drawdown.get("current_drawdown"), regime_mult,
    )

    # ── AI Scanner risk flags on held positions ──────────────────────────
    scanner_flags = {}
    if include_scanner and not positions_df.empty:
        symbols = positions_df["Symbol"].tolist()
        scanner_flags = scan_positions(db, symbols)

    # ── Valuation flags on held equities ─────────────────────────────────
    val_flags = {}
    if include_valuation and not positions_df.empty and tenant_id:
        equity_symbols = positions_df.loc[positions_df["Asset Class"] == "equity", "Symbol"].tolist()
        if equity_symbols:
            val_flags = valuation_flags(db, tenant_id, equity_symbols)

    # ── Options-specific context ─────────────────────────────────────────
    options_ctx = options_risk_summary() if include_options else {"available": False, "reason": "skipped"}

    # ── Survival score + defense directive (reuses autonomous_defense_engine) ──
    portfolio_risk_summary = {
        "cash_buffer": (cash / equity * 100.0) if equity else 0.0,
        "portfolio_risk_score": min(100.0, (var_95 / equity * 100.0) if equity else 50.0),
        "portfolio_volatility": vol_regime.get("annualized_vol", 0.0) * 100.0,
        "concentration_risk": (
            "High" if concentration.get("max_weight", 0) > 0.30 else
            "Moderate" if concentration.get("max_weight", 0) > 0.15 else "Controlled"
        ),
        "conviction_strength": "Moderate",
    }
    survival_score = portfolio_survival_score(portfolio_risk_summary)
    # autonomous_defense_engine special-cases specific regime tokens
    # ("bear", "panic") rather than our Risk-On/Risk-Off/Transition labels --
    # map to its vocabulary so the "elevated defensive posture" branch
    # actually triggers instead of silently never matching.
    defense_regime_token = {
        "Risk-On": "bull", "Risk-Off": "bear", "Transition": "neutral", "Unknown": "neutral",
    }.get(regime["label"], "neutral")
    defense_directive = generate_defense_directive(
        current_regime=defense_regime_token,
        portfolio_risk_summary=portfolio_risk_summary,
    )

    # ── External risk vendor cross-checks (supplemental, not authoritative) ──
    external_providers = {}
    if include_external_providers:
        for provider_name in enabled_providers_for_tenant(db, tenant_id):
            try:
                provider = get_risk_provider(provider_name, tenant_id=tenant_id)
                result = provider.fetch_portfolio_risk(RiskProviderRequest(
                    positions_df=positions_df, equity=equity, confidence=0.95, horizon_days=1,
                ))
                external_providers[provider_name] = result.to_dict()
            except Exception as e:
                external_providers[provider_name] = {"provider": provider_name, "available": False, "error": str(e)}

    return {
        "equity": equity,
        "gross_exposure": gross_exposure,
        "exposure_by_asset_class": exposure_by_class,
        "positions": positions_df,
        "var_95_1d": var_95,
        "expected_shortfall_95": es_95,
        "concentration": concentration,
        "stress_test": stress,
        "drawdown": drawdown,
        "volatility_regime": vol_regime,
        "advanced_risk": advanced_risk,
        "market_regime": regime,
        "regime_risk_multiplier": regime_mult,
        "limits": limits,
        "breaches": breaches,
        "data_quality_warnings": data_quality_warnings,
        "scanner_flags": scanner_flags,
        "valuation_flags": val_flags,
        "options": options_ctx,
        "external_risk_providers": external_providers,
        "survival_score": survival_score,
        "defense_directive": defense_directive.to_dict(),
    }
