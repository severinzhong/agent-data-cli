from __future__ import annotations

import argparse
from typing import Callable

from cli.commands.specs import CommandContext, CommandNodeSpec
from cli.help import build_source_help_doc, print_help_doc
from core.help import HelpDoc, HelpSection


def make_help_command(
    *,
    build_global_help_doc: Callable[[], HelpDoc],
    build_command_help_doc: Callable[[str], HelpDoc],
) -> CommandNodeSpec:
    def _add_help_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("topic", nargs="*")

    def _run_help(args: argparse.Namespace, extras: list[str], ctx: CommandContext) -> int:
        _ = extras
        topic = " ".join(args.topic or []).strip()
        if not topic:
            print_help_doc(build_global_help_doc())
            return 0
        if topic in ctx.registry.list_names():
            print_help_doc(build_source_help_doc(ctx.registry, topic))
            return 0
        print_help_doc(build_command_help_doc(topic))
        return 0

    return CommandNodeSpec(
        name="help",
        summary="查看全局帮助、命令帮助或 source 帮助。",
        command_line="help ...",
        sections=(
            HelpSection(
                title="Examples",
                lines=[
                    "help",
                    "help source",
                    "help channel search",
                    "help content query",
                    "help <source>",
                ],
            ),
        ),
        configure_parser=_add_help_args,
        run=_run_help,
    )
