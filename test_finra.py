"""
Test FINRA per-ticker filter — run: python test_finra_v4.py
"""
import sys, pathlib, requests, json
import toml

secrets = toml.load(pathlib.Path(".streamlit/secrets.toml"))
raw = secrets.get("FINRA_API_KEY", "")
client_id, client_secret = raw.split(":", 1)

r = requests.post(
    "https://ews.fip.finra.org/fip/rest/ews/oauth2/access_token",
    params={"grant_type": "client_credentials"},
    auth=(client_id.strip(), client_secret.strip()),
    timeout=12,
)
token = r.json().get("access_token", "")
headers = {"Authorization": f"Bearer {token}", "Accept": "application/json",
           "Content-Type": "application/json"}

BASE = "https://api.finra.org/data/group/otcMarket/name/weeklySummary"

# The key insight: FINRA's POST body uses a DIFFERENT filter structure
# than we tried before. Try each variant with NVDA

tests = [
    # Try offset-based pagination to find NVDA
    ("offset=0", "GET", None, {"limit": 5, "offset": 0}),
    ("offset=100", "GET", None, {"limit": 5, "offset": 100}),

    # Try POST with 'fields' to filter summaryTypeCode
    ("POST fields filter", "POST", {
        "fields": ["issueSymbolIdentifier", "weekStartDate", "totalWeeklyShareQuantity", "summaryTypeCode"],
        "compareFilters": [
            {"fieldName": "summaryTypeCode", "compareType": "EQUAL", "fieldValue": "ATS_W_SMBL_FIRM"},
            {"fieldName": "issueSymbolIdentifier", "compareType": "EQUAL", "fieldValue": "NVDA"},
        ],
        "limit": 5,
    }, None),

    # Try with 'andFilters'
    ("POST andFilters", "POST", {
        "andFilters": [
            {"fieldName": "issueSymbolIdentifier", "compareType": "EQUAL", "fieldValue": "NVDA"},
            {"fieldName": "summaryTypeCode", "compareType": "EQUAL", "fieldValue": "ATS_W_SMBL_FIRM"},
        ],
        "limit": 5,
    }, None),

    # Try the ATS Symbol dataset specifically
    ("weeklySummary/AtsSymbol", "GET", None, {"issueSymbolIdentifier": "NVDA", "limit": 5}),
]

for name, method, body, params in tests:
    url = BASE
    if "AtsSymbol" in name:
        url = "https://api.finra.org/data/group/otcMarket/name/weeklySummary"

    print(f"\n--- {name} ---")
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, params=params, timeout=10)
        else:
            resp = requests.post(url, headers={**headers}, json=body, timeout=10)

        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            rows = resp.json()
            ticker_rows = [r for r in rows if str(r.get("issueSymbolIdentifier") or "") == "NVDA"]
            print(f"Total rows: {len(rows)}, NVDA rows: {len(ticker_rows)}")
            for row in rows[:2]:
                print(f"  sym={row.get('issueSymbolIdentifier')} type={row.get('summaryTypeCode')} week={row.get('weekStartDate')} vol={row.get('totalWeeklyShareQuantity')}")
            if ticker_rows:
                print(f"  ✅ FOUND NVDA ROWS!")
                break
        else:
            print(f"  {resp.text[:200]}")
    except Exception as e:
        print(f"  ERROR: {e}")

# Also check total row count and available summaryTypeCode values
print("\n--- Checking summaryTypeCode distribution in first 200 rows ---")
resp = requests.get(BASE, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                    params={"limit": 200}, timeout=15)
if resp.status_code == 200:
    rows = resp.json()
    from collections import Counter
    types = Counter(r.get("summaryTypeCode") for r in rows)
    syms  = [r.get("issueSymbolIdentifier") for r in rows if r.get("issueSymbolIdentifier")]
    print(f"Total rows: {len(rows)}")
    print(f"summaryTypeCode counts: {dict(types)}")
    print(f"Sample symbols: {syms[:20]}")
    print(f"NVDA in rows: {'NVDA' in syms}")