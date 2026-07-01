
from importlib import import_module
mods = [
    "modules.forex.ui.forex_regime_summary",
    "modules.forex.ui.forex_regime_charts",
    "modules.forex.ui.forex_regime_cards",
    "modules.forex.ui.forex_regime_workspace",
]
for m in mods:
    import_module(m)
    print("PASS", m)
from modules.forex.ui.forex_regime_workspace import render_forex_regime_workspace
payload = render_forex_regime_workspace({"status": "READY", "regime": {"regime": "RISK_OFF", "confidence": 82}})
assert isinstance(payload, dict)
print("PASSED: Sprint 23.4 Regime Intelligence UI.")
