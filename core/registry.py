from __future__ import annotations

from core.config import build_config_check_items, resolve_source_config
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

    def build(self, name: str) -> BaseSource:
        try:
            source_class = self._source_classes[name]
        except KeyError as exc:
            raise RuntimeError(f"unknown source: {name}") from exc
        config = self._resolve_config(source_class)
        return source_class(store=self.store, config=config)

    def list_names(self) -> list[str]:
        return sorted(self._source_classes)

    def list_descriptors(self):
        return [self.build(name).describe() for name in self.list_names()]

    def config_check(self, name: str):
        try:
            source_class = self._source_classes[name]
        except KeyError as exc:
            raise RuntimeError(f"unknown source: {name}") from exc
        entries = {}
        if self.store is not None:
            entries = self.store.get_source_config_map(name)
        return build_config_check_items(source_class.config_spec(), entries)

    def _resolve_config(self, source_class: type[BaseSource]):
        entries = {}
        if self.store is not None:
            entries = self.store.get_source_config_map(source_class.name)
        return resolve_source_config(
            source=source_class.name,
            specs=source_class.config_spec(),
            entries=entries,
        )


def build_default_registry(store: Store | None) -> SourceRegistry:
    from sources.ashare.source import AShareSource
    from sources.bbc.source import BbcSource
    from sources.hackernews.source import HackerNewsSource

    registry = SourceRegistry(store=store)
    registry.register(AShareSource)
    registry.register(BbcSource)
    registry.register(HackerNewsSource)
    return registry
