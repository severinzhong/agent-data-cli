from __future__ import annotations

from dataclasses import dataclass


DEFAULT_HUB_INDEX = "https://raw.githubusercontent.com/severinzhong/agent-data-hub/main/sources.json"


@dataclass(frozen=True, slots=True)
class HubCatalogEntry:
    source_name: str
    display_name: str
    summary: str
    repo_url: str
    repo_subdir: str
    docs_url: str
    version: str
    install_strategy: str
    init_script: str
    capabilities: tuple[str, ...]
