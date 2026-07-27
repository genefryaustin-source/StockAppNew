"""
modules/forex/forex_api_documentation.py

API documentation registry for the Forex SDK and REST API.
"""

from __future__ import annotations
from copy import deepcopy

_DOCS={
    "service":"Forex API Documentation",
    "version":"1.0.0",
    "sdk":"ForexSDK",
    "rest":"ForexRestAPI",
    "openapi":"Forex OpenAPI 3.1",
    "sections":{
        "Platform":[
            "initialize","shutdown","reload","status","health"
        ],
        "Trading":[
            "submit_order","cancel_order","modify_order","close_position"
        ],
        "Portfolio":[
            "portfolio_summary","positions","orders","trade_history"
        ],
        "Market Data":[
            "quotes","currency_strength","sentiment",
            "macro_regime","central_bank_events"
        ],
        "Analytics":[
            "strategy_lab","alpha_model",
            "institutional_flow","performance"
        ],
        "Administration":[
            "validate","benchmark","stress_test",
            "production_readiness"
        ],
        "Enterprise":[
            "enterprise_snapshot",
            "deployment_status",
            "platform_metadata"
        ]
    }
}

def get_forex_api_documentation():
    return deepcopy(_DOCS)

def export_markdown():
    lines=[f"# {_DOCS['service']}","","## Sections"]
    for sec,items in _DOCS["sections"].items():
        lines.append(f"### {sec}")
        for i in items:
            lines.append(f"- `{i}`")
        lines.append("")
    return "\n".join(lines)

def api_summary():
    return {
        "service":_DOCS["service"],
        "sections":len(_DOCS["sections"]),
        "operations":sum(len(v) for v in _DOCS["sections"].values()),
        "version":_DOCS["version"],
    }
