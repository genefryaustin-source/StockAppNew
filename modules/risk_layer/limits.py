"""
modules/risk_layer/limits.py

Per-tenant risk limits for the Internal Risk Layer, backed by
modules.db.models.TenantRiskLimit. Same pattern as broker enable/disable
settings: no row means "use the default," a tenant/super admin can override
each one, and regime_bridge's risk multiplier automatically tightens the
effective limit in Risk-Off conditions without anyone having to remember
to do it by hand.
"""

from __future__ import annotations

from typing import Optional

from modules.db.models import TenantRiskLimit

DEFAULT_LIMITS = {
    "max_gross_exposure_multiple": 1.50,   # gross exposure / equity
    "max_single_name_weight": 0.25,        # abs(market value) / total mv, any one symbol
    "max_asset_class_weight_crypto": 0.20,
    "max_asset_class_weight_option": 0.30,
    "max_asset_class_weight_forex": 0.30,
    "max_asset_class_weight_real_world_asset": 0.30,
    "max_var_95_pct_of_equity": 0.05,      # 1-day historical VaR as % of equity
    "max_drawdown_halt": -0.20,            # current drawdown that should trigger a halt
}

LIMIT_DESCRIPTIONS = {
    "max_gross_exposure_multiple": "Max gross exposure (long + short) as a multiple of equity",
    "max_single_name_weight": "Max weight of any single position (as a fraction, e.g. 0.25 = 25%)",
    "max_asset_class_weight_crypto": "Max share of the book in crypto",
    "max_asset_class_weight_option": "Max share of the book in options",
    "max_asset_class_weight_forex": "Max share of the book in forex",
    "max_asset_class_weight_real_world_asset": "Max share of the book in tokenized real-world assets",
    "max_var_95_pct_of_equity": "Max 1-day historical VaR (95%) as a fraction of equity",
    "max_drawdown_halt": "Drawdown level (negative) that should trigger a trading halt",
}


def get_limits(db, tenant_id: Optional[str]) -> dict:
    """Returns the effective limits dict for a tenant -- defaults merged
    with any tenant-specific overrides."""
    limits = dict(DEFAULT_LIMITS)
    if not tenant_id:
        return limits
    rows = db.query(TenantRiskLimit).filter(TenantRiskLimit.tenant_id == tenant_id).all()
    for row in rows:
        if row.limit_name in limits:
            limits[row.limit_name] = row.limit_value
    return limits


def set_limit(db, tenant_id: str, limit_name: str, value: float, user_id: str = None) -> None:
    if limit_name not in DEFAULT_LIMITS:
        raise ValueError(f"Unknown risk limit: {limit_name!r}")

    row = (
        db.query(TenantRiskLimit)
        .filter(TenantRiskLimit.tenant_id == tenant_id, TenantRiskLimit.limit_name == limit_name)
        .first()
    )
    if row:
        row.limit_value = value
        row.updated_by_user_id = user_id
    else:
        db.add(TenantRiskLimit(tenant_id=tenant_id, limit_name=limit_name, limit_value=value,
                                updated_by_user_id=user_id))
    db.commit()


def reset_limit(db, tenant_id: str, limit_name: str) -> None:
    row = (
        db.query(TenantRiskLimit)
        .filter(TenantRiskLimit.tenant_id == tenant_id, TenantRiskLimit.limit_name == limit_name)
        .first()
    )
    if row:
        db.delete(row)
        db.commit()


def check_breaches(positions_df, equity: float, limits: dict, gross_exposure: float,
                    var_95: float, current_drawdown: float, regime_multiplier: float = 1.0) -> list[dict]:
    """
    Evaluates every limit against the current book. regime_multiplier
    (0-1) tightens exposure-style limits automatically in worse regimes --
    a 0.65 multiplier in Risk-Off means a 1.5x gross exposure limit
    effectively becomes 0.975x until conditions improve.
    """
    breaches = []

    if equity > 0:
        gross_mult = gross_exposure / equity
        effective_gross_limit = limits["max_gross_exposure_multiple"] * regime_multiplier
        if gross_mult > effective_gross_limit:
            breaches.append({
                "limit": "max_gross_exposure_multiple",
                "message": f"Gross exposure {gross_mult:.2f}x exceeds the regime-adjusted "
                           f"limit of {effective_gross_limit:.2f}x (base {limits['max_gross_exposure_multiple']:.2f}x).",
            })

    if positions_df is not None and not positions_df.empty and "Weight" in positions_df.columns:
        max_weight = float(positions_df["Weight"].max())
        if max_weight > limits["max_single_name_weight"]:
            top = positions_df.loc[positions_df["Weight"].idxmax()]
            breaches.append({
                "limit": "max_single_name_weight",
                "message": f"{top.get('Symbol', '?')} is {max_weight:.1%} of the book, "
                           f"above the {limits['max_single_name_weight']:.1%} limit.",
            })

        if "Asset Class" in positions_df.columns:
            by_class = positions_df.groupby("Asset Class")["Weight"].sum()
            for asset_class in ("crypto", "option", "forex", "real_world_asset"):
                limit_key = f"max_asset_class_weight_{asset_class}"
                if limit_key in limits and asset_class in by_class.index:
                    weight = float(by_class[asset_class])
                    if weight > limits[limit_key]:
                        breaches.append({
                            "limit": limit_key,
                            "message": f"{asset_class.title()} is {weight:.1%} of the book, "
                                       f"above the {limits[limit_key]:.1%} limit.",
                        })

    if equity > 0 and var_95 is not None:
        var_pct = var_95 / equity
        if var_pct > limits["max_var_95_pct_of_equity"]:
            breaches.append({
                "limit": "max_var_95_pct_of_equity",
                "message": f"1-day 95% VaR is {var_pct:.1%} of equity, "
                           f"above the {limits['max_var_95_pct_of_equity']:.1%} limit.",
            })

    if current_drawdown is not None and current_drawdown <= limits["max_drawdown_halt"]:
        breaches.append({
            "limit": "max_drawdown_halt",
            "message": f"Current drawdown {current_drawdown:.1%} has breached the "
                       f"{limits['max_drawdown_halt']:.1%} halt level.",
        })

    return breaches
