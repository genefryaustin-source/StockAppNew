"""
Diagnostic v2 — run from C:\StockApp:  python test_poly_key.py
"""
import os, sys, pathlib
sys.path.insert(0, ".")

import toml

# Read secrets.toml
secrets = {}
for p in [pathlib.Path(".streamlit/secrets.toml")]:
    if p.exists():
        secrets = toml.load(p)
        break

key      = secrets.get("MASSIVE_API_KEY") or secrets.get("POLYGON_API_KEY", "")
base_url = secrets.get("BASE_URL", "https://api.polygon.io").rstrip("/")

print(f"Key:      {key[:8]}..." if key else "Key: NOT FOUND")
print(f"Base URL: {base_url}")
print()

if not key:
    print("ERROR: No API key found")
    sys.exit(1)

import requests

# Test 1: price
print(f"Testing price: GET {base_url}/v2/last/trade/NVDA")
r = requests.get(f"{base_url}/v2/last/trade/NVDA",
                 params={"apiKey": key}, timeout=8)
print(f"  Status: {r.status_code}")
if r.status_code == 200:
    price = r.json().get("results", {}).get("p")
    print(f"  NVDA price: ${price}")
else:
    print(f"  Response: {r.text[:200]}")

print()

# Test 2: options snapshot
print(f"Testing options: GET {base_url}/v3/snapshot/options/NVDA")
r2 = requests.get(f"{base_url}/v3/snapshot/options/NVDA",
                  params={"apiKey": key, "limit": 5}, timeout=10)
print(f"  Status: {r2.status_code}")
if r2.status_code == 200:
    results = r2.json().get("results", [])
    print(f"  Options count: {len(results)}")
    if results:
        d = results[0].get("details", {})
        print(f"  First: {d.get('contract_type')} ${d.get('strike_price')} exp={d.get('expiration_date')}")
else:
    print(f"  Response: {r2.text[:300]}")

print()

# Test 3: try the full flow_service
print("Testing flow_service.get_options_summary('NVDA')...")
try:
    from modules.options_flow.flow_service import get_options_summary
    s = get_options_summary("NVDA")
    if "error" in s:
        print(f"  ERROR: {s['error']}")
    else:
        print(f"  Spot: ${s.get('spot')}")
        print(f"  P/C ratio: {s.get('pc_vol')}")
        print(f"  Max pain: ${s.get('max_pain')}")
        print(f"  IV rank: {s.get('iv_rank')}%")
        print(f"  Unusual contracts: {len(s.get('unusual_contracts',[]))}")
except Exception as e:
    print(f"  EXCEPTION: {e}")