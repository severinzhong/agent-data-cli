from __future__ import annotations

from cli.formatters import print_health, print_sources
from cli.commands.common import require_action
from cli.commands.specs import CommandArgSpec, CommandContext, CommandNodeSpec


def _run_source_list(args, extras: list[str], ctx: CommandContext) -> int:
    _ = args, extras
    print_sources(ctx.registry.list_descriptors())
    return 0


def _run_source_health(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    source = ctx.registry.build(args.source)
    require_action(ctx.registry, args.source, "source.health")
    health = source.health()
    ctx.store.save_health(health)
    print_health(health)
    return 0


SOURCE_COMMAND = CommandNodeSpec(
    name="source",
    summary="查看 source 列表和健康状态。",
    command_line="source ...",
    child_dest="source_command",
    children=(
        CommandNodeSpec(
            name="list",
            summary="列出已注册 source。",
            command_line="source list",
            run=_run_source_list,
        ),
        CommandNodeSpec(
            name="health",
            summary="检查某个 source 的健康状态。",
            command_line="source health <source>",
            arg_specs=(CommandArgSpec(names=("source",), value_name="source"),),
            run=_run_source_health,
        ),
    ),
)
