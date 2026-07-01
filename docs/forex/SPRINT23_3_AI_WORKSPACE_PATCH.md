
# Sprint 23.3 AI Workspace Patch

In `modules/forex/ui/forex_ai_workspace.py` replace:

```python
with tabs[2]:
    _render_factor_models(payload)
```

with:

```python
with tabs[2]:
    from modules.forex.ui.forex_factor_models_workspace import render_forex_factor_models_workspace
    render_forex_factor_models_workspace(payload, db=db)
```
