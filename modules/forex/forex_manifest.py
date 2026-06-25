"""
modules/forex/forex_manifest.py

Declarative manifest for the Forex subsystem.
"""
from __future__ import annotations
from copy import deepcopy

_MANIFEST={
    "module":"Forex",
    "display_name":"Foreign Exchange",
    "version":"1.0.0",
    "category":"Trading",
    "description":"Enterprise Forex trading and analytics platform.",
    "author":"StockApp",
    "license":"Proprietary",
    "enterprise":True,
    "enabled":True,
    "status":"READY",
    "services":18,
    "engines":14,
    "dashboards":20,
    "admin_pages":5,
    "validation_suites":6,
    "providers":8,
    "api_routes":12,
    "scheduled_jobs":9,
    "dependencies":{
        "python":["pandas","numpy","sqlalchemy","streamlit"],
        "tables":["forex_positions","forex_orders","forex_trade_journal"],
        "services":["platform_service","enterprise_platform","registry"],
        "providers":["Polygon","Finnhub","AlphaVantage","Yahoo"]
    },
    "ui":{
        "navigation":"Forex",
        "workspaces":["Trader","Institutional","Administration"],
        "dashboards":["Trading Desk","Terminal","Portfolio","Health","Validation"]
    },
    "validation":[
        "System Validation",
        "End-to-End Harness",
        "Performance Benchmarks",
        "Stress Tests",
        "Chaos Tests",
        "Disaster Recovery",
        "Production Readiness"
    ]
}

def get_forex_manifest():
    return deepcopy(_MANIFEST)

def validate_manifest():
    required=["module","version","services","engines","status"]
    missing=[k for k in required if k not in _MANIFEST]
    return {"valid":len(missing)==0,"missing":missing}

def export_manifest():
    return deepcopy(_MANIFEST)

def register_with_application(app_registry):
    app_registry["Forex"]=deepcopy(_MANIFEST)
    return True

def unregister_from_application(app_registry):
    app_registry.pop("Forex",None)
    return True
