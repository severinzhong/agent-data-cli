from __future__ import annotations

from agent_data_cli.cli.commands.content.interact import CONTENT_INTERACT_COMMAND, run_content_interact
from agent_data_cli.cli.commands.content.query import CONTENT_QUERY_COMMAND, run_content_query
from agent_data_cli.cli.commands.content.search import CONTENT_SEARCH_COMMAND, run_content_search
from agent_data_cli.cli.commands.content.update import CONTENT_UPDATE_COMMAND, run_content_update
from agent_data_cli.cli.commands.specs import CommandNodeSpec


CONTENT_COMMAND = CommandNodeSpec(
    name="content",
    summary="Unified content operations.",
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
    "run_content_interact",
    "run_content_query",
    "run_content_search",
    "run_content_update",
]
