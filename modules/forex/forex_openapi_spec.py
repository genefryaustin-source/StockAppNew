"""
modules/forex/forex_openapi_spec.py

OpenAPI specification generator for the Forex REST API.
"""

from __future__ import annotations
from copy import deepcopy

_SPEC={
    "openapi":"3.1.0",
    "info":{
        "title":"StockApp Forex API",
        "version":"1.0.0",
        "description":"Enterprise Forex REST interface"
    },
    "servers":[{"url":"/api"}],
    "paths":{
        "/forex/status":{"get":{"operationId":"status"}},
        "/forex/health":{"get":{"operationId":"health"}},
        "/forex/quotes":{"get":{"operationId":"quotes"}},
        "/forex/orders":{"get":{"operationId":"orders"},"post":{"operationId":"submitOrder"}},
        "/forex/positions":{"get":{"operationId":"positions"}},
        "/forex/portfolio":{"get":{"operationId":"portfolio"}},
        "/forex/strategy-lab":{"get":{"operationId":"strategyLab"}},
        "/forex/validate":{"post":{"operationId":"validate"}},
        "/forex/production-readiness":{"post":{"operationId":"productionReadiness"}}
    },
    "components":{
        "securitySchemes":{
            "BearerAuth":{"type":"http","scheme":"bearer"}
        }
    }
}

def get_forex_openapi_spec():
    return deepcopy(_SPEC)

def export_openapi():
    return deepcopy(_SPEC)

def endpoint_count():
    count=0
    for v in _SPEC["paths"].values():
        count+=len(v)
    return count
