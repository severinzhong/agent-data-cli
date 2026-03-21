# Changelog

## 0.2.0

- Remove launcher-based ADC home indirection.
- ADC home now resolves only from `ADC_HOME`, otherwise defaults to `~/.adc`.
- Remove `config cli set home` and related home config behavior.
- Remove `init --home` and keep init focused on the active ADC home plus optional `source_workspace`.
- Document direct installation and dependency usage through `uv tool install` and `uv add`.
