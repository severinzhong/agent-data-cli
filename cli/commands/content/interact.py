from __future__ import annotations

from cli.commands.common import summarize_interact_params, require_action, write_audit
from cli.commands.content.common import parse_interact_params, parse_source_ref
from cli.commands.specs import CommandArgSpec, CommandContext, CommandNodeSpec
from cli.formatters import print_interaction_results
from core.help import HelpSection


def run_content_interact(args, extras: list[str], ctx: CommandContext) -> int:
    require_action(ctx.registry, args.source, "content.interact")
    source = ctx.registry.build(args.source)
    canonical_refs = tuple(args.refs)
    refs = [parse_source_ref(args.source, ref, source) for ref in args.refs]
    params = parse_interact_params(args.source, args.verb, extras, ctx.registry)
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


CONTENT_INTERACT_COMMAND = CommandNodeSpec(
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
    arg_specs=(
        CommandArgSpec(names=("--source",), value_name="source", required=True),
        CommandArgSpec(names=("--verb",), value_name="verb", required=True),
        CommandArgSpec(names=("--ref",), value_name="content_ref", required=True, action="append", dest="refs"),
    ),
    run=run_content_interact,
    parse_known_args=True,
)
