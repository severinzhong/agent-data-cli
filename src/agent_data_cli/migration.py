from __future__ import annotations

import shutil
from pathlib import Path

from agent_data_cli.runtime_paths import RuntimePaths
from agent_data_cli.store.db import Store


def migrate_source_workspace(current_paths: RuntimePaths, target_source_workspace: str | Path) -> RuntimePaths:
    new_source_workspace = Path(target_source_workspace).expanduser()
    if new_source_workspace == current_paths.source_workspace:
        return current_paths
    _ensure_target_directory_available(new_source_workspace)
    new_source_workspace.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(current_paths.source_workspace), str(new_source_workspace))
    store = Store(str(current_paths.db_path))
    store.set_cli_config("source_workspace", str(new_source_workspace), "path", False)
    return RuntimePaths(
        home=current_paths.home,
        db_path=current_paths.db_path,
        source_workspace=new_source_workspace,
        runtime_dir=current_paths.runtime_dir,
    )


def _ensure_target_directory_available(path: Path) -> None:
    if not path.exists():
        return
    if not path.is_dir():
        raise RuntimeError(f"target path is not a directory: {path}")
    if any(path.iterdir()):
        raise RuntimeError(f"target directory must be empty: {path}")
