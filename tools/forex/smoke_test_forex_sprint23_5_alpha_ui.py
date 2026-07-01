
from importlib import import_module
mods = [
    "modules.forex.ui.forex_alpha_summary",
    "modules.forex.ui.forex_alpha_charts",
    "modules.forex.ui.forex_alpha_cards",
    "modules.forex.ui.forex_alpha_research_workspace",
]
for m in mods:
    import_module(m)
    print("PASS", m)
from modules.forex.ui.forex_alpha_research_workspace import render_forex_alpha_research_workspace
payload = render_forex_alpha_research_workspace({"status": "READY"})
assert isinstance(payload, dict)
print("PASSED: Sprint 23.5 Alpha Research UI.")
