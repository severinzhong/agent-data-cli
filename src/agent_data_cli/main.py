from __future__ import annotations

import sys

from agent_data_cli.cli.commands import CommandContext, build_parser, dispatch_command, parse_command_argv
from agent_data_cli.cli.help import print_help_doc
from agent_data_cli.init_service import initialize_runtime
from agent_data_cli.runtime_paths import is_initialized, resolve_runtime_paths


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args, extras = parse_command_argv(parser, argv)
    paths = _resolve_init_paths(args) if args.command == "init" else resolve_runtime_paths()

    if args.command == "init":
        initialize_runtime(paths, force=getattr(args, "force", False))
        print(f"initialized: {paths.home}")
        return 0

    if not is_initialized(paths):
        if args.command == "help" and not getattr(args, "topic", None):
            from agent_data_cli.cli.commands import build_global_help_doc

            print_help_doc(build_global_help_doc())
            return 0
        raise RuntimeError("adc 尚未初始化，请先运行 `adc init`")

    from agent_data_cli.cli import main as cli_main

    original_db_path = cli_main.DEFAULT_DB_PATH
    try:
        cli_main.DEFAULT_DB_PATH = str(paths.db_path)
        return cli_main.main(argv)
    finally:
        cli_main.DEFAULT_DB_PATH = original_db_path


def console_main() -> None:
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


def _resolve_init_paths(args) -> object:
    if getattr(args, "defaults", False) or getattr(args, "home", None) or getattr(args, "source_workspace", None):
        return resolve_runtime_paths(
            home_override=getattr(args, "home", None),
            source_workspace_override=getattr(args, "source_workspace", None),
        )

    initial = resolve_runtime_paths()
    home_input = input(f"ADC home [{initial.home}]: ").strip()
    resolved_home = home_input or str(initial.home)
    source_default = resolve_runtime_paths(home_override=resolved_home).source_workspace
    source_input = input(f"Source workspace [{source_default}]: ").strip()
    resolved_source_workspace = source_input or str(source_default)
    return resolve_runtime_paths(
        home_override=resolved_home,
        source_workspace_override=resolved_source_workspace,
    )

__all__ = ["console_main", "main"]
