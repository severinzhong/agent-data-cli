from __future__ import annotations

from rich.console import Console

from core.help import HelpDoc, HelpSection
from core.manifest import to_cli_flag
from core.registry import SourceRegistry


def build_global_help_doc() -> HelpDoc:
    from cli.commands import build_global_help_doc as _build_global_help_doc

    return _build_global_help_doc()


def build_command_help_doc(command: str) -> HelpDoc:
    from cli.commands import build_command_help_doc as _build_command_help_doc

    return _build_command_help_doc(command)


def build_source_help_doc(registry: SourceRegistry, source_name: str) -> HelpDoc:
    manifest = registry.get_manifest(source_name)
    resolver = registry.get_resolver(source_name)
    source = registry.build(source_name)
    sections: list[HelpSection] = [
        HelpSection(
            title="Actions",
            lines=_build_action_lines(manifest, resolver),
        ),
    ]
    if manifest.mode is not None:
        sections.append(
            HelpSection(
                title="Mode",
                lines=[
                    f"default: {manifest.mode.default}",
                    f"effective: {source.resolve_mode()}",
                    *[f"{choice.value}: {choice.summary}" for choice in manifest.mode.choices],
                ],
            )
        )
    config_lines = []
    for field_spec in resolver.visible_config_fields():
        line = f"{field_spec.key} ({field_spec.type})"
        if field_spec.inherits_from_cli:
            line = f"{line} <- cli.{field_spec.inherits_from_cli}"
        if field_spec.obtain_hint:
            line = f"{line} | {field_spec.obtain_hint}"
        config_lines.append(line)
    if config_lines:
        sections.append(HelpSection(title="Config", lines=config_lines))
    if manifest.query is not None:
        query_lines = [f"time_field: {manifest.query.time_field or 'none'}"]
        if manifest.query.supports_keywords:
            query_lines.append("supports --keywords")
        else:
            query_lines.append("does not support --keywords")
        sections.append(HelpSection(title="Query", lines=query_lines))
    if manifest.interaction_verbs:
        verb_lines = []
        for verb_name, verb in manifest.interaction_verbs.items():
            status = resolver.verb_status(verb_name)
            if status.status == "mode_unsupported":
                continue
            line = verb_name
            if status.status == "requires_config":
                line = f"{line} (requires config: {', '.join(status.missing_keys)})"
            verb_lines.append(line)
            for param in verb.params:
                param_status = resolver.param_status(verb_name, param.name)
                if param_status.status == "mode_unsupported":
                    continue
                verb_lines.append(f"{to_cli_flag(param.name)} ({param.type})")
        if verb_lines:
            sections.append(HelpSection(title="Interact", lines=verb_lines))
    if manifest.docs is not None:
        if manifest.docs.notes:
            sections.append(HelpSection(title="Notes", lines=list(manifest.docs.notes)))
        if manifest.docs.examples:
            sections.append(
                HelpSection(
                    title="Examples",
                    lines=[_strip_command_prefix(line) for line in manifest.docs.examples],
                )
            )
    return HelpDoc(
        title=source_name,
        summary=manifest.identity.summary,
        sections=sections,
    )


def _build_action_lines(manifest, resolver) -> list[str]:
    lines: list[str] = []
    for action_name in (
        "source.health",
        "channel.list",
        "channel.search",
        "content.search",
        "content.update",
        "content.query",
        "content.interact",
    ):
        status = resolver.action_status(action_name)
        if status.status == "mode_unsupported":
            continue
        label = action_name
        if status.status == "requires_config":
            label = f"{label} (requires config: {', '.join(status.missing_keys)})"
        elif status.status == "unsupported":
            continue
        lines.append(label)
        if action_name in manifest.source_actions:
            action = manifest.source_actions[action_name]
            for option_name in action.options:
                option_status = resolver.option_status(action_name, option_name)
                if option_status.status == "mode_unsupported":
                    continue
                option_line = f"  {to_cli_flag(option_name)}"
                if option_status.status == "requires_config":
                    option_line = f"{option_line} (requires config: {', '.join(option_status.missing_keys)})"
                lines.append(option_line)
    return lines


def render_help_doc(console: Console, doc: HelpDoc) -> None:
    console.print(f"[bold]{doc.title}[/bold]")
    console.print(doc.summary)
    for section in doc.sections:
        console.print()
        console.print(f"[bold]{section.title}[/bold]")
        for line in section.lines:
            console.print(f"- {line}")


def print_help_doc(doc: HelpDoc) -> None:
    render_help_doc(Console(), doc)


def _strip_command_prefix(line: str) -> str:
    for prefix in ("dc ", "uv run python -m cli ", ".venv/bin/python -m cli "):
        if line.startswith(prefix):
            return line[len(prefix) :]
    return line
