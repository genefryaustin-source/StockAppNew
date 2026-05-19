import shutil
import os

BASE = r"C:\StockApp"
STABLE = os.path.join(BASE, "_stable")

MAP = {
    "screener_v1": "modules/screener",
    "analytics_v1": "modules/analytics",
    "market_data_v1": "modules/market_data",
}

for k, v in MAP.items():
    src = os.path.join(STABLE, k)
    dst = os.path.join(BASE, v)

    print(f"Restoring {k} → {v}")

    if os.path.exists(dst):
        shutil.rmtree(dst)

    shutil.copytree(src, dst)

print("✅ RESTORE COMPLETE")