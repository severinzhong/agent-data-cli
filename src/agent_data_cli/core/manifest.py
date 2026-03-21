from __future__ import annotations

from dataclasses import dataclass, field
import re


SOURCE_ACTION_NAMES = {
    "source.health",
    "channel.list",
    "channel.search",
    "content.search",
    "content.update",
    "content.interact",
}
CORE_ACTION_NAMES = {
    "content.query",
}
SOURCE_OPTION_NAMES = {
    "channel",
    "query",
    "keywords",
    "since",
    "limit",
    "all",
}
TOP_LEVEL_COMMAND_NAMES = {
    "source",
    "channel",
    "content",
    "sub",
    "group",
    "config",
    "help",
}
RESERVED_PARAM_NAMES = {
    "source",
    "group",
    "channel",
    "query",
    "keywords",
    "since",
    "limit",
    "all",
    "jsonl",
    "csv",
    "dry_run",
    "verb",
    "ref",
    "help",
    "mode",
    "name",
}
CONFIG_FIELD_TYPES = {"string", "int", "bool", "enum", "url", "path", "json", "proxy"}
INTERACTION_PARAM_TYPES = {"string", "int", "bool", "enum", "path"}
IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def to_cli_flag(name: str) -> str:
    return f"--{name.replace('_', '-')}"


def _require_identifier(value: str, label: str) -> None:
    if not IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"invalid {label}: {value}")


def _require_modes_subset(values: tuple[str, ...], allowed: set[str], label: str) -> None:
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise ValueError(f"{label} references unknown modes: {', '.join(unknown)}")


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    name: str
    display_name: str
    summary: str

    def __post_init__(self) -> None:
        _require_identifier(self.name, "source name")
        if self.name in TOP_LEVEL_COMMAND_NAMES:
            raise ValueError(f"reserved source name: {self.name}")


@dataclass(frozen=True, slots=True)
class ModeChoice:
    value: str
    summary: str

    def __post_init__(self) -> None:
        _require_identifier(self.value, "mode value")


@dataclass(frozen=True, slots=True)
class ModeSpec:
    key: str
    default: str
    choices: tuple[ModeChoice, ...]

    def __post_init__(self) -> None:
        if self.key != "mode":
            raise ValueError("mode.key must be 'mode'")
        values = tuple(choice.value for choice in self.choices)
        if len(values) != len(set(values)):
            raise ValueError("duplicate mode choices")
        if self.default not in values:
            raise ValueError(f"mode default must be declared in choices: {self.default}")

    @property
    def values(self) -> tuple[str, ...]:
        return tuple(choice.value for choice in self.choices)


@dataclass(frozen=True, slots=True)
class ConfigFieldSpec:
    key: str
    type: str
    secret: bool
    description: str
    obtain_hint: str = ""
    example: str = ""
    choices: tuple[str, ...] = ()
    inherits_from_cli: str | None = None
    for_modes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_identifier(self.key, "config key")
        if self.type not in CONFIG_FIELD_TYPES:
            raise ValueError(f"unsupported config field type: {self.type}")
        if self.type == "enum" and not self.choices:
            raise ValueError(f"enum config field requires choices: {self.key}")
        if self.type != "enum" and self.choices:
            raise ValueError(f"only enum config field can declare choices: {self.key}")
        if self.inherits_from_cli is not None:
            _require_identifier(self.inherits_from_cli, "cli config key")


@dataclass(frozen=True, slots=True)
class ConfigRequirement:
    keys: tuple[str, ...]
    for_modes: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.keys:
            raise ValueError("config requirement keys cannot be empty")
        for key in self.keys:
            _require_identifier(key, "config requirement key")


@dataclass(frozen=True, slots=True)
class ActionOptionSpec:
    name: str
    supported_modes: tuple[str, ...] = ()
    config_requirements: tuple[ConfigRequirement, ...] = ()
    help_summary: str = ""

    def __post_init__(self) -> None:
        _require_identifier(self.name, "option name")
        if self.name not in SOURCE_OPTION_NAMES:
            raise ValueError(f"unsupported action option: {self.name}")


@dataclass(frozen=True, slots=True)
class SourceActionSpec:
    name: str
    summary: str
    supported_modes: tuple[str, ...] = ()
    options: dict[str, ActionOptionSpec] = field(default_factory=dict)
    config_requirements: tuple[ConfigRequirement, ...] = ()
    examples: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.name not in SOURCE_ACTION_NAMES:
            raise ValueError(f"unsupported source action: {self.name}")
        for option_name, spec in self.options.items():
            if option_name != spec.name:
                raise ValueError(f"action option key mismatch: {option_name} != {spec.name}")


@dataclass(frozen=True, slots=True)
class QuerySpec:
    time_field: str | None = "published_at"
    supports_keywords: bool = True

    def __post_init__(self) -> None:
        if self.time_field is not None:
            _require_identifier(self.time_field, "query time field")


@dataclass(frozen=True, slots=True)
class InteractionParamSpec:
    name: str
    type: str
    required: bool = False
    description: str = ""
    choices: tuple[str, ...] = ()
    multiple: bool = False
    for_modes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_identifier(self.name, "interaction param name")
        if self.name in RESERVED_PARAM_NAMES:
            raise ValueError(f"reserved interaction param name: {self.name}")
        if self.type not in INTERACTION_PARAM_TYPES:
            raise ValueError(f"unsupported interaction param type: {self.type}")
        if self.type == "enum" and not self.choices:
            raise ValueError(f"enum interaction param requires choices: {self.name}")
        if self.type != "enum" and self.choices:
            raise ValueError(f"only enum interaction param can declare choices: {self.name}")
        if self.type == "bool" and self.required:
            raise ValueError("bool interaction param cannot be required")
        if self.type == "bool" and self.multiple:
            raise ValueError("bool interaction param cannot be multiple")


@dataclass(frozen=True, slots=True)
class InteractionVerbSpec:
    name: str
    summary: str
    supported_modes: tuple[str, ...] = ()
    params: tuple[InteractionParamSpec, ...] = ()
    config_requirements: tuple[ConfigRequirement, ...] = ()
    examples: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_identifier(self.name, "interaction verb name")
        param_names = tuple(param.name for param in self.params)
        if len(param_names) != len(set(param_names)):
            raise ValueError(f"duplicate interaction params in verb: {self.name}")


@dataclass(frozen=True, slots=True)
class StorageSpec:
    table_name: str
    required_record_fields: tuple[str, ...]
    unique_key_fields: tuple[str, ...] = ("source", "content_key")

    def __post_init__(self) -> None:
        _require_identifier(self.table_name, "storage table name")
        required_minimum = {"source", "content_key", "content_type", "title", "url", "fetched_at", "raw_payload"}
        missing = sorted(required_minimum - set(self.required_record_fields))
        if missing:
            raise ValueError(f"storage.required_record_fields missing: {', '.join(missing)}")


@dataclass(frozen=True, slots=True)
class DocsSpec:
    notes: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceManifest:
    identity: SourceIdentity
    mode: ModeSpec | None
    config_fields: tuple[ConfigFieldSpec, ...]
    source_actions: dict[str, SourceActionSpec]
    query: QuerySpec | None
    interaction_verbs: dict[str, InteractionVerbSpec]
    storage: StorageSpec
    docs: DocsSpec | None = None

    def __post_init__(self) -> None:
        mode_values = set(self.mode.values) if self.mode is not None else set()
        config_keys = [field.key for field in self.config_fields]
        if len(config_keys) != len(set(config_keys)):
            raise ValueError("duplicate config field keys")
        if "mode" in config_keys:
            raise ValueError("mode is implicit and must not be declared in config_fields")
        for field_spec in self.config_fields:
            if self.mode is None and field_spec.for_modes:
                raise ValueError(f"config field {field_spec.key} declares for_modes without mode")
            if self.mode is not None:
                _require_modes_subset(field_spec.for_modes, mode_values, f"config field {field_spec.key}")
        for action_name, action in self.source_actions.items():
            if action_name != action.name:
                raise ValueError(f"source action key mismatch: {action_name} != {action.name}")
            if self.mode is None and action.supported_modes:
                raise ValueError(f"action {action.name} declares supported_modes without mode")
            if self.mode is not None:
                _require_modes_subset(action.supported_modes, mode_values, f"action {action.name}")
            for option in action.options.values():
                if self.mode is None and option.supported_modes:
                    raise ValueError(f"option {action.name}.{option.name} declares supported_modes without mode")
                if self.mode is not None:
                    _require_modes_subset(
                        option.supported_modes,
                        mode_values,
                        f"option {action.name}.{option.name}",
                    )
                for requirement in option.config_requirements:
                    self._validate_config_requirement(requirement, mode_values, config_keys)
            for requirement in action.config_requirements:
                self._validate_config_requirement(requirement, mode_values, config_keys)
        for verb_name, verb in self.interaction_verbs.items():
            if verb_name != verb.name:
                raise ValueError(f"interaction verb key mismatch: {verb_name} != {verb.name}")
            if self.mode is None and verb.supported_modes:
                raise ValueError(f"verb {verb.name} declares supported_modes without mode")
            if self.mode is not None:
                _require_modes_subset(verb.supported_modes, mode_values, f"verb {verb.name}")
            for param in verb.params:
                if self.mode is None and param.for_modes:
                    raise ValueError(f"param {verb.name}.{param.name} declares for_modes without mode")
                if self.mode is not None:
                    _require_modes_subset(param.for_modes, mode_values, f"param {verb.name}.{param.name}")
            for requirement in verb.config_requirements:
                self._validate_config_requirement(requirement, mode_values, config_keys)
        if "content.interact" in self.source_actions and "content_ref" not in self.storage.required_record_fields:
            raise ValueError("source with content.interact requires content_ref in storage.required_record_fields")
        if self.query is not None and self.query.time_field is not None and self.query.time_field not in self.storage.required_record_fields:
            raise ValueError(f"query.time_field must exist in storage.required_record_fields: {self.query.time_field}")

    def _validate_config_requirement(
        self,
        requirement: ConfigRequirement,
        mode_values: set[str],
        config_keys: list[str],
    ) -> None:
        declared_config_keys = set(config_keys)
        declared_config_keys.add("mode")
        unknown = sorted(set(requirement.keys) - declared_config_keys)
        if unknown:
            raise ValueError(f"unknown config requirement keys: {', '.join(unknown)}")
        if self.mode is None and requirement.for_modes:
            raise ValueError("config requirement declares for_modes without mode")
        if self.mode is not None:
            _require_modes_subset(requirement.for_modes, mode_values, "config requirement")
