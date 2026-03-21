from __future__ import annotations

import json
from dataclasses import dataclass

from agent_data_cli.core.manifest import ConfigFieldSpec


class SourceConfigError(RuntimeError):
    pass


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
    configured: bool
    inherited: bool
    value_type: str
    secret: bool
    description: str
    obtain_hint: str
    example: str
    choices: tuple[str, ...]


class ResolvedSourceConfig:
    def __init__(
        self,
        source: str,
        entries: dict[str, SourceConfigEntry],
        explicit_keys: set[str] | None = None,
        inherited_keys: set[str] | None = None,
    ) -> None:
        self.source = source
        self._entries = entries
        self._explicit_keys = explicit_keys or set(entries)
        self._inherited_keys = inherited_keys or set()

    @classmethod
    def empty(cls, source: str) -> ResolvedSourceConfig:
        return cls(source=source, entries={}, explicit_keys=set(), inherited_keys=set())

    def get(self, key: str, default: object | None = None):
        entry = self._entries.get(key)
        if entry is None:
            return default
        return _parse_entry_value(entry)

    def get_str(self, key: str, default: str | None = None) -> str | None:
        value = self.get(key, default)
        if value is None:
            return None
        if not isinstance(value, str):
            raise SourceConfigError(f"invalid string config for {self.source}.{key}")
        return value

    def get_int(self, key: str, default: int = 0) -> int:
        value = self.get(key, default)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value)
        raise SourceConfigError(f"invalid int config for {self.source}.{key}")

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        raise SourceConfigError(f"invalid bool config for {self.source}.{key}")

    def entries(self) -> dict[str, SourceConfigEntry]:
        return dict(self._entries)

    def explicit_keys(self) -> set[str]:
        return set(self._explicit_keys)

    def inherited_keys(self) -> set[str]:
        return set(self._inherited_keys)

    def configured_keys(self) -> set[str]:
        return set(self._entries)

    def is_explicit(self, key: str) -> bool:
        return key in self._explicit_keys

    def is_inherited(self, key: str) -> bool:
        return key in self._inherited_keys


def resolve_source_config(
    *,
    source: str,
    specs: tuple[ConfigFieldSpec, ...],
    source_entries: dict[str, SourceConfigEntry],
    cli_entries: dict[str, SourceConfigEntry],
) -> ResolvedSourceConfig:
    spec_map = {spec.key: spec for spec in specs}
    for key, entry in source_entries.items():
        spec = spec_map.get(key)
        if spec is None:
            raise SourceConfigError(f"unknown config key: {source}.{key}")
        _validate_entry_type(source, spec, entry)
    resolved_entries = dict(source_entries)
    inherited_keys: set[str] = set()
    for spec in specs:
        if spec.key in resolved_entries:
            continue
        if spec.inherits_from_cli is None:
            continue
        cli_entry = cli_entries.get(spec.inherits_from_cli)
        if cli_entry is None:
            continue
        _validate_cli_inheritance(source, spec, cli_entry)
        resolved_entries[spec.key] = SourceConfigEntry(
            source=source,
            key=spec.key,
            value=cli_entry.value,
            value_type=cli_entry.value_type,
            is_secret=cli_entry.is_secret,
            updated_at=cli_entry.updated_at,
        )
        inherited_keys.add(spec.key)
    return ResolvedSourceConfig(
        source=source,
        entries=resolved_entries,
        explicit_keys=set(source_entries),
        inherited_keys=inherited_keys,
    )


def validate_config_value(spec: ConfigFieldSpec, raw_value: str, *, owner: str) -> None:
    if spec.type == "proxy":
        if not raw_value.strip():
            raise SourceConfigError(f"invalid proxy config for {owner}.{spec.key}")
        return
    if spec.type == "enum":
        if raw_value not in spec.choices:
            raise SourceConfigError(f"invalid value for {owner}.{spec.key}: {raw_value}")
        return
    if spec.type == "int":
        try:
            int(raw_value)
        except ValueError as exc:
            raise SourceConfigError(f"invalid int config for {owner}.{spec.key}") from exc
        return
    if spec.type == "bool":
        normalized = raw_value.strip().lower()
        if normalized not in {"1", "true", "yes", "on", "0", "false", "no", "off"}:
            raise SourceConfigError(f"invalid bool config for {owner}.{spec.key}")
        return
    if spec.type == "json":
        try:
            json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise SourceConfigError(f"invalid json config for {owner}.{spec.key}") from exc


def build_config_check_items(
    specs: tuple[ConfigFieldSpec, ...],
    resolved: ResolvedSourceConfig,
) -> list[ConfigCheckItem]:
    items: list[ConfigCheckItem] = []
    for spec in specs:
        items.append(
            ConfigCheckItem(
                key=spec.key,
                configured=spec.key in resolved.configured_keys(),
                inherited=resolved.is_inherited(spec.key),
                value_type=spec.type,
                secret=spec.secret,
                description=spec.description,
                obtain_hint=spec.obtain_hint,
                example=spec.example,
                choices=spec.choices,
            )
        )
    return items


def _validate_entry_type(source: str, spec: ConfigFieldSpec, entry: SourceConfigEntry) -> None:
    if not _config_types_compatible(spec.type, entry.value_type):
        raise SourceConfigError(
            f"config type mismatch for {source}.{spec.key}: expected {spec.type}, got {entry.value_type}"
        )


def _validate_cli_inheritance(source: str, spec: ConfigFieldSpec, entry: SourceConfigEntry) -> None:
    if not _config_types_compatible(spec.type, entry.value_type):
        raise SourceConfigError(
            f"cli config type mismatch for {source}.{spec.key}: expected {spec.type}, got {entry.value_type}"
        )


def _config_types_compatible(expected: str, actual: str) -> bool:
    if actual == expected:
        return True
    if expected in {"url", "path", "enum", "proxy"} and actual == "string":
        return True
    if expected == "string" and actual in {"url", "path", "enum", "proxy"}:
        return True
    if expected == "proxy" and actual == "url":
        return True
    if expected == "url" and actual == "proxy":
        return True
    return False


def _parse_entry_value(entry: SourceConfigEntry):
    if entry.value_type == "json":
        return json.loads(entry.value)
    if entry.value_type == "int":
        return int(entry.value)
    if entry.value_type == "bool":
        normalized = entry.value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise SourceConfigError(f"invalid bool config for {entry.source}.{entry.key}")
    return entry.value
