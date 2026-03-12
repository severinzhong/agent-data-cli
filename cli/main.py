from __future__ import annotations

import sys

from cli.commands import CommandContext, build_parser, dispatch_command, parse_command_argv
from core.registry import build_default_registry
from store.db import Store
from utils.time import parse_since_expr


DEFAULT_DB_PATH = "agent-data-cli.db"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args, extras = parse_command_argv(parser, argv)
    store = Store(DEFAULT_DB_PATH)
    registry = build_default_registry(store)
    store.init_schema(storage_specs=registry.list_storage_specs())
    return dispatch_command(args, extras, CommandContext(registry=registry, store=store))


def console_main() -> None:
    raise SystemExit(main())
