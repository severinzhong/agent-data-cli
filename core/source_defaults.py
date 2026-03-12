from __future__ import annotations

from core.manifest import ConfigFieldSpec


def proxy_url_config() -> ConfigFieldSpec:
    return ConfigFieldSpec(
        key="proxy_url",
        type="url",
        secret=False,
        description="Proxy URL used by this source",
        inherits_from_cli="proxy_url",
    )


def default_user_agent_config(*, description: str = "Custom user agent") -> ConfigFieldSpec:
    return ConfigFieldSpec(
        key="user_agent",
        type="string",
        secret=False,
        description=description,
        inherits_from_cli="default_user_agent",
    )
