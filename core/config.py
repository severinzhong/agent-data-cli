from __future__ import annotations

import json
from dataclasses import dataclass


class SourceConfigError(RuntimeError):
    pass


@dataclass(slots=True)
class ConfigFieldSpec:
    key: str
    value_type: str = "string"
    required: bool = False
    secret: bool = False
    description: str = ""


@dataclass(slots=True)
class SourceConfigEntry:
    source: str
    key: str
    value: str
    value_type: str
    is_secret: bool
    updated_at: str


@dataclass(slots=True)
class ConfigCheckItem:
    key: str
    required: bool
    configured: bool
    value_type: str
    secret: bool
    description: str


class ResolvedSourceConfig:
    def __init__(self, source: str, entries: dict[str, SourceConfigEntry]) -> None:
        self.source = source
        self._entries = entries

    @classmethod
    def empty(cls, source: str) -> ResolvedSourceConfig:
        return cls(source=source, entries={})

    def get(self, key: str, default: object | None = None):
        entry = self._entries.get(key)
        if entry is None:
            return default
        return _parse_entry_value(entry)

    def get_bool(self, key: str, default: bool = False) -> bool:
        entry = self._entries.get(key)
        if entry is None:
            return default
        value = _parse_entry_value(entry)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        raise SourceConfigError(f"invalid boolean config for {self.source}.{key}")

    def entries(self) -> dict[str, SourceConfigEntry]:
        return dict(self._entries)


def build_config_check_items(
    specs: list[ConfigFieldSpec],
    entries: dict[str, SourceConfigEntry],
) -> list[ConfigCheckItem]:
    return [
        ConfigCheckItem(
            key=spec.key,
            required=spec.required,
            configured=spec.key in entries,
            value_type=spec.value_type,
            secret=spec.secret,
            description=spec.description,
        )
        for spec in specs
    ]


def resolve_source_config(
    source: str,
    specs: list[ConfigFieldSpec],
    entries: dict[str, SourceConfigEntry],
    required_keys: tuple[str, ...] | None = None,
) -> ResolvedSourceConfig:
    spec_keys = {spec.key for spec in specs}
    if required_keys is None:
        required_keys = tuple(spec.key for spec in specs if spec.required)
    unknown_required = [key for key in required_keys if key not in spec_keys]
    if unknown_required:
        raise SourceConfigError(
            f"unknown required config keys for {source}: {','.join(unknown_required)}"
        )
    for spec in specs:
        entry = entries.get(spec.key)
        if entry is not None and entry.value_type != spec.value_type:
            raise SourceConfigError(
                f"config type mismatch for {source}.{spec.key}: "
                f"expected {spec.value_type}, got {entry.value_type}"
            )
    for key in required_keys:
        if key not in entries:
            raise SourceConfigError(f"missing required config: {source}.{key}")
    return ResolvedSourceConfig(source=source, entries=entries)


def _parse_entry_value(entry: SourceConfigEntry):
    if entry.value_type == "json":
        return json.loads(entry.value)
    if entry.value_type == "bool":
        normalized = entry.value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise SourceConfigError(f"invalid boolean config for {entry.source}.{entry.key}")
    return entry.value
