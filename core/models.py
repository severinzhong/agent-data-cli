from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class SourceDescriptor:
    name: str
    display_name: str
    description: str
    supports_search: bool
    supports_subscriptions: bool
    supports_updates: bool
    supports_query: bool
    required_config_ok: bool = True
    missing_required_configs: tuple[str, ...] = ()


@dataclass(slots=True)
class SourceStorageSpec:
    source: str
    table_name: str
    record_schema: str
    supports_keywords: bool
    time_field: str


@dataclass(slots=True)
class ChannelRecord:
    source: str
    channel_id: str
    channel_key: str
    display_name: str
    url: str
    metadata: dict[str, str]


@dataclass(slots=True)
class SubscriptionRecord:
    subscription_id: int
    source: str
    channel_key: str
    display_name: str
    created_at: str
    last_updated_at: str | None
    enabled: bool
    metadata: dict[str, str]


@dataclass(slots=True)
class ContentRecord:
    source: str
    channel_key: str
    record_type: str
    external_id: str
    title: str
    url: str
    snippet: str
    author: str | None
    published_at: str | None
    fetched_at: str | None
    raw_payload: str
    dedup_key: str


@dataclass(slots=True)
class HealthRecord:
    source: str
    status: str
    checked_at: str
    latency_ms: int
    error: str | None
    details: str


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str
    result_kind: str
    channel_key: str | None = None
    metadata: dict[str, str] | None = None


@dataclass(slots=True)
class UpdateSummary:
    source: str
    channel_key: str | None
    record_type: str | None
    saved_count: int
    skipped_count: int


@dataclass(slots=True)
class GroupRecord:
    group_name: str
    created_at: str


@dataclass(slots=True)
class GroupMemberRecord:
    group_name: str
    member_type: str
    source: str
    channel_key: str | None


@dataclass(slots=True)
class QueryColumnSpec:
    header: str
    getter: Callable[[ContentRecord], str]
    justify: str = "left"
    max_width: int | None = None
    no_wrap: bool = False


@dataclass(slots=True)
class QueryViewSpec:
    columns: list[QueryColumnSpec]


@dataclass(slots=True)
class SearchColumnSpec:
    header: str
    getter: Callable[[SearchResult], str]
    justify: str = "left"
    max_width: int | None = None
    no_wrap: bool = False


@dataclass(slots=True)
class SearchViewSpec:
    columns: list[SearchColumnSpec]
