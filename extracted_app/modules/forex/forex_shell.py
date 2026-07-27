"""
modules/forex/forex_shell.py

Interactive command shell for the Forex SDK.
"""

from __future__ import annotations

import cmd
import json

from modules.forex.forex_sdk import get_forex_sdk


class ForexShell(cmd.Cmd):
    intro = "Forex SDK Shell. Type help or ? to list commands."
    prompt = "forex> "

    def __init__(self, db=None):
        super().__init__()
        self.sdk = get_forex_sdk(db=db)

    def _show(self, obj):
        print(json.dumps(obj, indent=2, default=str))

    def do_health(self, arg):
        self._show(self.sdk.health())

    def do_status(self, arg):
        self._show(self.sdk.status())

    def do_quote(self, arg):
        pair = arg.strip() or "EURUSD"
        self._show(self.sdk.quotes(pair))

    def do_buy(self, arg):
        pair = arg.strip() or "EURUSD"
        self._show(self.sdk.submit_order(
            pair=pair,
            side="BUY",
            units=10000,
            order_type="MARKET",
        ))

    def do_portfolio(self, arg):
        self._show(self.sdk.portfolio_summary())

    def do_validate(self, arg):
        self._show(self.sdk.validate())

    def do_snapshot(self, arg):
        self._show(self.sdk.enterprise_snapshot())

    def do_exit(self, arg):
        return True

    def do_quit(self, arg):
        return True


def main():
    ForexShell().cmdloop()


if __name__ == "__main__":
    main()
