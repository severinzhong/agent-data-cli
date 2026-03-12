from __future__ import annotations

from cli.formatters import print_subscriptions
from cli.commands.specs import CommandArgSpec, CommandContext, CommandNodeSpec


def _run_sub_add(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    source = ctx.registry.build(args.source)
    source.subscribe(args.channel, display_name=args.name)
    print_subscriptions(ctx.store.list_subscriptions(args.source))
    return 0


def _run_sub_remove(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    source = ctx.registry.build(args.source)
    source.unsubscribe(args.channel)
    print_subscriptions(ctx.store.list_subscriptions(args.source))
    return 0


def _run_sub_list(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    print_subscriptions(ctx.store.list_subscriptions(args.source))
    return 0


SUB_COMMAND = CommandNodeSpec(
    name="sub",
    summary="管理本地订阅。",
    command_line="sub ...",
    child_dest="sub_command",
    children=(
        CommandNodeSpec(
            name="add",
            summary="添加订阅。",
            command_line="sub add --source <source> --channel <channel> [--name <name>]",
            arg_specs=(
                CommandArgSpec(names=("--source",), value_name="source", required=True),
                CommandArgSpec(names=("--channel",), value_name="channel", required=True),
                CommandArgSpec(names=("--name",), value_name="name"),
            ),
            run=_run_sub_add,
        ),
        CommandNodeSpec(
            name="remove",
            summary="删除订阅。",
            command_line="sub remove --source <source> --channel <channel>",
            arg_specs=(
                CommandArgSpec(names=("--source",), value_name="source", required=True),
                CommandArgSpec(names=("--channel",), value_name="channel", required=True),
            ),
            run=_run_sub_remove,
        ),
        CommandNodeSpec(
            name="list",
            summary="列出订阅。",
            command_line="sub list [--source <source>]",
            arg_specs=(CommandArgSpec(names=("--source",), value_name="source"),),
            run=_run_sub_list,
        ),
    ),
)
