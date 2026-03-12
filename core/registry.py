from __future__ import annotations

from core.config import ConfigFieldSpec, SourceConfigError, build_config_check_items, resolve_source_config
from core.models import SourceDescriptor, SourceStorageSpec
from store.db import Store

from .base import BaseSource


class SourceRegistry:
    def __init__(self, store: Store | None) -> None:
        self.store = store
        self._source_classes: dict[str, type[BaseSource]] = {}

    def register(self, source_class: type[BaseSource]) -> None:
        if source_class.name in self._source_classes:
            raise RuntimeError(f"source already registered: {source_class.name}")
        self._source_classes[source_class.name] = source_class

    def build(self, name: str, capability: str | None = None) -> BaseSource:
        try:
            source_class = self._source_classes[name]
        except KeyError as exc:
            raise RuntimeError(f"unknown source: {name}") from exc
        config = self._resolve_config(source_class, capability=capability)
        return source_class(store=self.store, config=config)

    def list_names(self) -> list[str]:
        return sorted(self._source_classes)

    def list_descriptors(self):
        descriptors = []
        for name in self.list_names():
            source_class = self._source_classes[name]
            entries = self._get_source_config_entries(source_class.name)
            search_missing = self._get_missing_required_config_keys(source_class, "search", entries)
            subscribe_missing = self._get_missing_required_config_keys(source_class, "subscribe", entries)
            update_missing = self._get_missing_required_config_keys(source_class, "update", entries)
            query_missing = self._get_missing_required_config_keys(source_class, "query", entries)
            missing_required = _merge_missing_keys(
                source_class.supports_search,
                search_missing,
                source_class.supports_subscriptions,
                subscribe_missing,
                source_class.supports_updates,
                update_missing,
                source_class.supports_query,
                query_missing,
            )
            descriptors.append(
                SourceDescriptor(
                    name=source_class.name,
                    display_name=source_class.display_name,
                    description=source_class.description,
                    supports_search=source_class.supports_search,
                    supports_subscriptions=source_class.supports_subscriptions,
                    supports_updates=source_class.supports_updates,
                    supports_query=source_class.supports_query,
                    search_missing_required_configs=tuple(search_missing),
                    subscribe_missing_required_configs=tuple(subscribe_missing),
                    update_missing_required_configs=tuple(update_missing),
                    query_missing_required_configs=tuple(query_missing),
                    required_config_ok=len(missing_required) == 0,
                    missing_required_configs=tuple(missing_required),
                )
            )
        return descriptors

    def get_storage_spec(self, name: str) -> SourceStorageSpec:
        return self.build(name).get_storage_spec()

    def list_storage_specs(self) -> list[SourceStorageSpec]:
        return [self.get_storage_spec(name) for name in self.list_names()]

    def config_check(self, name: str):
        try:
            source_class = self._source_classes[name]
        except KeyError as exc:
            raise RuntimeError(f"unknown source: {name}") from exc
        entries = {}
        if self.store is not None:
            entries = self.store.get_source_config_map(name)
        return build_config_check_items(source_class.config_spec(), entries)

    def get_config_field_spec(self, source_name: str, key: str) -> ConfigFieldSpec:
        try:
            source_class = self._source_classes[source_name]
        except KeyError as exc:
            raise RuntimeError(f"unknown source: {source_name}") from exc
        for spec in source_class.config_spec():
            if spec.key == key:
                return spec
        raise SourceConfigError(f"unknown config key: {source_name}.{key}")

    def prune_undeclared_configs(self) -> None:
        if self.store is None:
            return
        allowed_keys_by_source = {
            source_name: {spec.key for spec in source_class.config_spec()}
            for source_name, source_class in self._source_classes.items()
        }
        self.store.prune_source_configs(allowed_keys_by_source)

    def _resolve_config(
        self,
        source_class: type[BaseSource],
        capability: str | None = None,
    ):
        entries = self._get_source_config_entries(source_class.name)
        required_keys: tuple[str, ...] | None = None
        if capability is not None:
            required_keys = source_class.required_config_keys_for_capability(capability)
        return resolve_source_config(
            source=source_class.name,
            specs=source_class.config_spec(),
            entries=entries,
            required_keys=required_keys,
        )

    def _get_missing_required_config_keys(
        self,
        source_class: type[BaseSource],
        capability: str,
        entries: dict | None = None,
    ) -> list[str]:
        if entries is None:
            entries = self._get_source_config_entries(source_class.name)
        required_keys = source_class.required_config_keys_for_capability(capability)
        return [key for key in required_keys if key not in entries]

    def _get_source_config_entries(self, source_name: str):
        if self.store is None:
            return {}
        return self.store.get_source_config_map(source_name)


def _merge_missing_keys(*parts: bool | list[str]) -> list[str]:
    merged: list[str] = []
    include = False
    for part in parts:
        if isinstance(part, bool):
            include = part
            continue
        if not include:
            continue
        for key in part:
            if key not in merged:
                merged.append(key)
    return merged


def build_default_registry(store: Store | None) -> SourceRegistry:
    from sources.ashare.source import AShareSource
    from sources.bbc.source import BbcSource
    from sources.hackernews.source import HackerNewsSource
    from sources.rsshub.source import RsshubSource
    from sources.sina_finance_724.source import SinaFinance724Source

    registry = SourceRegistry(store=store)
    registry.register(AShareSource)
    registry.register(BbcSource)
    registry.register(HackerNewsSource)
    registry.register(RsshubSource)
    registry.register(SinaFinance724Source)
    return registry
