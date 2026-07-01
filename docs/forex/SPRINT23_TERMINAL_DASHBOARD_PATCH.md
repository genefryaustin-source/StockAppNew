
# Sprint 23 Terminal Dashboard Wiring

Replace `_render_ai_quant_platform` in `modules/forex/forex_terminal_dashboard.py` with:

```python
def _render_ai_quant_platform(data, db=None):
    from modules.forex.ui.forex_ai_workspace import render_forex_ai_workspace

    try:
        from modules.forex.forex_institutional_command_center_v2 import (
            get_forex_institutional_command_center_v2,
        )
        payload = get_forex_institutional_command_center_v2(
            db=db
        ).dashboard(snapshot=data.get("raw_snapshot") or data)
    except Exception as exc:
        payload = {
            "status": "WARNING",
            "error": str(exc),
            "snapshot": data.get("raw_snapshot") or data,
        }

    return render_forex_ai_workspace(
        payload=payload,
        db=db,
        snapshot=data.get("raw_snapshot") or data,
    )
```
