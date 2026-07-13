"""Pro subcommands: list impersonate targets (fingerprint management disabled)."""

from __future__ import annotations

from curl_impy import impersonate_list


def add_pro_parsers(subparsers) -> None:
    parser = subparsers.add_parser("pro", help="Pro features")
    sub = parser.add_subparsers(dest="pro_action")
    sub.add_parser("list", help="List available impersonate targets")


def handle_pro_command(args) -> bool:
    if args.pro_action == "list":
        targets = impersonate_list()
        for t in targets:
            print(t)
        return True
    return False
