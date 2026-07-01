# Phase 20 Dashboard Patch

Add workspace:

```python
"Autonomous Trading Platform"
```

Route:

```python
elif workspace == "Autonomous Trading Platform":
    from modules.forex.forex_autonomous_platform_dashboard import render_forex_autonomous_trading_platform
    render_forex_autonomous_trading_platform(data, db=self.db)
```
