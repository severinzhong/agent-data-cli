from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Callable

from agent_data_cli.core.help import HelpDoc, HelpSection
from agent_data_cli.core.registry import SourceRegistry
from agent_data_cli.store.db import Store

PROGRAM_NAME = "adc"


ParserConfigurator = Callable[[argparse.ArgumentParser], None]
CommandRunner = Callable[[argparse.Namespace, list[str], "CommandContext"], int]


@dataclass(slots=True)
class CommandContext:
    registry: SourceRegistry
    store: Store


@dataclass(slots=True)
class CommandArgSpec:
    names: tuple[str, ...]
    value_name: str | None = None
    required: bool = False
    action: str | None = None
    dest: str | None = None
    nargs: str | int | None = None
    type: object | None = None
    exclusive_group: str | None = None

    def add_to_parser(self, parser: argparse.ArgumentParser | argparse._MutuallyExclusiveGroup) -> None:
        kwargs: dict[str, object] = {}
        if self.required and not self.is_positional:
            kwargs["required"] = True
        if self.action is not None:
            kwargs["action"] = self.action
        if self.dest is not None and not self.is_positional:
            kwargs["dest"] = self.dest
        if self.nargs is not None:
            kwargs["nargs"] = self.nargs
        if self.type is not None:
            kwargs["type"] = self.type
        parser.add_argument(*self.names, **kwargs)

    def help_line(self) -> str:
        return self.usage_fragment()

    def usage_fragment(self, *, bracket_optional: bool = True) -> str:
        if self.is_positional:
            if self.value_name is None:
                return self.names[0]
            return f"<{self.value_name}>"
        flag = self.names[0]
        if self.action == "store_true":
            rendered = flag
        elif self.value_name is not None:
            rendered = f"{flag} <{self.value_name}>"
        else:
            rendered = flag
        if self.required or not bracket_optional:
            return rendered
        return f"[{rendered}]"

    @property
    def is_positional(self) -> bool:
        return all(not name.startswith("-") for name in self.names)


@dataclass(slots=True)
class CommandNodeSpec:
    name: str
    summary: str
    usage_override: str | None = None
    sections: tuple[HelpSection, ...] = ()
    arg_specs: tuple[CommandArgSpec, ...] = ()
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

    def usage_line(self, parent_path: tuple[str, ...] = ()) -> str:
        if self.usage_override is not None:
            return self.usage_override
        base = " ".join((*parent_path, self.name)).strip()
        if self.children:
            return f"{base} ..."
        if not self.arg_specs:
            return base
        return " ".join([base, *_render_usage_parts(self.arg_specs)])


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
            HelpSection(title="Command Overview", lines=_collect_leaf_usage_lines(commands)),
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
        sections.append(HelpSection(title="Commands", lines=[child.usage_line(tokens) for child in node.children]))
    elif node.arg_specs:
        sections.append(HelpSection(title="Arguments", lines=[arg.help_line() for arg in node.arg_specs]))
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
    exclusive_groups: dict[str, argparse._MutuallyExclusiveGroup] = {}
    for arg_spec in node.arg_specs:
        target: argparse.ArgumentParser | argparse._MutuallyExclusiveGroup = parser
        if arg_spec.exclusive_group is not None:
            group = exclusive_groups.get(arg_spec.exclusive_group)
            if group is None:
                group = parser.add_mutually_exclusive_group()
                exclusive_groups[arg_spec.exclusive_group] = group
            target = group
        arg_spec.add_to_parser(target)
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


def _collect_leaf_usage_lines(
    commands: tuple[CommandNodeSpec, ...],
    parent_path: tuple[str, ...] = (),
) -> list[str]:
    lines: list[str] = []
    for command in commands:
        current_path = parent_path + (command.name,)
        if command.children:
            lines.extend(_collect_leaf_usage_lines(command.children, current_path))
            continue
        lines.append(command.usage_line(parent_path))
    return lines


def _render_usage_parts(arg_specs: tuple[CommandArgSpec, ...]) -> list[str]:
    parts: list[str] = []
    rendered_groups: set[str] = set()
    for arg_spec in arg_specs:
        if arg_spec.exclusive_group is None:
            parts.append(arg_spec.help_line())
            continue
        if arg_spec.exclusive_group in rendered_groups:
            continue
        group_specs = tuple(spec for spec in arg_specs if spec.exclusive_group == arg_spec.exclusive_group)
        group_usage = " | ".join(spec.usage_fragment(bracket_optional=False) for spec in group_specs)
        if all(not spec.required for spec in group_specs):
            group_usage = f"[{group_usage}]"
        parts.append(group_usage)
        rendered_groups.add(arg_spec.exclusive_group)
    return parts
