"""
Test script for Options Flow module.
Run from C:\StockApp: python test_options_v2.py
"""
import sys
import time
sys.path.insert(0, ".")   # run from C:\StockApp

print("Testing Options Flow module...\n")

# Test 1: Options chain with retry
print("=== TEST 1: Options Chain (Yahoo Finance) ===")
try:
    from modules.options_flow.flow_service import get_options_summary
    # Wait a moment before calling to avoid rate limit
    print("Waiting 3 seconds before Yahoo Finance call...")
    time.sleep(3)
    s = get_options_summary("SPY")  # SPY is less likely to be rate limited
    if "error" in s:
        print("ERROR:", s["error"])
        print("-> If rate limited, wait 30 seconds and try again")
    else:
        print("Spot:              ", s.get("spot"))
        print("P/C Ratio (Vol):   ", s.get("pc_vol"))
        print("P/C Ratio (OI):    ", s.get("pc_oi"))
        print("P/C Sentiment:     ", s.get("pc_sentiment"))
        print("Max Pain:          ", s.get("max_pain"))
        print("IV Rank:           ", s.get("iv_rank"), "%")
        print("Call Volume:       ", s.get("call_volume"))
        print("Put Volume:        ", s.get("put_volume"))
        n = len(s.get("unusual_contracts", []))
        print("Unusual contracts: ", n)
        for u in s.get("unusual_contracts", [])[:3]:
            print(f"  {u['type']:4} ${u['strike']:7.0f}  "
                  f"exp={u['expiry']}  "
                  f"vol={u['volume']:6,}  oi={u['open_interest']:6,}  "
                  f"ratio={u['vol_oi_ratio']:.1f}x  {u['premium_fmt']}")
except Exception as e:
    print("EXCEPTION:", e)

print()

# Test 2: FINRA Dark Pool / Proxy
print("=== TEST 2: Dark Pool (FINRA / Proxy) ===")
try:
    from modules.options_flow.flow_service import get_finra_dark_pool
    d = get_finra_dark_pool("SPY")
    if "error" in d:
        print("ERROR:", d["error"])
    else:
        source = d.get("source", "unknown")
        print("Source:            ", source)
        print("Signal:            ", d.get("signal"))
        if source == "proxy":
            print("Inst Score:        ", d.get("inst_score"))
            print("P/C OI:            ", d.get("pc_oi"))
            print("IV Rank:           ", d.get("iv_rank"))
            print("Note:              ", d.get("data_note", "")[:80])
        else:
            print("Dark Pool %:       ", d.get("dark_pct"))
            print("Z-Score:           ", d.get("z_score"))
            print("Weeks of data:     ", len(d.get("weekly_history", [])))
except Exception as e:
    print("EXCEPTION:", e)

print()

# Test 3: Insider transactions
print("=== TEST 3: Insider Transactions (Finnhub) ===")
try:
    from modules.options_flow.flow_service import get_insider_transactions
    ins = get_insider_transactions("NVDA")
    if not ins:
        print("No insider data (check FINNHUB_API_KEY in secrets)")
    else:
        print(f"Found {len(ins)} transactions")
        for i in ins[:3]:
            icon = "BUY" if i["is_buy"] else "SELL"
            print(f"  {icon:4}  {i['name'][:25]:25}  "
                  f"{i['shares']:8,} shares  ${i['price']:7.2f}  {i['date']}")
except Exception as e:
    print("EXCEPTION:", e)

print("\nDone.")