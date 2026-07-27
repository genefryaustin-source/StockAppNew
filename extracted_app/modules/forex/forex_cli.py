"""
modules/forex/forex_cli.py

Command-line interface for the Forex SDK.
"""

from __future__ import annotations
import argparse
import json

from modules.forex.forex_sdk import get_forex_sdk


def build_parser():
    p=argparse.ArgumentParser(prog="forex")
    sub=p.add_subparsers(dest="command")

    sub.add_parser("health")
    sub.add_parser("status")
    sub.add_parser("validate")

    q=sub.add_parser("quote")
    q.add_argument("pair")

    o=sub.add_parser("buy")
    o.add_argument("pair")
    o.add_argument("--units",type=float,default=10000)

    return p


def main(argv=None):
    args=build_parser().parse_args(argv)
    sdk=get_forex_sdk()

    if args.command=="health":
        result=sdk.health()
    elif args.command=="status":
        result=sdk.status()
    elif args.command=="validate":
        result=sdk.validate()
    elif args.command=="quote":
        result=sdk.quotes(args.pair)
    elif args.command=="buy":
        result=sdk.submit_order(
            pair=args.pair,
            side="BUY",
            units=args.units,
            order_type="MARKET",
        )
    else:
        result={"status":"No command specified"}

    print(json.dumps(result,indent=2,default=str))


if __name__=="__main__":
    main()
