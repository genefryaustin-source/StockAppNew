# Forex Phase 13 — Final Production Test + Admin Integration Polish

## Purpose

Phase 13 closes the Forex terminal build by adding:

- final smoke test
- production broker safety test
- admin production page
- final install order
- post-install checklist

---

## Final Install Order

Install in order:

1. `forex_portfolio_engine_terminal_*.zip`
2. `forex_terminal_dashboard_phase2_*.zip`
3. `forex_terminal_phase3_execution_*.zip`
4. `forex_terminal_phase4_validation_*.zip`
5. `forex_terminal_phase5_workstation_*.zip`
6. `forex_terminal_phase6_bloomberg_*.zip`
7. `forex_terminal_phase7_dashboard_ui_*.zip`
8. `forex_phase9_hardened_validation_*.zip`
9. `forex_phase10_runbook_*.zip`
10. `forex_phase11_production_*.zip`
11. `forex_phase12_production_wiring_*.zip`
12. `forex_phase13_final_test_admin_*.zip`

---

## Admin Navigation Integration

Add this to your Admin Panel:

```python
from ui.admin.forex_production_admin import render_forex_production_admin

render_forex_production_admin(db=db)
```

This gives you tabs for:

- Validation Center
- Production Health
- Broker Health
- Broker Safety

---

## Final Smoke Test

Run:

```powershell
python tools\forex\smoke_test_forex_terminal_final.py
```

Expected:

```text
PASSED: all imports succeeded.
```

---

## Broker Safety Test

Run:

```powershell
python tools\forex\broker_safety_test.py
```

Expected:

```text
PASSED: live broker safety lockout verified.
```

The live adapters must reject orders unless explicitly configured.

---

## Post-Install Verification

1. Start Streamlit.
2. Open the app.
3. Open the Forex terminal.
4. Confirm no import errors.
5. Open Institutional Workstation.
6. Confirm Watchlist loads.
7. Confirm Order Book loads.
8. Confirm AI Command Center loads.
9. Confirm Execution Blotter loads.
10. Open Admin > Forex Production Admin.
11. Run Validation Center without paper order.
12. Run Broker Safety Test.
13. Run validation with 0.01 lot paper order.
14. Confirm:
    - order validation passes
    - paper execution returns FILLED or OPEN
    - snapshot updates
    - positions/orders/margin update
15. Confirm live broker routes reject by default.

---

## Production Safety Rule

Live broker execution remains disabled until each adapter config explicitly has:

```python
{
    "enabled": True,
    "live_enabled": True
}
```

Until then, OANDA, MT5, IBKR, and DXtrade adapters must reject orders.
