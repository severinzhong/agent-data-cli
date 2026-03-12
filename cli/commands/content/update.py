from __future__ import annotations

from datetime import datetime

from cli.commands.common import parse_since, resolve_limit, summarize_update_params, write_audit
from cli.commands.content.common import group_targets_by_source, require_update_options
from cli.commands.specs import CommandArgSpec, CommandContext, CommandNodeSpec
from cli.formatters import print_update_summaries, print_update_summary, print_update_targets
from core.help import HelpSection


def run_content_update(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    if bool(args.source) == bool(args.group):
        raise RuntimeError("content update requires exactly one of --source or --group")
    if args.channel is not None and args.source is None:
        raise RuntimeError("--channel requires --source")
    if args.fetch_all and args.since is not None:
        raise RuntimeError("content update does not allow --all with --since")
    if args.fetch_all and args.limit is not None:
        raise RuntimeError("content update does not allow --all with --limit")
    if args.dry_run and args.group is None:
        raise RuntimeError("--dry-run only works with content update --group")
    since = parse_since(args.since) if args.since is not None else None
    limit = None if args.fetch_all else resolve_limit(args.limit)
    if args.group is not None:
        return _run_group_content_update(args, ctx, since=since, limit=limit)
    return _run_single_source_content_update(args, ctx, since=since, limit=limit)


def _run_group_content_update(
    args,
    ctx: CommandContext,
    *,
    since: datetime | None,
    limit: int | None,
) -> int:
    targets = ctx.store.expand_group_update_targets(args.group)
    if not targets:
        raise RuntimeError(f"group has no subscribed update targets: {args.group}")
    for source_name, channel_key in targets:
        if not ctx.store.is_subscribed(source_name, channel_key):
            raise RuntimeError(f"group target is not subscribed: {source_name}:{channel_key}")
    grouped_targets_by_source = group_targets_by_source(targets)
    for source_name in grouped_targets_by_source:
        require_update_options(
            ctx.registry,
            source_name,
            channel=False,
            since=args.since is not None,
            limit=args.limit is not None,
            fetch_all=args.fetch_all,
        )
    if args.dry_run:
        for source_name, grouped_targets in grouped_targets_by_source.items():
            write_audit(
                ctx.store,
                ctx.registry.build(source_name),
                action="content.update",
                target_kind="channel",
                targets=grouped_targets,
                dry_run=True,
                params_summary=summarize_update_params(limit=limit, since=since, fetch_all=args.fetch_all),
                status="ok",
                error=None,
            )
        print_update_targets(targets)
        return 0
    summaries = []
    for source_name, grouped_targets in grouped_targets_by_source.items():
        source = ctx.registry.build(source_name)
        try:
            for channel_key in grouped_targets:
                summary = source.update(
                    channel_key=channel_key,
                    limit=limit,
                    since=since,
                    fetch_all=args.fetch_all,
                )
                summaries.append(summary)
            write_audit(
                ctx.store,
                source,
                action="content.update",
                target_kind="channel",
                targets=grouped_targets,
                dry_run=False,
                params_summary=summarize_update_params(limit=limit, since=since, fetch_all=args.fetch_all),
                status="ok",
                error=None,
            )
        except Exception as exc:  # noqa: BLE001
            write_audit(
                ctx.store,
                source,
                action="content.update",
                target_kind="channel",
                targets=grouped_targets,
                dry_run=False,
                params_summary=summarize_update_params(limit=limit, since=since, fetch_all=args.fetch_all),
                status="error",
                error=str(exc),
            )
            raise
    print_update_summaries(summaries)
    return 0


def _run_single_source_content_update(
    args,
    ctx: CommandContext,
    *,
    since: datetime | None,
    limit: int | None,
) -> int:
    require_update_options(
        ctx.registry,
        args.source,
        channel=args.channel is not None,
        since=args.since is not None,
        limit=args.limit is not None,
        fetch_all=args.fetch_all,
    )
    source = ctx.registry.build(args.source)
    audit_targets = (
        (args.channel,)
        if args.channel is not None
        else tuple(sorted(subscription.channel_key for subscription in source.list_subscriptions()))
    )
    try:
        summary = source.update(
            channel_key=args.channel,
            limit=limit,
            since=since,
            fetch_all=args.fetch_all,
        )
        write_audit(
            ctx.store,
            source,
            action="content.update",
            target_kind="channel",
            targets=audit_targets,
            dry_run=False,
            params_summary=summarize_update_params(limit=limit, since=since, fetch_all=args.fetch_all),
            status="ok",
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        write_audit(
            ctx.store,
            source,
            action="content.update",
            target_kind="channel",
            targets=audit_targets if args.channel is None else (args.channel,),
            dry_run=False,
            params_summary=summarize_update_params(limit=limit, since=since, fetch_all=args.fetch_all),
            status="error",
            error=str(exc),
        )
        raise
    print_update_summary(summary)
    return 0


CONTENT_UPDATE_COMMAND = CommandNodeSpec(
    name="update",
    summary="只同步已订阅目标，并落库。",
    usage_override="content update --source <source> ... | content update --group <group> ...",
    sections=(
        HelpSection(
            title="语义",
            lines=[
                "--source 与 --group 二选一",
                "--channel 只允许跟 --source 组合",
                "--all 与 --since 互斥",
                "--all 与 --limit 互斥",
                "--dry-run 只允许配合 --group",
            ],
        ),
        HelpSection(
            title="Examples",
            lines=[
                "content update --source <source> --channel <channel> --limit <n>",
                "content update --group <group> --dry-run",
            ],
        ),
    ),
    arg_specs=(
        CommandArgSpec(names=("--source",), value_name="source"),
        CommandArgSpec(names=("--group",), value_name="group"),
        CommandArgSpec(names=("--channel",), value_name="channel"),
        CommandArgSpec(names=("--since",), value_name="since"),
        CommandArgSpec(names=("--limit",), value_name="n", type=int),
        CommandArgSpec(names=("--all",), action="store_true", dest="fetch_all"),
        CommandArgSpec(names=("--dry-run",), action="store_true"),
    ),
    run=run_content_update,
)
