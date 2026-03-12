from __future__ import annotations

import argparse

from cli.formatters import print_subscriptions
from cli.commands.specs import CommandContext, CommandNodeSpec


def _add_sub_add_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", required=True)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--name")


def _add_sub_remove_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", required=True)
    parser.add_argument("--channel", required=True)


def _add_sub_list_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source")


def _run_sub_add(args: argparse.Namespace, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    source = ctx.registry.build(args.source)
    source.subscribe(args.channel, display_name=args.name)
    print_subscriptions(ctx.store.list_subscriptions(args.source))
    return 0


def _run_sub_remove(args: argparse.Namespace, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    source = ctx.registry.build(args.source)
    source.unsubscribe(args.channel)
    print_subscriptions(ctx.store.list_subscriptions(args.source))
    return 0


def _run_sub_list(args: argparse.Namespace, extras: list[str], ctx: CommandContext) -> int:
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
            configure_parser=_add_sub_add_args,
            run=_run_sub_add,
        ),
        CommandNodeSpec(
            name="remove",
            summary="删除订阅。",
            command_line="sub remove --source <source> --channel <channel>",
            configure_parser=_add_sub_remove_args,
            run=_run_sub_remove,
        ),
        CommandNodeSpec(
            name="list",
            summary="列出订阅。",
            command_line="sub list [--source <source>]",
            configure_parser=_add_sub_list_args,
            run=_run_sub_list,
        ),
    ),
)
