from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime

from core.base import BaseSource
from core.manifest import (
    ActionOptionSpec,
    ConfigFieldSpec,
    DocsSpec,
    InteractionVerbSpec,
    QuerySpec,
    SourceActionSpec,
    SourceIdentity,
    SourceManifest,
    StorageSpec,
)
from core.models import (
    ChannelRecord,
    ContentChannelLink,
    ContentNode,
    ContentRecord,
    ContentSyncBatch,
    HealthRecord,
    InteractionResult,
    QueryColumnSpec,
    QueryViewSpec,
    SearchColumnSpec,
    SearchResult,
    SearchViewSpec,
    build_content_ref,
    parse_content_ref,
)
from core.registry import build_default_registry
from utils.time import utc_now_iso


OFFICIAL_CHANNEL = "official"


@dataclass(frozen=True, slots=True)
class CatalogEntry:
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


class DataHubSource(BaseSource):
    name = "data_hub"
    display_name = "Data Hub"
    description = "Official source catalog and source lifecycle entrypoint"

    def health(self) -> HealthRecord:
        started_at = time.perf_counter()
        entry_count = len(self._load_index())
        return HealthRecord(
            source=self.name,
            status="ok",
            checked_at=utc_now_iso(),
            latency_ms=int((time.perf_counter() - started_at) * 1000),
            error=None,
            details=f"loaded {entry_count} official source entries",
        )

    def list_channels(self) -> list[ChannelRecord]:
        return [
            ChannelRecord(
                source=self.name,
                channel_id=OFFICIAL_CHANNEL,
                channel_key=OFFICIAL_CHANNEL,
                display_name="Official",
                url="https://github.com/severinzhong/agent-data-hub",
                metadata={"kind": "catalog"},
            )
        ]

    def search_content(
        self,
        channel_key: str | None = None,
        query: str | None = None,
        since: datetime | None = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        _ = since
        normalized_channel = channel_key or OFFICIAL_CHANNEL
        if normalized_channel != OFFICIAL_CHANNEL:
            raise RuntimeError(f"{self.name} only supports channel: {OFFICIAL_CHANNEL}")
        entries = self._matching_entries(query)
        return [self._search_result_from_entry(entry) for entry in entries[:limit]]

    def get_content_search_view(self, channel_key: str | None) -> SearchViewSpec | None:
        if channel_key not in (None, OFFICIAL_CHANNEL):
            return None
        return SearchViewSpec(
            columns=[
                SearchColumnSpec("source_name", lambda item: (item.metadata or {}).get("source_name", "")),
                SearchColumnSpec("summary", lambda item: item.snippet, max_width=36),
                SearchColumnSpec("repo_url", lambda item: item.url, no_wrap=True, max_width=56),
            ]
        )

    def get_query_view(self, channel_key: str | None = None) -> QueryViewSpec | None:
        if channel_key not in (None, OFFICIAL_CHANNEL):
            return None
        return QueryViewSpec(
            columns=[
                QueryColumnSpec("source_name", lambda item: item.external_id),
                QueryColumnSpec("version", lambda item: self._payload_field(item, "version")),
                QueryColumnSpec("install_strategy", lambda item: self._payload_field(item, "install_strategy")),
                QueryColumnSpec("repo_url", lambda item: item.url, no_wrap=True, max_width=56),
            ]
        )

    def fetch_content(
        self,
        channel_key: str,
        since: datetime | None = None,
        limit: int | None = 20,
        fetch_all: bool = False,
    ) -> ContentSyncBatch:
        _ = since
        if channel_key != OFFICIAL_CHANNEL:
            raise RuntimeError(f"{self.name} only supports channel: {OFFICIAL_CHANNEL}")
        entries = self._load_index()
        if not fetch_all and limit is not None and limit >= 0:
            entries = entries[:limit]
        nodes = [self._content_node_from_entry(entry) for entry in entries]
        return ContentSyncBatch(
            nodes=nodes,
            channel_links=[
                ContentChannelLink(
                    source=self.name,
                    channel_key=OFFICIAL_CHANNEL,
                    content_key=node.content_key,
                    membership_kind="direct",
                )
                for node in nodes
            ],
            relations=[],
        )

    def parse_content_ref(self, ref: str) -> str:
        parsed = parse_content_ref(ref)
        if parsed.source != self.name:
            raise RuntimeError(f"content ref source mismatch: expected {self.name}, got {parsed.source}")
        return parsed.opaque_id

    def interact(self, verb: str, refs: list[str], params: dict[str, object]) -> list[InteractionResult]:
        _ = params
        if verb not in {"install", "uninstall"}:
            raise RuntimeError(f"unsupported verb: {self.name}.{verb}")
        results: list[InteractionResult] = []
        for source_name in refs:
            if verb == "install":
                self._install_source(source_name)
            else:
                self._uninstall_source(source_name)
            results.append(InteractionResult(ref=source_name, verb=verb, status="ok"))
        return results

    def _matching_entries(self, query: str | None) -> list[CatalogEntry]:
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

    def _search_result_from_entry(self, entry: CatalogEntry) -> SearchResult:
        return SearchResult(
            title=entry.display_name,
            url=entry.repo_url,
            snippet=entry.summary,
            source=self.name,
            channel_key=OFFICIAL_CHANNEL,
            metadata={
                "source_name": entry.source_name,
                "version": entry.version,
                "install_strategy": entry.install_strategy,
                "repo_subdir": entry.repo_subdir,
                "docs_url": entry.docs_url,
                "capabilities": ", ".join(entry.capabilities),
            },
            content_ref=build_content_ref(self.name, entry.source_name),
        )

    def _content_node_from_entry(self, entry: CatalogEntry) -> ContentNode:
        payload = {
            "source_name": entry.source_name,
            "display_name": entry.display_name,
            "summary": entry.summary,
            "repo_url": entry.repo_url,
            "repo_subdir": entry.repo_subdir,
            "docs_url": entry.docs_url,
            "version": entry.version,
            "install_strategy": entry.install_strategy,
            "init_script": entry.init_script,
            "capabilities": list(entry.capabilities),
        }
        return ContentNode(
            source=self.name,
            content_key=f"source:{entry.source_name}",
            content_type="source_index",
            external_id=entry.source_name,
            title=entry.display_name,
            url=entry.repo_url,
            snippet=entry.summary,
            author=None,
            published_at=utc_now_iso(),
            fetched_at=utc_now_iso(),
            raw_payload=json.dumps(payload, ensure_ascii=False),
            content_ref=build_content_ref(self.name, entry.source_name),
        )

    def _index_path(self) -> Path:
        configured = self.config.get_str("index_path")
        if configured is not None:
            return Path(configured).expanduser()
        return self._workspace_path() / "sources.json"

    def _workspace_path(self) -> Path:
        configured = self.config.get_str("workspace_path")
        return Path(configured or "./sources").expanduser()

    def _load_index(self) -> list[CatalogEntry]:
        index_path = self._index_path()
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise RuntimeError(f"{self.name} source index must be a list: {index_path}")
        entries: list[CatalogEntry] = []
        for item in payload:
            if not isinstance(item, dict):
                raise RuntimeError(f"{self.name} source index entry must be an object: {index_path}")
            capabilities = item.get("capabilities") or []
            if not isinstance(capabilities, list):
                raise RuntimeError(f"{self.name} source index capabilities must be a list: {item}")
            entries.append(
                CatalogEntry(
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

    def _install_source(self, source_name: str) -> None:
        entry = self._entry_by_source_name(source_name)
        if entry.install_strategy != "git_clone_subdir":
            raise RuntimeError(f"unsupported install strategy: {entry.install_strategy}")
        workspace = self._workspace_path()
        target_dir = workspace / entry.source_name
        if target_dir.exists():
            raise RuntimeError(f"source already exists in workspace: {target_dir}")
        workspace.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="data-hub-install-") as temp_dir:
            repo_dir = Path(temp_dir) / "repo"
            self._run(
                ["git", "clone", "--depth", "1", entry.repo_url, str(repo_dir)],
                cwd=workspace,
            )
            source_dir = repo_dir / entry.repo_subdir
            if not source_dir.is_dir():
                raise RuntimeError(f"source subdir not found in repo: {entry.repo_subdir}")
            shutil.copytree(source_dir, target_dir)
        requirements_file = target_dir / "requirements.txt"
        if requirements_file.is_file():
            self._run(
                ["uv", "pip", "install", "-p", sys.executable, "-r", str(requirements_file)],
                cwd=target_dir,
            )
        if entry.init_script:
            script_path = target_dir / entry.init_script
            if not script_path.is_file():
                raise RuntimeError(f"init script not found: {script_path}")
            self._run(["bash", str(script_path)], cwd=target_dir)
        self._run(
            [
                sys.executable,
                "-c",
                "from pathlib import Path; from core.registry import build_default_registry; "
                "build_default_registry(store=None, sources_dir=Path(r'%s'))" % str(workspace),
            ],
            cwd=Path(__file__).resolve().parents[2],
        )

    def _uninstall_source(self, source_name: str) -> None:
        entry = self._entry_by_source_name(source_name)
        target_dir = self._workspace_path() / entry.source_name
        if not target_dir.is_dir():
            raise RuntimeError(f"source not installed in workspace: {target_dir}")
        self._require_store().purge_source_state(entry.source_name)
        shutil.rmtree(target_dir)
        build_default_registry(store=None, sources_dir=self._workspace_path())

    def _entry_by_source_name(self, source_name: str) -> CatalogEntry:
        for entry in self._load_index():
            if entry.source_name == source_name:
                return entry
        raise RuntimeError(f"unknown indexed source: {source_name}")

    def _payload_field(self, record: ContentRecord, key: str) -> str:
        value = json.loads(record.raw_payload).get(key, "")
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        return str(value)

    def _run(self, command: list[str], *, cwd: Path) -> None:
        result = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
        if result.returncode == 0:
            return
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise RuntimeError(message)


MANIFEST = SourceManifest(
    identity=SourceIdentity(
        name="data_hub",
        display_name="Data Hub",
        summary="Official source catalog and source lifecycle entrypoint",
    ),
    mode=None,
    config_fields=(
        ConfigFieldSpec(
            key="workspace_path",
            type="path",
            secret=False,
            description="Workspace root where installed sources will be written",
            example="./sources",
            inherits_from_cli="source_workspace",
        ),
        ConfigFieldSpec(
            key="index_path",
            type="path",
            secret=False,
            description="Optional source index JSON path; leave unset to read <workspace_path>/sources.json",
            example="/abs/path/to/sources.json",
        ),
    ),
    source_actions={
        "source.health": SourceActionSpec(name="source.health", summary="Load the source index"),
        "channel.list": SourceActionSpec(name="channel.list", summary="List hub channels"),
        "content.search": SourceActionSpec(
            name="content.search",
            summary="Search official source entries",
            options={
                "channel": ActionOptionSpec(name="channel"),
                "query": ActionOptionSpec(name="query"),
                "limit": ActionOptionSpec(name="limit"),
            },
            examples=("adc content search --source data_hub --channel official --query rss",),
        ),
        "content.update": SourceActionSpec(
            name="content.update",
            summary="Sync official source entries to the local store",
            options={
                "channel": ActionOptionSpec(name="channel"),
                "limit": ActionOptionSpec(name="limit"),
                "all": ActionOptionSpec(name="all"),
            },
        ),
        "content.interact": SourceActionSpec(
            name="content.interact",
            summary="Install or uninstall a source entry in the workspace",
        ),
    },
    query=QuerySpec(time_field="published_at", supports_keywords=True),
    interaction_verbs={
        "install": InteractionVerbSpec(
            name="install",
            summary="Install the selected source into the configured workspace",
            examples=("adc content interact --source data_hub --verb install --ref data_hub:content/xiaohongshu",),
        ),
        "uninstall": InteractionVerbSpec(
            name="uninstall",
            summary="Uninstall the selected source from the configured workspace and clear local state",
            examples=("adc content interact --source data_hub --verb uninstall --ref data_hub:content/xiaohongshu",),
        ),
    },
    storage=StorageSpec(
        table_name="data_hub_records",
        required_record_fields=(
            "source",
            "content_key",
            "content_type",
            "external_id",
            "title",
            "url",
            "snippet",
            "published_at",
            "fetched_at",
            "raw_payload",
            "content_ref",
        ),
    ),
    docs=DocsSpec(
        notes=(
            "data_hub publishes official source index entries as content.",
            "Install and uninstall are explicit content.interact verbs and never run implicitly.",
        ),
        examples=(
            "adc content search --source data_hub --channel official --query xiaohongshu",
            "adc content interact --source data_hub --verb install --ref data_hub:content/xiaohongshu",
            "adc content interact --source data_hub --verb uninstall --ref data_hub:content/xiaohongshu",
        ),
    ),
)
SOURCE_CLASS = DataHubSource
DataHubSource.manifest = MANIFEST
