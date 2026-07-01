
from importlib import import_module
mods = [
    "modules.forex.ui.forex_factor_summary",
    "modules.forex.ui.forex_factor_charts",
    "modules.forex.ui.forex_factor_cards",
    "modules.forex.ui.forex_factor_tables",
    "modules.forex.ui.forex_factor_models_workspace",
]
for m in mods:
    import_module(m)
    print("PASS", m)
from modules.forex.ui.forex_factor_models_workspace import render_forex_factor_models_workspace
payload = render_forex_factor_models_workspace({"status": "READY"})
assert isinstance(payload, dict)
print("PASSED: Sprint 23.3 Factor Models UI.")
