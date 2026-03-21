from __future__ import annotations

from agent_data_cli.cli.commands.specs import CommandArgSpec, CommandNodeSpec
from agent_data_cli.init_service import initialize_runtime
from agent_data_cli.runtime_paths import resolve_runtime_paths


def _run_init(args, extras: list[str], ctx) -> int:
    _ = extras, ctx
    paths = resolve_runtime_paths(
        home_override=args.home,
        source_workspace_override=args.source_workspace,
    )
    initialize_runtime(paths, force=args.force)
    print(f"initialized: {paths.home}")
    return 0


INIT_COMMAND = CommandNodeSpec(
    name="init",
    summary="Initialize adc home, database, workspace, and bootstrap assets.",
    arg_specs=(
        CommandArgSpec(names=("--defaults",), action="store_true"),
        CommandArgSpec(names=("--force",), action="store_true"),
        CommandArgSpec(names=("--home",), value_name="path"),
        CommandArgSpec(names=("--source-workspace",), value_name="path", dest="source_workspace"),
    ),
    run=_run_init,
)
