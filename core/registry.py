from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.capabilities import CapabilityResolver
from core.config import (
    ConfigCheckItem,
    ResolvedSourceConfig,
    SourceConfigError,
    build_config_check_items,
    resolve_source_config,
)
from core.discovery import discover_source_modules
from core.manifest import ConfigFieldSpec, SourceManifest
from core.models import CapabilityStatus, SourceDescriptor, SourceStorageSpec
from store.db import Store

from .base import BaseSource


CLI_CONFIG_FIELDS: tuple[ConfigFieldSpec, ...] = (
    ConfigFieldSpec(
        key="source_workspace",
        type="path",
        secret=False,
        description="Source workspace root directory scanned for source packages",
        example="./sources",
    ),
    ConfigFieldSpec(
        key="proxy_url",
        type="proxy",
        secret=False,
        description="Default proxy URL inherited by sources that opt in. Leave unset to use environment proxy settings. Set direct to force direct connection.",
        example="http://127.0.0.1:7890 or direct",
    ),
    ConfigFieldSpec(
        key="default_user_agent",
        type="string",
        secret=False,
        description="Default user agent inherited by sources that opt in",
    ),
    ConfigFieldSpec(
        key="browser_profile_dir",
        type="path",
        secret=False,
        description="Default browser profile directory",
    ),
    ConfigFieldSpec(
        key="browser_ws_endpoint",
        type="url",
        secret=False,
        description="Browser websocket endpoint",
    ),
    ConfigFieldSpec(
        key="browser_binary",
        type="path",
        secret=False,
        description="Browser executable path",
    ),
    ConfigFieldSpec(
        key="headless",
        type="bool",
        secret=False,
        description="Default browser headless flag",
    ),
)

CLI_CONFIG_DEFAULTS: dict[str, str] = {
    "source_workspace": "./sources",
}


@dataclass(frozen=True, slots=True)
class SourceConfigCheck:
    source: str
    effective_mode: str | None
    action_status: CapabilityStatus | None
    verb_status: CapabilityStatus | None
    items: list[ConfigCheckItem]


@dataclass(frozen=True, slots=True)
class RegisteredSource:
    manifest: SourceManifest
    source_class: type[BaseSource]


class SourceRegistry:
    def __init__(self, store: Store | None) -> None:
        self.store = store
        self._sources: dict[str, RegisteredSource] = {}

    def register(self, source_class: type[BaseSource], manifest: SourceManifest | None = None) -> None:
        source_manifest = manifest or getattr(source_class, "manifest", None)
        if source_manifest is None:
            raise RuntimeError(f"{source_class.__name__} missing manifest")
        if source_class.name != source_manifest.identity.name:
            raise RuntimeError(
                f"source class name mismatch: {source_class.name} != {source_manifest.identity.name}"
            )
        if source_manifest.identity.name in self._sources:
            raise RuntimeError(f"source already registered: {source_manifest.identity.name}")
        self._sources[source_manifest.identity.name] = RegisteredSource(
            manifest=source_manifest,
            source_class=source_class,
        )

    def build(self, name: str) -> BaseSource:
        registered = self._require_source(name)
        config = self._resolve_source_config(registered)
        source = registered.source_class(store=self.store, config=config, manifest=registered.manifest)
        source.manifest = registered.manifest
        return source

    def list_names(self) -> list[str]:
        return sorted(self._sources)

    def list_descriptors(self) -> list[SourceDescriptor]:
        descriptors: list[SourceDescriptor] = []
        for name in self.list_names():
            registered = self._sources[name]
            config = self._resolve_source_config(registered)
            resolved_mode = self._resolve_mode(registered, config)
            resolver = CapabilityResolver(
                manifest=registered.manifest,
                resolved_mode=resolved_mode,
                configured_keys=config.configured_keys(),
            )
            descriptors.append(
                SourceDescriptor(
                    name=registered.manifest.identity.name,
                    display_name=registered.manifest.identity.display_name,
                    summary=registered.manifest.identity.summary,
                    effective_mode=resolved_mode,
                    action_statuses={
                        "channel.search": resolver.action_status("channel.search"),
                        "content.search": resolver.action_status("content.search"),
                        "content.update": resolver.action_status("content.update"),
                        "content.query": resolver.action_status("content.query"),
                        "content.interact": resolver.action_status("content.interact"),
                    },
                )
            )
        return descriptors

    def list_storage_specs(self) -> list[SourceStorageSpec]:
        specs: list[SourceStorageSpec] = []
        for name in self.list_names():
            manifest = self._sources[name].manifest
            query = manifest.query
            specs.append(
                SourceStorageSpec(
                    source=manifest.identity.name,
                    table_name=manifest.storage.table_name,
                    required_record_fields=manifest.storage.required_record_fields,
                    time_field=None if query is None else query.time_field,
                    supports_keywords=True if query is None else query.supports_keywords,
                )
            )
        return specs

    def get_storage_spec(self, name: str) -> SourceStorageSpec:
        for spec in self.list_storage_specs():
            if spec.source == name:
                return spec
        raise RuntimeError(f"unknown source: {name}")

    def get_manifest(self, name: str) -> SourceManifest:
        return self._require_source(name).manifest

    def get_resolver(self, name: str) -> CapabilityResolver:
        registered = self._require_source(name)
        config = self._resolve_source_config(registered)
        return CapabilityResolver(
            manifest=registered.manifest,
            resolved_mode=self._resolve_mode(registered, config),
            configured_keys=config.configured_keys(),
        )

    def get_source_config_specs(self, name: str) -> tuple[ConfigFieldSpec, ...]:
        manifest = self._require_source(name).manifest
        return self._effective_source_config_specs(manifest)

    def get_source_config_field_spec(self, source_name: str, key: str) -> ConfigFieldSpec:
        for spec in self.get_source_config_specs(source_name):
            if spec.key == key:
                return spec
        raise SourceConfigError(f"unknown config key: {source_name}.{key}")

    def get_cli_config_field_spec(self, key: str) -> ConfigFieldSpec:
        for spec in CLI_CONFIG_FIELDS:
            if spec.key == key:
                return spec
        raise SourceConfigError(f"unknown cli config key: {key}")

    def get_cli_config_specs(self) -> tuple[ConfigFieldSpec, ...]:
        return CLI_CONFIG_FIELDS

    def get_cli_config_default(self, key: str) -> str | None:
        return CLI_CONFIG_DEFAULTS.get(key)

    def config_check(
        self,
        name: str,
        *,
        action_id: str | None = None,
        verb: str | None = None,
    ) -> SourceConfigCheck:
        registered = self._require_source(name)
        config = self._resolve_source_config(registered)
        effective_mode = self._resolve_mode(registered, config)
        resolver = CapabilityResolver(
            manifest=registered.manifest,
            resolved_mode=effective_mode,
            configured_keys=config.configured_keys(),
        )
        action_status = None if action_id is None else resolver.action_status(action_id)
        verb_status = None if verb is None else resolver.verb_status(verb)
        return SourceConfigCheck(
            source=name,
            effective_mode=effective_mode,
            action_status=action_status,
            verb_status=verb_status,
            items=build_config_check_items(self._effective_source_config_specs(registered.manifest), config),
        )

    def prune_undeclared_configs(self) -> None:
        if self.store is None:
            return
        self.store.prune_source_configs(
            {
                name: {spec.key for spec in self._effective_source_config_specs(registered.manifest)}
                for name, registered in self._sources.items()
            }
        )
        self.store.prune_cli_configs({spec.key for spec in CLI_CONFIG_FIELDS})

    def _effective_source_config_specs(self, manifest: SourceManifest) -> tuple[ConfigFieldSpec, ...]:
        mode_spec = manifest.mode
        if mode_spec is None:
            return manifest.config_fields
        return (
            ConfigFieldSpec(
                key="mode",
                type="enum",
                secret=False,
                description="Source execution mode",
                choices=mode_spec.values,
            ),
            *manifest.config_fields,
        )

    def _require_source(self, name: str) -> RegisteredSource:
        try:
            return self._sources[name]
        except KeyError as exc:
            raise RuntimeError(f"unknown source: {name}") from exc

    def _resolve_source_config(self, registered: RegisteredSource) -> ResolvedSourceConfig:
        source_entries = {}
        cli_entries = {}
        if self.store is not None:
            source_entries = self.store.get_source_config_map(registered.manifest.identity.name)
            cli_entries = self.store.get_cli_config_map()
        return resolve_source_config(
            source=registered.manifest.identity.name,
            specs=self._effective_source_config_specs(registered.manifest),
            source_entries=source_entries,
            cli_entries=cli_entries,
        )

    def _resolve_mode(self, registered: RegisteredSource, config: ResolvedSourceConfig) -> str | None:
        if registered.manifest.mode is None:
            return None
        source = registered.source_class(store=self.store, config=config, manifest=registered.manifest)
        resolved_mode = source.resolve_mode()
        if resolved_mode == "auto":
            raise RuntimeError(
                f"{registered.manifest.identity.name} resolve_mode() must return a concrete mode, got auto"
            )
        if resolved_mode not in registered.manifest.mode.values:
            raise RuntimeError(
                f"{registered.manifest.identity.name} resolved invalid mode: {resolved_mode}"
            )
        return resolved_mode

def build_default_registry(store: Store | None, sources_dir: Path | None = None) -> SourceRegistry:
    registry = SourceRegistry(store=store)
    resolved_sources_dir = sources_dir or _resolve_sources_dir(store)
    for discovered in discover_source_modules(resolved_sources_dir):
        source_class = discovered.source_class
        source_class.manifest = discovered.manifest
        registry.register(source_class, manifest=discovered.manifest)
    return registry


def _resolve_sources_dir(store: Store | None) -> Path:
    default_dir = Path("./sources")
    if store is None:
        return default_dir
    entry = store.get_cli_config_map().get("source_workspace")
    if entry is None:
        return default_dir
    return Path(entry.value).expanduser()
