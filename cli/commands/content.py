from __future__ import annotations

import argparse
from datetime import datetime

from cli.formatters import (
    build_content_json_rows,
    build_search_json_rows,
    print_content,
    print_interaction_results,
    print_jsonl_rows,
    print_search_results,
    print_update_summaries,
    print_update_summary,
    print_update_targets,
)
from cli.commands.common import (
    require_action,
    require_option,
    resolve_limit,
    parse_since,
    summarize_interact_params,
    summarize_update_params,
    write_audit,
)
from cli.commands.specs import PROGRAM_NAME, CommandContext, CommandNodeSpec
from core.models import parse_content_ref
from core.help import HelpSection
from store.db import Store
from utils.time import since_datetime_to_iso


def _add_content_search_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", required=True)
    parser.add_argument("--channel")
    parser.add_argument("--query")
    parser.add_argument("--since")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--jsonl", action="store_true")


def _add_content_update_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source")
    parser.add_argument("--group")
    parser.add_argument("--channel")
    parser.add_argument("--since")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--all", dest="fetch_all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")


def _add_content_query_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source")
    parser.add_argument("--channel")
    parser.add_argument("--group")
    parser.add_argument("--keywords")
    parser.add_argument("--since")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--all", dest="fetch_all", action="store_true")
    parser.add_argument("--jsonl", action="store_true")


def _add_content_interact_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", required=True)
    parser.add_argument("--verb", required=True)
    parser.add_argument("--ref", dest="refs", action="append", required=True)


def run_content_search(args: argparse.Namespace, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    if args.channel is None and args.query is None:
        raise RuntimeError("content search requires --channel or --query")
    source = ctx.registry.build(args.source)
    require_action(ctx.registry, args.source, "content.search")
    if args.channel is not None:
        require_option(ctx.registry, args.source, "content.search", "channel")
    if args.query is not None:
        require_option(ctx.registry, args.source, "content.search", "query")
    since = parse_since(args.since) if args.since is not None else None
    if since is not None:
        require_option(ctx.registry, args.source, "content.search", "since")
    if args.limit is not None:
        require_option(ctx.registry, args.source, "content.search", "limit")
    limit = resolve_limit(args.limit)
    results = source.search_content(
        channel_key=args.channel,
        query=args.query,
        since=since,
        limit=limit,
    )
    validate_search_results(args.source, results, ctx.registry)
    if args.jsonl:
        print_jsonl_rows(build_search_json_rows(results, view_getter=source.get_content_search_view))
        return 0
    print_search_results(results, view_getter=source.get_content_search_view)
    return 0


def run_content_update(args: argparse.Namespace, extras: list[str], ctx: CommandContext) -> int:
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


def run_content_query(args: argparse.Namespace, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    if args.channel is not None and args.source is None:
        raise RuntimeError("--channel requires --source")
    if args.channel is not None and args.group is not None:
        raise RuntimeError("content query does not allow --channel with --group")
    if args.source is not None and args.group is not None:
        raise RuntimeError("content query does not allow --source with --group")
    if args.fetch_all and args.limit is not None:
        raise RuntimeError("content query does not allow --all with --limit")
    since = parse_since(args.since) if args.since is not None else None
    target_sources = _resolve_query_sources(ctx.registry, ctx.store, source=args.source, group=args.group)
    if args.keywords is not None:
        for source_name in target_sources:
            spec = ctx.registry.get_storage_spec(source_name)
            if not spec.supports_keywords:
                raise RuntimeError(f"{source_name} does not support --keywords")
    if since is not None:
        for source_name in target_sources:
            spec = ctx.registry.get_storage_spec(source_name)
            if spec.time_field is None:
                raise RuntimeError(f"{source_name} does not support --since")
    limit = None if args.fetch_all else resolve_limit(args.limit)
    rows = ctx.store.query_content(
        source=args.source,
        channel_key=args.channel,
        group_name=args.group,
        since=None if since is None else since_datetime_to_iso(since),
        keywords=args.keywords,
        limit=-1 if limit is None else limit,
        fetch_all=args.fetch_all,
    )
    view, native_view_ok = resolve_query_view(rows, ctx.registry)
    if args.jsonl:
        print_jsonl_rows(build_content_json_rows(rows, view=view, native_view_ok=native_view_ok))
        return 0
    print_content(rows, view=view, native_view_ok=native_view_ok)
    return 0


def run_content_interact(args: argparse.Namespace, extras: list[str], ctx: CommandContext) -> int:
    require_action(ctx.registry, args.source, "content.interact")
    source = ctx.registry.build(args.source)
    canonical_refs = tuple(args.refs)
    refs = [_parse_source_ref(args.source, ref, source) for ref in args.refs]
    params = _parse_interact_params(args.source, args.verb, extras, ctx.registry)
    params_summary = summarize_interact_params(args.verb, params)
    try:
        results = source.interact(args.verb, refs, params)
        write_audit(
            ctx.store,
            source,
            action="content.interact",
            target_kind="content_ref",
            targets=canonical_refs,
            dry_run=False,
            params_summary=params_summary,
            status="ok",
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        write_audit(
            ctx.store,
            source,
            action="content.interact",
            target_kind="content_ref",
            targets=canonical_refs,
            dry_run=False,
            params_summary=params_summary,
            status="error",
            error=str(exc),
        )
        raise
    print_interaction_results(results)
    return 0


def _run_group_content_update(
    args: argparse.Namespace,
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
        _require_update_options(
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
    args: argparse.Namespace,
    ctx: CommandContext,
    *,
    since: datetime | None,
    limit: int | None,
) -> int:
    _require_update_options(
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


def _parse_source_ref(source_name: str, ref: str, source) -> str:
    try:
        parsed = parse_content_ref(ref)
    except ValueError as exc:
        raise RuntimeError(f"invalid content_ref: {ref}") from exc
    if parsed.source != source_name:
        raise RuntimeError(f"content ref source mismatch: expected {source_name}, got {parsed.source}")
    return source.parse_content_ref(ref)


def _parse_interact_params(source_name: str, verb_name: str, extras: list[str], registry) -> dict[str, object]:
    resolver = registry.get_resolver(source_name)
    status = resolver.verb_status(verb_name)
    if status.status == "unsupported":
        raise RuntimeError(f"unsupported verb: {source_name}.{verb_name}")
    if status.status == "mode_unsupported":
        raise RuntimeError(
            f"verb is not supported in current mode: {source_name}.{verb_name} mode={resolver.resolved_mode}"
        )
    if status.status == "requires_config":
        raise RuntimeError(f"verb requires config: {', '.join(status.missing_keys)}")
    manifest = registry.get_manifest(source_name)
    verb = manifest.interaction_verbs[verb_name]
    parser = argparse.ArgumentParser(
        prog=f"{PROGRAM_NAME} content interact --source {source_name} --verb {verb_name}",
        add_help=False,
    )
    for param in verb.params:
        if resolver.param_status(verb_name, param.name).status == "mode_unsupported":
            continue
        flag = f"--{param.name.replace('_', '-')}"
        kwargs: dict[str, object] = {"dest": param.name}
        if param.type == "bool":
            kwargs["action"] = "store_true"
        elif param.multiple:
            kwargs["action"] = "append"
        else:
            kwargs["required"] = param.required
        parser.add_argument(flag, **kwargs)
    namespace, unknown = parser.parse_known_args(extras)
    if unknown:
        raise RuntimeError(f"unsupported interact params: {' '.join(unknown)}")
    params = vars(namespace)
    for param in verb.params:
        value = params.get(param.name)
        if param.type == "enum" and value is not None and value not in param.choices:
            raise RuntimeError(f"invalid value for --{param.name}: {value}")
        if param.type == "int":
            if param.multiple:
                params[param.name] = [int(item) for item in value or []]
            elif value is not None:
                params[param.name] = int(value)
    return params


def validate_search_results(source_name: str, results, registry) -> None:
    manifest = registry.get_manifest(source_name)
    if "content.interact" not in manifest.source_actions:
        return
    for result in results:
        if result.content_ref in (None, ""):
            raise RuntimeError(f"{source_name} content.search returned result missing content_ref")
        try:
            parsed = parse_content_ref(result.content_ref)
        except ValueError as exc:
            raise RuntimeError(f"{source_name} content.search returned invalid content_ref: {result.content_ref}") from exc
        if parsed.source != source_name:
            raise RuntimeError(
                f"{source_name} content.search returned content_ref source mismatch: {result.content_ref}"
            )


def _require_update_options(
    registry,
    source_name: str,
    *,
    channel: bool,
    since: bool,
    limit: bool,
    fetch_all: bool,
) -> None:
    require_action(registry, source_name, "content.update")
    if channel:
        require_option(registry, source_name, "content.update", "channel")
    if since:
        require_option(registry, source_name, "content.update", "since")
    if limit:
        require_option(registry, source_name, "content.update", "limit")
    if fetch_all:
        require_option(registry, source_name, "content.update", "all")


def _resolve_query_sources(registry, store: Store, *, source: str | None, group: str | None) -> list[str]:
    if source is not None:
        return [source]
    if group is not None:
        members = store.list_group_members(group)
        return sorted({member.source for member in members})
    return registry.list_names()


def resolve_query_view(rows, registry) -> tuple[object | None, bool]:
    if not rows:
        return None, False
    sources = {row.source for row in rows}
    if len(sources) != 1:
        specs = [registry.get_storage_spec(source_name) for source_name in sorted(sources)]
        first = specs[0]
        if not first.view_id:
            return None, False
        if any(spec.view_id != first.view_id or spec.view_fields != first.view_fields for spec in specs[1:]):
            return None, False
        return registry.build(specs[0].source).get_query_view(), True
    source_name = next(iter(sources))
    spec = registry.get_storage_spec(source_name)
    if spec.view_id is None:
        return None, False
    return registry.build(source_name).get_query_view(), True


def group_targets_by_source(targets: list[tuple[str, str]]) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for source_name, channel_key in targets:
        grouped.setdefault(source_name, []).append(channel_key)
    return {source_name: tuple(sorted(channel_keys)) for source_name, channel_keys in grouped.items()}


CONTENT_COMMAND = CommandNodeSpec(
    name="content",
    summary="统一内容操作入口。",
    command_line="content ...",
    child_dest="content_command",
    children=(
        CommandNodeSpec(
            name="search",
            summary="远端发现 content，不落库。",
            command_line="content search --source <source> [--channel <channel>] [--query <query>] [--since <since>] [--limit <n>] [--jsonl]",
            sections=(
                HelpSection(
                    title="语义",
                    lines=[
                        "--source 必填",
                        "--channel 与 --query 至少提供一个",
                        "是否支持 --since 由 source capability 决定",
                    ],
                ),
                HelpSection(
                    title="Examples",
                    lines=[
                        "content search --source <source> --query <query> --limit <n>",
                        "content search --source <source> --channel <channel> --jsonl",
                    ],
                ),
            ),
            configure_parser=_add_content_search_args,
            run=run_content_search,
        ),
        CommandNodeSpec(
            name="update",
            summary="只同步已订阅目标，并落库。",
            command_line="content update --source <source> ... | content update --group <group> ...",
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
            configure_parser=_add_content_update_args,
            run=run_content_update,
        ),
        CommandNodeSpec(
            name="query",
            summary="永远只查本地库。",
            command_line="content query [--source <source>] [--channel <channel>] [--group <group>] ...",
            sections=(
                HelpSection(
                    title="语义",
                    lines=[
                        "--keywords 只是本地过滤，不触发远端搜索",
                        "--group 只做本地过滤，不做远端展开",
                        "默认 limit=20，不做 since=>all 的隐式语义",
                    ],
                ),
                HelpSection(
                    title="Examples",
                    lines=[
                        "content query --source <source> --limit <n>",
                        "content query --group <group> --keywords <keywords> --limit <n>",
                    ],
                ),
            ),
            configure_parser=_add_content_query_args,
            run=run_content_query,
        ),
        CommandNodeSpec(
            name="interact",
            summary="显式远端副作用操作。",
            command_line="content interact --source <source> --verb <verb> --ref <content_ref> ...",
            sections=(
                HelpSection(
                    title="语义",
                    lines=[
                        "--source 必填",
                        "--verb 必填",
                        "--ref 至少一个",
                        "所有 ref 必须属于同一 source",
                    ],
                ),
                HelpSection(
                    title="Examples",
                    lines=[
                        "content interact --source <source> --verb <verb> --ref <content_ref>",
                    ],
                ),
            ),
            configure_parser=_add_content_interact_args,
            run=run_content_interact,
            parse_known_args=True,
        ),
    ),
)
