from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from agent_data_cli.core.registry import build_default_registry
from agent_data_cli.fetchers.http import HttpFetcher
from agent_data_cli.hub.models import DEFAULT_HUB_INDEX, HubCatalogEntry
from agent_data_cli.runtime_paths import resolve_runtime_paths
from agent_data_cli.store.db import Store


class HubService:
    def __init__(self, store: Store) -> None:
        self.store = store

    def list_installed_rows(self) -> list[dict[str, object]]:
        registry = build_default_registry(self.store, sources_dir=self._workspace_path())
        rows: list[dict[str, object]] = []
        for descriptor in registry.list_descriptors():
            rows.append(
                {
                    "source_name": descriptor.name,
                    "summary": descriptor.summary,
                    "mode": descriptor.effective_mode or "",
                }
            )
        return rows

    def search_rows(self, *, query: str | None, limit: int) -> list[dict[str, object]]:
        entries = self._matching_entries(query)
        rows: list[dict[str, object]] = []
        for entry in entries[:limit]:
            rows.append(
                {
                    "source_name": entry.source_name,
                    "display_name": entry.display_name,
                    "summary": entry.summary,
                    "repo_url": entry.repo_url,
                    "version": entry.version,
                    "capabilities": ", ".join(entry.capabilities),
                }
            )
        return rows

    def install(self, source_name: str) -> None:
        entry = self._entry_by_source_name(source_name)
        workspace = self._workspace_path()
        target_dir = workspace / entry.source_name
        if target_dir.exists():
            raise RuntimeError(f"source already exists in workspace: {target_dir}")
        temp_root, staged_dir = self._stage_source(entry, temp_prefix="hub-install-")
        try:
            workspace.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staged_dir), str(target_dir))
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root)

    def update(self, source_name: str) -> None:
        entry = self._entry_by_source_name(source_name)
        workspace = self._workspace_path()
        target_dir = workspace / entry.source_name
        if not target_dir.is_dir():
            raise RuntimeError(f"source not installed in workspace: {target_dir}")
        temp_root, staged_dir = self._stage_source(entry, temp_prefix="hub-update-")
        backup_dir = workspace / f".{entry.source_name}.backup"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.move(str(target_dir), str(backup_dir))
        try:
            shutil.move(str(staged_dir), str(target_dir))
        except Exception:
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.move(str(backup_dir), str(target_dir))
            raise
        finally:
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            if temp_root.exists():
                shutil.rmtree(temp_root)

    def uninstall(self, source_name: str) -> None:
        target_dir = self._workspace_path() / source_name
        if not target_dir.is_dir():
            raise RuntimeError(f"source not installed in workspace: {target_dir}")
        self.store.purge_source_state(source_name)
        shutil.rmtree(target_dir)

    def _entry_by_source_name(self, source_name: str) -> HubCatalogEntry:
        for entry in self._load_index():
            if entry.source_name == source_name:
                return entry
        raise RuntimeError(f"unknown indexed source: {source_name}")

    def _matching_entries(self, query: str | None) -> list[HubCatalogEntry]:
        if query is None or not query.strip():
            return self._load_index()
        normalized = query.strip().lower()
        return [
            entry
            for entry in self._load_index()
            if normalized in entry.source_name.lower()
            or normalized in entry.display_name.lower()
            or normalized in entry.summary.lower()
        ]

    def _load_index(self) -> list[HubCatalogEntry]:
        locator = self._hub_index()
        if locator.startswith(("http://", "https://")):
            proxy_entry = self.store.get_cli_config_map().get("proxy_url")
            fetcher = HttpFetcher(proxy_url=None if proxy_entry is None else proxy_entry.value)
            try:
                payload = fetcher.get_json(locator)
            finally:
                fetcher.close()
        else:
            payload = json.loads(Path(locator).expanduser().read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise RuntimeError(f"hub index must be a list: {locator}")
        entries: list[HubCatalogEntry] = []
        for item in payload:
            if not isinstance(item, dict):
                raise RuntimeError(f"hub index entry must be an object: {locator}")
            capabilities = item.get("capabilities") or []
            if not isinstance(capabilities, list):
                raise RuntimeError(f"hub index capabilities must be a list: {item}")
            entries.append(
                HubCatalogEntry(
                    source_name=str(item["source_name"]).strip(),
                    display_name=str(item.get("display_name") or item["source_name"]).strip(),
                    summary=str(item.get("summary") or "").strip(),
                    repo_url=str(item["repo_url"]).strip(),
                    repo_subdir=str(item.get("repo_subdir") or item["source_name"]).strip(),
                    docs_url=str(item.get("docs_url") or item["repo_url"]).strip(),
                    version=str(item.get("version") or "unknown").strip(),
                    install_strategy=str(item.get("install_strategy") or "git_clone_subdir").strip(),
                    init_script=str(item.get("init_script") or "").strip(),
                    capabilities=tuple(str(capability).strip() for capability in capabilities),
                )
            )
        return entries

    def _hub_index(self) -> str:
        entry = self.store.get_cli_config_map().get("hub_index")
        if entry is None:
            return DEFAULT_HUB_INDEX
        return entry.value

    def _workspace_path(self) -> Path:
        entry = self.store.get_cli_config_map().get("source_workspace")
        if entry is not None:
            return Path(entry.value).expanduser()
        return resolve_runtime_paths().source_workspace

    def _stage_source(self, entry: HubCatalogEntry, *, temp_prefix: str) -> tuple[Path, Path]:
        if entry.install_strategy != "git_clone_subdir":
            raise RuntimeError(f"unsupported install strategy: {entry.install_strategy}")
        temp_root = Path(tempfile.mkdtemp(prefix=temp_prefix))
        repo_dir = temp_root / "repo"
        staged_workspace = temp_root / "workspace"
        staged_workspace.mkdir(parents=True, exist_ok=True)
        staged_dir = staged_workspace / entry.source_name
        self._run(["git", "clone", "--depth", "1", entry.repo_url, str(repo_dir)], cwd=staged_workspace)
        source_dir = repo_dir / entry.repo_subdir
        if not source_dir.is_dir():
            raise RuntimeError(f"source subdir not found in repo: {entry.repo_subdir}")
        shutil.copytree(source_dir, staged_dir)
        self._install_requirements(staged_dir)
        self._run_init_script(staged_dir, entry.init_script)
        self._validate_workspace_source(staged_workspace, entry.source_name)
        return temp_root, staged_dir

    def _install_requirements(self, source_dir: Path) -> None:
        requirements_file = source_dir / "requirements.txt"
        if not requirements_file.is_file():
            return
        self._run(["uv", "pip", "install", "-p", sys.executable, "-r", str(requirements_file)], cwd=source_dir)

    def _run_init_script(self, source_dir: Path, init_script: str) -> None:
        if not init_script:
            return
        script_path = source_dir / init_script
        if not script_path.is_file():
            raise RuntimeError(f"init script not found: {script_path}")
        self._run(["bash", str(script_path)], cwd=source_dir)

    def _validate_workspace_source(self, workspace: Path, source_name: str) -> None:
        self._run(
            [
                sys.executable,
                "-c",
                "from pathlib import Path; from agent_data_cli.core.registry import build_default_registry; "
                "registry = build_default_registry(store=None, sources_dir=Path(r'%s')); "
                "registry.build(%r)" % (str(workspace), source_name),
            ],
            cwd=Path(__file__).resolve().parents[2],
        )

    def _run(self, command: list[str], *, cwd: Path) -> None:
        result = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
        if result.returncode == 0:
            return
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise RuntimeError(message)
