from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib
from typing import Mapping


APP_DIRNAME = ".adc"
DB_FILE_NAME = "agent-data-cli.db"
LAUNCHER_FILE_NAME = "launcher.toml"


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    home: Path
    db_path: Path
    source_workspace: Path
    runtime_dir: Path
    launcher_path: Path


def resolve_runtime_paths(
    *,
    user_home: Path | None = None,
    env: Mapping[str, str] | None = None,
    home_override: str | Path | None = None,
    source_workspace_override: str | Path | None = None,
) -> RuntimePaths:
    resolved_env = dict(os.environ if env is None else env)
    resolved_user_home = Path.home() if user_home is None else Path(user_home)
    default_home = resolved_user_home / APP_DIRNAME
    launcher_path = default_home / LAUNCHER_FILE_NAME

    home = _resolve_home(
        default_home=default_home,
        launcher_path=launcher_path,
        env=resolved_env,
        home_override=home_override,
    )
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
        launcher_path=launcher_path,
    )


def is_initialized(paths: RuntimePaths) -> bool:
    return paths.db_path.exists()


def write_launcher_home(launcher_path: Path, home: Path) -> None:
    launcher_path.parent.mkdir(parents=True, exist_ok=True)
    launcher_path.write_text(f'home = "{home}"\n', encoding="utf-8")


def _resolve_home(
    *,
    default_home: Path,
    launcher_path: Path,
    env: Mapping[str, str],
    home_override: str | Path | None,
) -> Path:
    if home_override is not None:
        return Path(home_override).expanduser()
    env_home = env.get("ADC_HOME")
    if env_home:
        return Path(env_home).expanduser()
    launcher_home = _read_launcher_home(launcher_path)
    if launcher_home is not None:
        return launcher_home
    return default_home


def _read_launcher_home(launcher_path: Path) -> Path | None:
    if not launcher_path.exists():
        return None
    data = tomllib.loads(launcher_path.read_text(encoding="utf-8"))
    home = data.get("home")
    if not isinstance(home, str) or not home.strip():
        return None
    return Path(home).expanduser()
