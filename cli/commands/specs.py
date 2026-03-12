from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Callable

from core.help import HelpDoc, HelpSection
from core.registry import SourceRegistry
from store.db import Store

PROGRAM_NAME = "python -m cli"


ParserConfigurator = Callable[[argparse.ArgumentParser], None]
CommandRunner = Callable[[argparse.Namespace, list[str], "CommandContext"], int]


@dataclass(slots=True)
class CommandContext:
    registry: SourceRegistry
    store: Store


@dataclass(slots=True)
class CommandNodeSpec:
    name: str
    summary: str
    command_line: str
    sections: tuple[HelpSection, ...] = ()
    configure_parser: ParserConfigurator | None = None
    run: CommandRunner | None = None
    children: tuple["CommandNodeSpec", ...] = ()
    parse_known_args: bool = False
    child_dest: str | None = None

    def __post_init__(self) -> None:
        child_names = [child.name for child in self.children]
        if len(child_names) != len(set(child_names)):
            raise ValueError(f"duplicate child command names under {self.name}")
        if self.children and self.run is not None:
            raise ValueError(f"group command cannot define run handler: {self.name}")
        if not self.children and self.run is None:
            raise ValueError(f"leaf command must define run handler: {self.name}")


def build_root_parser(commands: tuple[CommandNodeSpec, ...]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROGRAM_NAME)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in commands:
        _attach_node(subparsers, command, path=())
    return parser


def parse_command_argv(
    parser: argparse.ArgumentParser,
    argv: list[str],
) -> tuple[argparse.Namespace, list[str]]:
    args, extras = parser.parse_known_args(argv)
    if extras and not getattr(args, "__accept_extras__", False):
        parser.error(f"unrecognized arguments: {' '.join(extras)}")
    return args, extras


def dispatch_command(args: argparse.Namespace, extras: list[str], ctx: CommandContext) -> int:
    node = getattr(args, "__command_node__", None)
    if node is None or node.run is None:
        raise RuntimeError("missing command handler")
    return node.run(args, extras, ctx)


def build_global_help_doc(
    *,
    title: str,
    summary: str,
    commands: tuple[CommandNodeSpec, ...],
    sections: tuple[HelpSection, ...] = (),
) -> HelpDoc:
    return HelpDoc(
        title=title,
        summary=summary,
        sections=[
            HelpSection(title="命令速览", lines=[command.command_line for command in commands]),
            *list(sections),
        ],
    )


def build_command_help_doc(commands: tuple[CommandNodeSpec, ...], topic: str) -> HelpDoc:
    tokens = tuple(part for part in topic.split() if part)
    if not tokens:
        raise RuntimeError("empty help topic")
    node = resolve_topic_node(commands, tokens)
    sections: list[HelpSection] = []
    if node.children:
        sections.append(HelpSection(title="Commands", lines=[child.command_line for child in node.children]))
    sections.extend(node.sections)
    return HelpDoc(
        title=" ".join(tokens),
        summary=node.summary,
        sections=sections,
    )


def resolve_topic_node(commands: tuple[CommandNodeSpec, ...], tokens: tuple[str, ...]) -> CommandNodeSpec:
    current = {command.name: command for command in commands}
    node: CommandNodeSpec | None = None
    for token in tokens:
        node = current.get(token)
        if node is None:
            raise RuntimeError(f"unknown help topic: {' '.join(tokens)}")
        current = {child.name: child for child in node.children}
    if node is None:
        raise RuntimeError(f"unknown help topic: {' '.join(tokens)}")
    return node


def _attach_node(
    subparsers: argparse._SubParsersAction,
    node: CommandNodeSpec,
    *,
    path: tuple[str, ...],
) -> None:
    parser = subparsers.add_parser(node.name)
    if node.configure_parser is not None:
        node.configure_parser(parser)
    next_path = path + (node.name,)
    if node.children:
        child_subparsers = parser.add_subparsers(dest=node.child_dest or _dest_name(next_path), required=True)
        for child in node.children:
            _attach_node(child_subparsers, child, path=next_path)
        return
    parser.set_defaults(
        __command_node__=node,
        __command_path__=next_path,
        __accept_extras__=node.parse_known_args,
    )


def _dest_name(path: tuple[str, ...]) -> str:
    return "__" + "_".join(path) + "_command"
