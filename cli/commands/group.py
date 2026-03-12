from __future__ import annotations

from cli.formatters import print_group_members, print_groups
from cli.commands.specs import CommandArgSpec, CommandContext, CommandNodeSpec


def _run_group_create(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    ctx.store.create_group(args.group)
    print_groups(ctx.store.list_groups())
    return 0


def _run_group_delete(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    ctx.store.delete_group(args.group)
    print_groups(ctx.store.list_groups())
    return 0


def _run_group_list(args, extras: list[str], ctx: CommandContext) -> int:
    _ = args, extras
    print_groups(ctx.store.list_groups())
    return 0


def _run_group_show(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    print_group_members(ctx.store.list_group_members(args.group))
    return 0


def _run_group_add_source(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    ctx.store.add_group_source(args.group, args.source)
    print_group_members(ctx.store.list_group_members(args.group))
    return 0


def _run_group_add_channel(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    ctx.store.add_group_channel(args.group, args.source, args.channel)
    print_group_members(ctx.store.list_group_members(args.group))
    return 0


def _run_group_remove_source(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    ctx.store.remove_group_source(args.group, args.source)
    print_group_members(ctx.store.list_group_members(args.group))
    return 0


def _run_group_remove_channel(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    ctx.store.remove_group_channel(args.group, args.source, args.channel)
    print_group_members(ctx.store.list_group_members(args.group))
    return 0


GROUP_COMMAND = CommandNodeSpec(
    name="group",
    summary="管理本地分组。",
    child_dest="group_command",
    children=(
        CommandNodeSpec(
            name="create",
            summary="创建分组。",
            arg_specs=(CommandArgSpec(names=("group",), value_name="group"),),
            run=_run_group_create,
        ),
        CommandNodeSpec(
            name="delete",
            summary="删除分组。",
            arg_specs=(CommandArgSpec(names=("group",), value_name="group"),),
            run=_run_group_delete,
        ),
        CommandNodeSpec(
            name="list",
            summary="列出分组。",
            run=_run_group_list,
        ),
        CommandNodeSpec(
            name="show",
            summary="查看分组成员。",
            arg_specs=(CommandArgSpec(names=("group",), value_name="group"),),
            run=_run_group_show,
        ),
        CommandNodeSpec(
            name="add-source",
            summary="向分组添加 source。",
            arg_specs=(
                CommandArgSpec(names=("group",), value_name="group"),
                CommandArgSpec(names=("source",), value_name="source"),
            ),
            run=_run_group_add_source,
        ),
        CommandNodeSpec(
            name="add-channel",
            summary="向分组添加 channel。",
            arg_specs=(
                CommandArgSpec(names=("group",), value_name="group"),
                CommandArgSpec(names=("source",), value_name="source"),
                CommandArgSpec(names=("channel",), value_name="channel"),
            ),
            run=_run_group_add_channel,
        ),
        CommandNodeSpec(
            name="remove-source",
            summary="从分组删除 source。",
            arg_specs=(
                CommandArgSpec(names=("group",), value_name="group"),
                CommandArgSpec(names=("source",), value_name="source"),
            ),
            run=_run_group_remove_source,
        ),
        CommandNodeSpec(
            name="remove-channel",
            summary="从分组删除 channel。",
            arg_specs=(
                CommandArgSpec(names=("group",), value_name="group"),
                CommandArgSpec(names=("source",), value_name="source"),
                CommandArgSpec(names=("channel",), value_name="channel"),
            ),
            run=_run_group_remove_channel,
        ),
    ),
)
