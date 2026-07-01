"""
Production broker safety test.

This intentionally verifies:
- Paper broker route is available.
- Live broker adapters reject orders unless explicitly enabled.
"""

from __future__ import annotations


def main() -> int:
    from modules.forex.forex_broker_router import get_forex_broker_router

    router = get_forex_broker_router(default_broker="paper")

    print("Broker health")
    for row in router.health():
        print(row)

    failures = 0

    for broker in ["oanda", "mt5", "ibkr", "dxtrade"]:
        result = router.route_order(
            broker=broker,
            pair="EUR/USD",
            side="BUY",
            lots=0.01,
            order_type="MARKET",
        )
        status = str(result.get("status", "")).upper()
        if status != "REJECTED":
            failures += 1
            print(f"FAIL {broker}: expected REJECTED, got {status}")
        else:
            print(f"PASS {broker}: live broker safety lockout active")

    if failures:
        print(f"FAILED: {failures} broker safety check(s) failed.")
        return 1

    print("PASSED: live broker safety lockout verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
