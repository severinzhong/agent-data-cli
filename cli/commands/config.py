from __future__ import annotations

from cli.formatters import print_cli_config_entries, print_config_check, print_config_entries
from cli.commands.specs import CommandArgSpec, CommandContext, CommandNodeSpec
from core.config import validate_config_value
from core.manifest import CORE_ACTION_NAMES, SOURCE_ACTION_NAMES


CONFIG_CHECK_ACTION_IDS = CORE_ACTION_NAMES | SOURCE_ACTION_NAMES


def _run_config_cli_list(args, extras: list[str], ctx: CommandContext) -> int:
    _ = args, extras
    _print_cli_config_entries(ctx)
    return 0


def _run_config_cli_set(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    spec = ctx.registry.get_cli_config_field_spec(args.key)
    validate_config_value(spec, args.value, owner="cli")
    ctx.store.set_cli_config(args.key, args.value, spec.type, spec.secret)
    _print_cli_config_entries(ctx)
    return 0


def _run_config_cli_unset(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    ctx.store.unset_cli_config(args.key)
    _print_cli_config_entries(ctx)
    return 0


def _run_config_cli_explain(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    _print_config_explain("cli", ctx.registry.get_cli_config_field_spec(args.key))
    return 0


def _run_config_source_list(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    print_config_entries(ctx.store.list_source_configs(args.source))
    return 0


def _run_config_source_set(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    spec = ctx.registry.get_source_config_field_spec(args.source, args.key)
    validate_config_value(spec, args.value, owner=args.source)
    ctx.store.set_source_config(args.source, args.key, args.value, spec.type, spec.secret)
    print_config_entries(ctx.store.list_source_configs(args.source))
    return 0


def _run_config_source_unset(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    ctx.store.unset_source_config(args.source, args.key)
    print_config_entries(ctx.store.list_source_configs(args.source))
    return 0


def _run_config_source_explain(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    _print_config_explain(args.source, ctx.registry.get_source_config_field_spec(args.source, args.key))
    return 0


def _run_config_source_check(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    _validate_config_check_action_id(args.action_id)
    if args.action_id == "content.interact" and not args.verb:
        raise RuntimeError("config source check --for content.interact requires --verb")
    print_config_check(ctx.registry.config_check(args.source, action_id=args.action_id, verb=args.verb))
    return 0


def _print_config_explain(owner: str, spec) -> None:
    print(f"{owner}.{spec.key}")
    print(f"type: {spec.type}")
    print(f"secret: {int(spec.secret)}")
    print(f"description: {spec.description}")
    if spec.inherits_from_cli:
        print(f"inherits_from_cli: {spec.inherits_from_cli}")
    if spec.choices:
        print(f"choices: {', '.join(spec.choices)}")
    if spec.obtain_hint:
        print(f"obtain_hint: {spec.obtain_hint}")
    if spec.example:
        print(f"example: {spec.example}")


def _print_cli_config_entries(ctx: CommandContext) -> None:
    defaults_by_key = {
        spec.key: ctx.registry.get_cli_config_default(spec.key)
        for spec in ctx.registry.get_cli_config_specs()
    }
    print_cli_config_entries(
        ctx.registry.get_cli_config_specs(),
        ctx.store.list_cli_configs(),
        defaults_by_key,
    )


def _validate_config_check_action_id(action_id: str | None) -> None:
    if action_id is None:
        return
    if action_id not in CONFIG_CHECK_ACTION_IDS:
        raise RuntimeError(f"unknown action id: {action_id}")


CONFIG_COMMAND = CommandNodeSpec(
    name="config",
    summary="Inspect and modify CLI or source configuration.",
    child_dest="config_scope",
    children=(
        CommandNodeSpec(
            name="cli",
            summary="Manage CLI-level configuration.",
            child_dest="config_command",
            children=(
                CommandNodeSpec(
                    name="list",
                    summary="List CLI configuration.",
                    run=_run_config_cli_list,
                ),
                CommandNodeSpec(
                    name="set",
                    summary="Set a CLI configuration value.",
                    arg_specs=(
                        CommandArgSpec(names=("key",), value_name="key"),
                        CommandArgSpec(names=("value",), value_name="value"),
                    ),
                    run=_run_config_cli_set,
                ),
                CommandNodeSpec(
                    name="unset",
                    summary="Unset a CLI configuration value.",
                    arg_specs=(CommandArgSpec(names=("key",), value_name="key"),),
                    run=_run_config_cli_unset,
                ),
                CommandNodeSpec(
                    name="explain",
                    summary="Explain a CLI configuration field.",
                    arg_specs=(CommandArgSpec(names=("key",), value_name="key"),),
                    run=_run_config_cli_explain,
                ),
            ),
        ),
        CommandNodeSpec(
            name="source",
            summary="Manage source configuration.",
            child_dest="config_command",
            children=(
                CommandNodeSpec(
                    name="list",
                    summary="List configuration for a source.",
                    arg_specs=(CommandArgSpec(names=("source",), value_name="source"),),
                    run=_run_config_source_list,
                ),
                CommandNodeSpec(
                    name="set",
                    summary="Set a source configuration value.",
                    arg_specs=(
                        CommandArgSpec(names=("source",), value_name="source"),
                        CommandArgSpec(names=("key",), value_name="key"),
                        CommandArgSpec(names=("value",), value_name="value"),
                    ),
                    run=_run_config_source_set,
                ),
                CommandNodeSpec(
                    name="unset",
                    summary="Unset a source configuration value.",
                    arg_specs=(
                        CommandArgSpec(names=("source",), value_name="source"),
                        CommandArgSpec(names=("key",), value_name="key"),
                    ),
                    run=_run_config_source_unset,
                ),
                CommandNodeSpec(
                    name="explain",
                    summary="Explain a source configuration field.",
                    arg_specs=(
                        CommandArgSpec(names=("source",), value_name="source"),
                        CommandArgSpec(names=("key",), value_name="key"),
                    ),
                    run=_run_config_source_explain,
                ),
                CommandNodeSpec(
                    name="check",
                    summary="Check configuration status for a source.",
                    usage_override="config source check <source> [--for <action-id>] [--verb <verb>]",
                    arg_specs=(
                        CommandArgSpec(names=("source",), value_name="source"),
                        CommandArgSpec(names=("--for",), value_name="action-id", dest="action_id"),
                        CommandArgSpec(names=("--verb",), value_name="verb"),
                    ),
                    run=_run_config_source_check,
                ),
            ),
        ),
    ),
)
