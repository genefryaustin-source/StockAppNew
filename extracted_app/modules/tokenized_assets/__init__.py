"""
modules/tokenized_assets

Tokenized real-world asset (RWA) trading -- tokenized Treasuries, private
credit, commodities, equities/ETFs, and real estate -- integrated as
genuine brokers (modules.portfolio.brokers.base.BrokerBase subclasses),
not a separate system. Positions land in the same PortfolioPosition table
as every other asset class, so they get full parity with equities:
Trading & Execution, portfolio analytics, and the Internal Risk Layer all
see tokenized assets automatically once a provider here is enabled and
connected.

Providers:
  - ondo_provider.OndoProvider          Ondo Finance / Global Markets
                                        (tokenized equities/ETFs/commodities,
                                        plus OUSG/USDY tokenized Treasuries)
  - securitize_provider.SecuritizeProvider   Securitize (institutional
                                        tokenized funds, e.g. BlackRock's
                                        BUIDL)
  - custom_provider.CustomTokenizedAssetProvider   any other venue via a
                                        configurable REST endpoint

Registered in modules.portfolio.brokers.factory.BROKER_REGISTRY, managed
from the existing Admin > Brokers and Admin > API Keys tabs -- no
separate tokenized-asset admin UI needed.
"""
