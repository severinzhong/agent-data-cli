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
    summary="Manage local subscriptions.",
    child_dest="sub_command",
    children=(
        CommandNodeSpec(
            name="add",
            summary="Add a subscription.",
            arg_specs=(
                CommandArgSpec(names=("--source",), value_name="source", required=True),
                CommandArgSpec(names=("--channel",), value_name="channel", required=True),
                CommandArgSpec(names=("--name",), value_name="name"),
            ),
            run=_run_sub_add,
        ),
        CommandNodeSpec(
            name="remove",
            summary="Remove a subscription.",
            arg_specs=(
                CommandArgSpec(names=("--source",), value_name="source", required=True),
                CommandArgSpec(names=("--channel",), value_name="channel", required=True),
            ),
            run=_run_sub_remove,
        ),
        CommandNodeSpec(
            name="list",
            summary="List subscriptions.",
            arg_specs=(CommandArgSpec(names=("--source",), value_name="source"),),
            run=_run_sub_list,
        ),
    ),
)
