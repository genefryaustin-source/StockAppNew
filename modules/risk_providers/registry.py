"""
modules/risk_providers/registry.py

Registry of connectable external risk-analytics vendors, mirroring
modules.portfolio.brokers.factory.BROKER_REGISTRY. Adding a new vendor
means: build a RiskProviderBase subclass in this package, register its
credentials in modules.admin.tenant_api_keys.KNOWN_PROVIDERS, and add one
line here.
"""

from __future__ import annotations

from modules.risk_providers.portfolioscience_provider import PortfolioScienceRiskProvider
from modules.risk_providers.factset_provider import FactSetRiskProvider
from modules.risk_providers.custom_provider import CustomRiskProvider

RISK_PROVIDER_REGISTRY = {
    "portfolioscience": PortfolioScienceRiskProvider,
    "factset": FactSetRiskProvider,
    "custom": CustomRiskProvider,
}

RISK_PROVIDER_INFO = {
    "portfolioscience": (
        "PortfolioScience RiskAPI",
        "Hosted multi-model VaR, stress testing, and valuation service.",
    ),
    "factset": (
        "FactSet Open:Risk API",
        "Holdings-based portfolio risk analytics (VaR, sensitivities, factor exposures).",
    ),
    "custom": (
        "Custom Risk Provider",
        "Point at any REST risk API with a configurable field mapping.",
    ),
}


def available_risk_providers() -> list[str]:
    return list(RISK_PROVIDER_REGISTRY.keys())


def get_risk_provider(name: str, tenant_id: str = None, config: dict = None):
    cls = RISK_PROVIDER_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown risk provider: {name!r}. Available: {', '.join(available_risk_providers())}")
    if name == "custom":
        return cls(tenant_id=tenant_id, config=config)
    return cls(tenant_id=tenant_id)
