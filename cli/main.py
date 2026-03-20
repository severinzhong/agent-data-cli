from __future__ import annotations

import sys

from cli.commands import CommandContext, build_parser, dispatch_command, parse_command_argv
from core.registry import build_default_registry
from store.db import Store
from utils.time import parse_since_expr


DEFAULT_DB_PATH = "agent-data-cli.db"
_DASHBOARD_SUBCOMMANDS = {"start", "status", "stop"}


def normalize_argv(argv: list[str]) -> list[str]:
    if not argv or argv[0] != "dashboard":
        return argv
    if len(argv) == 1:
        return ["dashboard", "start"]
    second = argv[1]
    if second in _DASHBOARD_SUBCOMMANDS:
        return argv
    if second.startswith("-"):
        return ["dashboard", "start", *argv[1:]]
    return argv


def main(argv: list[str] | None = None) -> int:
    argv = normalize_argv(list(sys.argv[1:] if argv is None else argv))
    parser = build_parser()
    args, extras = parse_command_argv(parser, argv)
    store = Store(DEFAULT_DB_PATH)
    store.init_schema()
    registry = build_default_registry(store)
    store.init_schema(storage_specs=registry.list_storage_specs())
    return dispatch_command(args, extras, CommandContext(registry=registry, store=store))


def console_main() -> None:
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
