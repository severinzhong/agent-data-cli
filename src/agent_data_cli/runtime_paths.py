from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


APP_DIRNAME = ".adc"
DB_FILE_NAME = "agent-data-cli.db"


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    home: Path
    db_path: Path
    source_workspace: Path
    runtime_dir: Path


def resolve_runtime_paths(
    *,
    user_home: Path | None = None,
    env: Mapping[str, str] | None = None,
    source_workspace_override: str | Path | None = None,
) -> RuntimePaths:
    resolved_env = dict(os.environ if env is None else env)
    resolved_user_home = Path.home() if user_home is None else Path(user_home)
    default_home = resolved_user_home / APP_DIRNAME
    env_home = resolved_env.get("ADC_HOME")
    home = Path(env_home).expanduser() if env_home else default_home
    source_workspace = (
        Path(source_workspace_override).expanduser()
        if source_workspace_override is not None
        else home / "sources"
    )
    return RuntimePaths(
        home=home,
        db_path=home / DB_FILE_NAME,
        source_workspace=source_workspace,
        runtime_dir=home / "runtime",
    )


def is_initialized(paths: RuntimePaths) -> bool:
    return paths.db_path.exists()
