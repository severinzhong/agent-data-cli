from __future__ import annotations

from cli.commands.content.interact import CONTENT_INTERACT_COMMAND, run_content_interact
from cli.commands.content.query import CONTENT_QUERY_COMMAND, run_content_query
from cli.commands.content.search import CONTENT_SEARCH_COMMAND, run_content_search
from cli.commands.content.update import CONTENT_UPDATE_COMMAND, run_content_update
from cli.commands.content.common import resolve_query_view
from cli.commands.specs import CommandNodeSpec


CONTENT_COMMAND = CommandNodeSpec(
    name="content",
    summary="统一内容操作入口。",
    child_dest="content_command",
    children=(
        CONTENT_SEARCH_COMMAND,
        CONTENT_UPDATE_COMMAND,
        CONTENT_QUERY_COMMAND,
        CONTENT_INTERACT_COMMAND,
    ),
)


__all__ = [
    "CONTENT_COMMAND",
    "resolve_query_view",
    "run_content_interact",
    "run_content_query",
    "run_content_search",
    "run_content_update",
]
