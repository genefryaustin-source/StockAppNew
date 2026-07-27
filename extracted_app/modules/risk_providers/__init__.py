"""
modules/risk_providers

External risk-analytics vendor integrations for the Internal Risk Layer
(modules/risk_layer). Same architecture as modules/portfolio/brokers:
a common interface (base.py), one adapter per vendor, a registry, and
per-tenant enable/disable + credentials managed the same way brokers are
-- through Admin > API Keys and a dedicated Admin > Risk Providers tab.

These vendors are supplemental cross-checks on the Risk Layer's own
internal risk math (RiskAnalyticsService), not a replacement for it.
"""
