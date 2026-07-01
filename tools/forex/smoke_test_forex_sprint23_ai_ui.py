
from importlib import import_module
mods = [
    "modules.forex.ui.forex_ai_cards",
    "modules.forex.ui.forex_ai_charts",
    "modules.forex.ui.forex_ai_workspace",
    "modules.forex.forex_ai_dashboard",
]
for m in mods:
    import_module(m)
    print("PASS", m)
from modules.forex.ui.forex_ai_workspace import render_forex_ai_workspace
payload = render_forex_ai_workspace(payload={"status": "READY"})
assert isinstance(payload, dict)
print("PASSED: Sprint 23 AI & Quant UI.")
