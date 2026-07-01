
from importlib import import_module
mods=[
"modules.forex.forex_phase19_validation",
"modules.forex.forex_phase20_validation",
"modules.forex.forex_master_validation",
]
for m in mods:
    import_module(m)
print("Master validation imports passed.")
