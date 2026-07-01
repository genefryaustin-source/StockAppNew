
from importlib import import_module
mods=["modules.forex.ui.forex_quant_statistics","modules.forex.ui.forex_quant_visualizations","modules.forex.ui.forex_quant_research_workspace"]
for m in mods:
    import_module(m)
    print("PASS",m)
from modules.forex.ui.forex_quant_research_workspace import render_forex_quant_research_workspace
payload=render_forex_quant_research_workspace({"status":"READY"})
assert isinstance(payload,dict)
print("PASSED: Sprint 23.2 Quant Research UI.")
