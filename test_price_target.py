"""
Test FMP new API endpoints (v3 stable ones) — run: python test_fmp_new.py
"""
import sys, pathlib, requests, json
sys.path.insert(0, ".")
import toml
secrets = toml.load(pathlib.Path(".streamlit/secrets.toml"))
fmp = secrets.get("FMP_API_KEY", "")
ticker = "DELL"

# FMP v3 endpoints that are NOT legacy
tests = [
    f"/api/v3/quote/{ticker}",
    f"/api/v3/company/profile/{ticker}",
    f"/api/v3/ratios-ttm/{ticker}",
    f"/api/v3/key-metrics/{ticker}",
    f"/api/v3/grade/{ticker}",
    f"/api/v3/historical-rating/{ticker}",
    f"/api/v3/analyst-estimates/{ticker}",
    f"/api/v3/discounted-cash-flow/{ticker}",
    f"/api/v3/advanced_dcf?symbol={ticker}",
    f"/api/v4/analyst-estimates?symbol={ticker}",
    f"/api/v4/price-target-rss-feed",
]

for path in tests:
    r = requests.get(
        f"https://financialmodelingprep.com{path}",
        params={"apikey": fmp, "limit": 1},
        timeout=8
    )
    if r.status_code == 200:
        d = r.json()
        if isinstance(d, list) and d:
            keys = list(d[0].keys())[:8]
            # Check for any price target field
            pt_fields = [k for k in d[0].keys() if "target" in k.lower() or "price" in k.lower()]
            print(f"✅ {path.split('?')[0].split('/')[-1]}: {r.status_code} — keys: {keys}")
            if pt_fields:
                print(f"   >>> TARGET FIELDS: {[(k, d[0][k]) for k in pt_fields[:5]]}")
        elif isinstance(d, dict):
            pt_fields = [k for k in d.keys() if "target" in k.lower()]
            print(f"✅ {path.split('?')[0].split('/')[-1]}: {r.status_code} — dict keys: {list(d.keys())[:8]}")
            if pt_fields:
                print(f"   >>> TARGET FIELDS: {[(k, d[k]) for k in pt_fields[:5]]}")
    else:
        print(f"❌ {path.split('?')[0].split('/')[-1]}: {r.status_code} — {r.text[:80]}")