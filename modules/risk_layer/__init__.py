"""
modules/risk_layer

The app's cross-asset Internal Risk Layer -- a single place that reads
positions from the Portfolio module (across whichever brokers are
connected: Alpaca, Tradier, IBKR, or Paper) and produces a unified risk
picture by leaning on modules that already exist elsewhere in the app:

  - modules.portfolio.*            positions, equity curve, existing
                                    RiskAnalyticsService (VaR/ES/concentration)
  - modules.market.regime_engine   shared trend/vol/breadth classification
  - modules.alerts.scanner_engine  the AI Scanner's own condition evaluator,
                                    run against every held position
  - modules.valuation               per-equity fair-value read
  - modules.options.*               Greeks exposure (best-effort, options
                                    positions only)
  - modules.risk.autonomous_defense_engine   survival score + defense
                                    directive generation

It is asset-class extensible by design: every position is tagged with an
asset_class ("equity", "option", "crypto", "forex", or "real_world_asset"
for the future), and every metric in engine.py either applies uniformly
across classes (exposure, concentration, VaR) or is computed per-class
(options Greeks, equity valuation) and merged into one RiskSnapshot.
"""
