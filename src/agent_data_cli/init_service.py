from __future__ import annotations

from importlib import resources
import shutil

from agent_data_cli.runtime_paths import RuntimePaths, is_initialized, write_launcher_home
from agent_data_cli.store.db import Store


def initialize_runtime(paths: RuntimePaths, *, force: bool = False) -> None:
    if is_initialized(paths):
        if not force:
            raise RuntimeError("adc 已初始化，请改用 `adc config`")
        _reset_runtime(paths)

    paths.home.mkdir(parents=True, exist_ok=True)
    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    paths.source_workspace.mkdir(parents=True, exist_ok=True)
    write_launcher_home(paths.launcher_path, paths.home)
    store = Store(str(paths.db_path))
    store.init_schema()
    store.set_cli_config("home", str(paths.home), "path", False)
    store.set_cli_config("source_workspace", str(paths.source_workspace), "path", False)
    _bootstrap_data_hub(paths)


def _reset_runtime(paths: RuntimePaths) -> None:
    if paths.home.exists():
        shutil.rmtree(paths.home)
    if paths.source_workspace.exists() and not paths.source_workspace.is_relative_to(paths.home):
        shutil.rmtree(paths.source_workspace)


def _bootstrap_data_hub(paths: RuntimePaths) -> None:
    bootstrap_root = resources.files("agent_data_cli.bootstrap")
    data_hub_src = bootstrap_root.joinpath("data_hub")
    data_hub_dst = paths.source_workspace / "data_hub"
    if data_hub_dst.exists():
        shutil.rmtree(data_hub_dst)
    with resources.as_file(data_hub_src) as source_dir:
        shutil.copytree(source_dir, data_hub_dst)
    with resources.as_file(bootstrap_root.joinpath("sources.json")) as sources_index:
        shutil.copy2(sources_index, paths.source_workspace / "sources.json")
