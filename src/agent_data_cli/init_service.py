from __future__ import annotations

import shutil

from agent_data_cli.runtime_paths import RuntimePaths, is_initialized
from agent_data_cli.store.db import Store


def initialize_runtime(paths: RuntimePaths, *, force: bool = False) -> None:
    if is_initialized(paths):
        if not force:
            raise RuntimeError("adc 已初始化，请改用 `adc config`")
        _reset_runtime(paths)

    paths.home.mkdir(parents=True, exist_ok=True)
    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    paths.source_workspace.mkdir(parents=True, exist_ok=True)
    with Store(str(paths.db_path)) as store:
        store.init_schema()
        store.set_cli_config("source_workspace", str(paths.source_workspace), "path", False)


def _reset_runtime(paths: RuntimePaths) -> None:
    if paths.home.exists():
        shutil.rmtree(paths.home)
    if paths.source_workspace.exists() and not paths.source_workspace.is_relative_to(paths.home):
        shutil.rmtree(paths.source_workspace)
