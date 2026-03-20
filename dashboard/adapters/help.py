from __future__ import annotations

from cli.commands import ROOT_COMMANDS, build_command_help_doc, build_global_help_doc
from cli.help import build_source_help_doc
from cli.commands.specs import CommandNodeSpec
from core.help import HelpDoc


def list_help_topics(registry) -> dict[str, list[str]]:
    return {
        "commands": sorted(_collect_topics(ROOT_COMMANDS)),
        "sources": registry.list_names(),
    }


def build_help_doc_for_topic(registry, topic: str | None) -> HelpDoc:
    normalized = "" if topic is None else topic.strip()
    if not normalized or normalized == "global":
        return build_global_help_doc()
    if normalized in registry.list_names():
        return build_source_help_doc(registry, normalized)
    return build_command_help_doc(normalized)


def _collect_topics(commands: tuple[CommandNodeSpec, ...], parent: tuple[str, ...] = ()) -> list[str]:
    topics: list[str] = []
    for command in commands:
        current = parent + (command.name,)
        topics.append(" ".join(current))
        if command.children:
            topics.extend(_collect_topics(command.children, current))
    return topics
