from __future__ import annotations

from agent_data_cli.cli.formatters import print_cli_config_entries, print_config_check, print_config_entries
from agent_data_cli.cli.commands.specs import CommandArgSpec, CommandContext, CommandNodeSpec
from agent_data_cli.core.config import validate_config_value
from agent_data_cli.core.manifest import CORE_ACTION_NAMES, SOURCE_ACTION_NAMES
from agent_data_cli.migration import migrate_home, migrate_source_workspace
from agent_data_cli.runtime_paths import RuntimePaths, resolve_runtime_paths
from agent_data_cli.store.db import Store


CONFIG_CHECK_ACTION_IDS = CORE_ACTION_NAMES | SOURCE_ACTION_NAMES


def _run_config_cli_list(args, extras: list[str], ctx: CommandContext) -> int:
    _ = args, extras
    _print_cli_config_entries(ctx)
    return 0


def _run_config_cli_set(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    spec = ctx.registry.get_cli_config_field_spec(args.key)
    validate_config_value(spec, args.value, owner="cli")
    current_paths = _resolve_active_runtime_paths(ctx)
    if args.key == "home":
        migrated_paths = migrate_home(current_paths, args.value)
        _print_cli_config_entries_with_paths(ctx, migrated_paths)
        return 0
    if args.key == "source_workspace":
        migrated_paths = migrate_source_workspace(current_paths, args.value)
        _print_cli_config_entries_with_paths(ctx, migrated_paths)
        return 0
    ctx.store.set_cli_config(args.key, args.value, spec.type, spec.secret)
    _print_cli_config_entries_with_paths(ctx, current_paths)
    return 0


def _run_config_cli_unset(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    ctx.store.unset_cli_config(args.key)
    _print_cli_config_entries_with_paths(ctx, _resolve_active_runtime_paths(ctx))
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
    _print_cli_config_entries_with_paths(ctx, _resolve_active_runtime_paths(ctx))


def _print_cli_config_entries_with_paths(ctx: CommandContext, paths: RuntimePaths) -> None:
    store = ctx.store
    if str(paths.db_path) != getattr(ctx.store, "path", ""):
        store = Store(str(paths.db_path))
    defaults_by_key = {
        spec.key: ctx.registry.get_cli_config_default(spec.key)
        for spec in ctx.registry.get_cli_config_specs()
    }
    defaults_by_key["home"] = str(paths.home)
    defaults_by_key["source_workspace"] = str(paths.source_workspace)
    print_cli_config_entries(
        ctx.registry.get_cli_config_specs(),
        store.list_cli_configs(),
        defaults_by_key,
    )


def _resolve_active_runtime_paths(ctx: CommandContext) -> RuntimePaths:
    paths = resolve_runtime_paths()
    source_workspace_entry = ctx.store.get_cli_config_map().get("source_workspace")
    if source_workspace_entry is None:
        return paths
    return RuntimePaths(
        home=paths.home,
        db_path=paths.db_path,
        source_workspace=resolve_runtime_paths(source_workspace_override=source_workspace_entry.value).source_workspace,
        runtime_dir=paths.runtime_dir,
        launcher_path=paths.launcher_path,
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
