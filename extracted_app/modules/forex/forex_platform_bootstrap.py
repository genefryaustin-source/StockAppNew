"""
modules/forex/forex_platform_bootstrap.py

17 files across this package (forex_api, forex_cli, forex_installer,
forex_quickstart, forex_sdk, forex_module_loader, etc.) import
`bootstrap_forex_platform` from a module named `forex_platform_bootstrap`
that never existed - the actual implementation lives in forex_bootstrap.py
under the same function name. This shim re-exports it under the name those
17 files expect, rather than editing every one of them individually.
"""

from __future__ import annotations

from modules.forex.forex_bootstrap import (
    bootstrap_forex_platform,
    shutdown_forex_platform,
    reload_forex_platform,
    platform_status,
    bootstrap_forex_runtime,
    shutdown_forex_runtime,
    forex_runtime_status,
    get_forex_bootstrap,
    ForexBootstrap,
)

__all__ = [
    "bootstrap_forex_platform",
    "shutdown_forex_platform",
    "reload_forex_platform",
    "platform_status",
    "bootstrap_forex_runtime",
    "shutdown_forex_runtime",
    "forex_runtime_status",
    "get_forex_bootstrap",
    "ForexBootstrap",
]
