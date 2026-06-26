# Forex Terminal Phase 10 — Deployment Runbook

## Install Order
1. forex_portfolio_engine_terminal_*.zip
2. forex_terminal_dashboard_phase2_*.zip
3. forex_terminal_phase3_execution_*.zip
4. forex_terminal_phase4_validation_*.zip
5. forex_terminal_phase5_workstation_*.zip
6. forex_terminal_phase6_bloomberg_*.zip
7. forex_terminal_phase7_dashboard_ui_*.zip
8. forex_phase9_hardened_validation_*.zip

## Admin Validation Center Integration
```python
from ui.admin.forex_terminal_validation_center import render_forex_terminal_validation_center
render_forex_terminal_validation_center(db=db)
```

## First Test Sequence
1. Restart Streamlit.
2. Open Forex terminal.
3. Open Admin > Forex Terminal Validation Center.
4. Run validation without paper order.
5. Run validation with paper order.
6. Confirm positions, orders, margin, and P/L update.
7. Open Institutional Workstation.
8. Test AI candidate dry run.
9. Test autonomous dry run.

## Rollback
Run `tools/forex/rollback_forex_terminal.ps1 -BackupPath <backup_folder>`.
