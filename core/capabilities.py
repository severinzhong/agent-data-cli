from __future__ import annotations

from dataclasses import dataclass

from core.manifest import ConfigFieldSpec, SourceManifest
from core.models import CapabilityStatus


def _mode_matches(active_mode: str | None, allowed_modes: tuple[str, ...]) -> bool:
    if not allowed_modes:
        return True
    if active_mode is None:
        return False
    return active_mode in allowed_modes


def _requirement_applies(active_mode: str | None, for_modes: tuple[str, ...]) -> bool:
    if not for_modes:
        return True
    if active_mode is None:
        return False
    return active_mode in for_modes


@dataclass(frozen=True, slots=True)
class CapabilityResolver:
    manifest: SourceManifest
    resolved_mode: str | None
    configured_keys: set[str]

    def action_status(self, action_name: str) -> CapabilityStatus:
        if action_name == "content.query":
            if self.manifest.query is None:
                return CapabilityStatus(status="unsupported")
            return CapabilityStatus(status="supported")
        action = self.manifest.source_actions.get(action_name)
        if action is None:
            return CapabilityStatus(status="unsupported")
        if not _mode_matches(self.resolved_mode, action.supported_modes):
            return CapabilityStatus(status="mode_unsupported")
        missing_keys = self._missing_keys(action.config_requirements)
        if missing_keys:
            return CapabilityStatus(status="requires_config", missing_keys=missing_keys)
        return CapabilityStatus(status="supported")

    def option_status(self, action_name: str, option_name: str) -> CapabilityStatus:
        action_status = self.action_status(action_name)
        if action_status.status == "unsupported":
            return action_status
        action = self.manifest.source_actions[action_name]
        option = action.options.get(option_name)
        if option is None:
            return CapabilityStatus(status="unsupported")
        if not _mode_matches(self.resolved_mode, option.supported_modes):
            return CapabilityStatus(status="mode_unsupported")
        missing_keys = self._missing_keys(option.config_requirements)
        if missing_keys:
            return CapabilityStatus(status="requires_config", missing_keys=missing_keys)
        return CapabilityStatus(status="supported")

    def verb_status(self, verb_name: str) -> CapabilityStatus:
        action_status = self.action_status("content.interact")
        if action_status.status == "unsupported":
            return action_status
        verb = self.manifest.interaction_verbs.get(verb_name)
        if verb is None:
            return CapabilityStatus(status="unsupported")
        if not _mode_matches(self.resolved_mode, verb.supported_modes):
            return CapabilityStatus(status="mode_unsupported")
        missing_keys = self._missing_keys(verb.config_requirements)
        if missing_keys:
            return CapabilityStatus(status="requires_config", missing_keys=missing_keys)
        return CapabilityStatus(status="supported")

    def param_status(self, verb_name: str, param_name: str) -> CapabilityStatus:
        verb_status = self.verb_status(verb_name)
        if verb_status.status != "supported":
            return verb_status
        verb = self.manifest.interaction_verbs[verb_name]
        for param in verb.params:
            if param.name != param_name:
                continue
            if not _mode_matches(self.resolved_mode, param.for_modes):
                return CapabilityStatus(status="mode_unsupported")
            return CapabilityStatus(status="supported")
        return CapabilityStatus(status="unsupported")

    def visible_config_fields(self) -> tuple[ConfigFieldSpec, ...]:
        fields: list[ConfigFieldSpec] = []
        for field_spec in self.manifest.config_fields:
            if not _mode_matches(self.resolved_mode, field_spec.for_modes):
                continue
            fields.append(field_spec)
        return tuple(fields)

    def _missing_keys(self, requirements) -> tuple[str, ...]:
        missing: list[str] = []
        for requirement in requirements:
            if not _requirement_applies(self.resolved_mode, requirement.for_modes):
                continue
            for key in requirement.keys:
                if key in self.configured_keys or key in missing:
                    continue
                missing.append(key)
        return tuple(missing)
