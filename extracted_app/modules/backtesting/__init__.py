"""
modules/backtesting

Fast, vectorized strategy backtesting via vectorbt
(https://github.com/polakowo/vectorbt). License note: vectorbt's
open-source edition is "fair-code" (Apache 2.0 + Commons Clause) -- free
to use, including commercially, as long as you're not selling a product
that IS PRIMARILY vectorbt itself. Using it as one feature inside this
platform is the normal case that license is meant to allow; it's not a
plain MIT/BSD license though, so worth knowing if this ever gets vendored
or resold as a standalone tool.

vectorbt_engine.py exposes two entry points:
  - backtest_signal_suite_strategy(): backtests the exact same buy/sell
    logic already drawn on charts app-wide (modules.indicators.signal_suite),
    so "does this signal actually make money historically" is one call away.
  - backtest_ma_crossover(): a simple, dependency-free baseline strategy
    for comparison.

Both degrade gracefully (return {"available": False, "reason": ...}) if
vectorbt isn't installed or there isn't enough price history.
"""
