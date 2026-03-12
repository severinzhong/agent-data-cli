from __future__ import annotations

from cli.commands.channel import CHANNEL_COMMAND
from cli.commands.config import CONFIG_COMMAND
from cli.commands.content import CONTENT_COMMAND
from cli.commands.group import GROUP_COMMAND
from cli.commands.help import make_help_command
from cli.commands.source import SOURCE_COMMAND
from cli.commands.specs import (
    CommandContext,
    CommandNodeSpec,
    build_command_help_doc as _build_command_help_doc,
    build_global_help_doc as _build_global_help_doc,
    build_root_parser,
    dispatch_command,
    parse_command_argv,
)
from cli.commands.sub import SUB_COMMAND
from core.help import HelpSection


_BASE_COMMANDS: tuple[CommandNodeSpec, ...] = (
    SOURCE_COMMAND,
    CHANNEL_COMMAND,
    CONTENT_COMMAND,
    SUB_COMMAND,
    GROUP_COMMAND,
    CONFIG_COMMAND,
)

GLOBAL_HELP_SECTIONS = (
    HelpSection(
        title="Examples",
        lines=[
            "help content search",
            "source list",
            "channel search --source <source> --query <query>",
            "content update --group <group> --dry-run",
        ],
    ),
)

HELP_COMMAND = make_help_command(
    build_global_help_doc=lambda: build_global_help_doc(),
    build_command_help_doc=lambda topic: build_command_help_doc(topic),
)

ROOT_COMMANDS: tuple[CommandNodeSpec, ...] = (*_BASE_COMMANDS, HELP_COMMAND)


def build_parser():
    return build_root_parser(ROOT_COMMANDS)


def build_global_help_doc():
    return _build_global_help_doc(
        title="data-cli",
        summary="Unified multi-source content CLI.",
        commands=ROOT_COMMANDS,
        sections=GLOBAL_HELP_SECTIONS,
    )


def build_command_help_doc(topic: str):
    return _build_command_help_doc(ROOT_COMMANDS, topic)


__all__ = [
    "CommandContext",
    "ROOT_COMMANDS",
    "build_command_help_doc",
    "build_global_help_doc",
    "build_parser",
    "dispatch_command",
    "parse_command_argv",
]
