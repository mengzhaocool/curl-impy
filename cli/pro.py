"""Pro subcommands: list impersonate targets (fingerprint management disabled)."""

from __future__ import annotations

import sys

from curl_impy import impersonate_list


def add_pro_parser(subparsers) -> None:
    parser = subparsers.add_parser("pro", help="Pro features")
    sub = parser.add_subparsers(dest="pro_action")

    sub.add_parser("list", help="List available impersonate targets")


def run_pro(args) -> int:
    if args.pro_action == "list":
        targets = impersonate_list()
        for t in targets:
            print(t)
        return 0

    print(f"Unknown pro action: {args.pro_action}", file=sys.stderr)
    return 1
