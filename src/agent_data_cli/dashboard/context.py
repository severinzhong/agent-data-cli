from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_data_cli.core.registry import SourceRegistry, build_default_registry
from agent_data_cli.runtime_paths import resolve_runtime_paths
from agent_data_cli.store.db import Store


@dataclass(frozen=True, slots=True)
class DashboardContext:
    db_path: str
    store: Store
    registry: SourceRegistry


def build_dashboard_context(
    *,
    db_path: str | None = None,
    sources_dir: Path | None = None,
) -> DashboardContext:
    resolved_db_path = str(resolve_runtime_paths().db_path) if db_path is None else db_path
    Path(resolved_db_path).parent.mkdir(parents=True, exist_ok=True)
    store = Store(resolved_db_path)
    store.init_schema()
    registry = build_default_registry(store, sources_dir=sources_dir)
    store.init_schema(storage_specs=registry.list_storage_specs())
    return DashboardContext(db_path=resolved_db_path, store=store, registry=registry)
