from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
import re
from urllib.parse import quote_from_bytes, unquote_to_bytes


_CONTENT_REF_SOURCE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_UNRESERVED_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"


@dataclass(frozen=True, slots=True)
class ParsedContentRef:
    source: str
    opaque_id: str
    encoded_opaque_id: str


def build_content_ref(source: str, opaque_id: str) -> str:
    if not _CONTENT_REF_SOURCE_RE.fullmatch(source):
        raise ValueError(f"invalid content ref source: {source}")
    if opaque_id == "":
        raise ValueError("content ref opaque id cannot be empty")
    encoded_opaque_id = quote_from_bytes(opaque_id.encode("utf-8"), safe=_UNRESERVED_CHARS)
    return f"{source}:content/{encoded_opaque_id}"


def parse_content_ref(ref: str) -> ParsedContentRef:
    try:
        source, encoded_opaque_id = ref.split(":content/", 1)
    except ValueError as exc:
        raise ValueError(f"invalid content ref delimiter: {ref}") from exc
    if not _CONTENT_REF_SOURCE_RE.fullmatch(source):
        raise ValueError(f"invalid content ref source: {source}")
    if encoded_opaque_id == "":
        raise ValueError("content ref opaque id cannot be empty")
    _validate_percent_encoded_opaque_id(encoded_opaque_id)
    try:
        opaque_id = unquote_to_bytes(encoded_opaque_id).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"invalid content ref utf-8 payload: {encoded_opaque_id}") from exc
    return ParsedContentRef(
        source=source,
        opaque_id=opaque_id,
        encoded_opaque_id=encoded_opaque_id,
    )


def _validate_percent_encoded_opaque_id(encoded_opaque_id: str) -> None:
    index = 0
    while index < len(encoded_opaque_id):
        char = encoded_opaque_id[index]
        if char in _UNRESERVED_CHARS:
            index += 1
            continue
        if char != "%":
            raise ValueError(f"invalid content ref percent encoding: {encoded_opaque_id}")
        if index + 2 >= len(encoded_opaque_id):
            raise ValueError(f"invalid content ref percent encoding: {encoded_opaque_id}")
        pair = encoded_opaque_id[index + 1 : index + 3]
        if any(digit not in "0123456789abcdefABCDEF" for digit in pair):
            raise ValueError(f"invalid content ref percent encoding: {encoded_opaque_id}")
        index += 3


@dataclass(frozen=True, slots=True)
class CapabilityStatus:
    status: str
    missing_keys: tuple[str, ...] = ()
    reason: str = ""


@dataclass(slots=True)
class SourceDescriptor:
    name: str
    display_name: str
    summary: str
    effective_mode: str | None
    action_statuses: dict[str, CapabilityStatus] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SourceStorageSpec:
    source: str
    required_record_fields: tuple[str, ...]
    time_field: str | None
    supports_keywords: bool


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
class ContentNode:
    source: str
    content_key: str
    content_type: str
    external_id: str
    title: str
    url: str
    snippet: str
    author: str | None
    published_at: str | None
    fetched_at: str | None
    raw_payload: str
    content_ref: str | None = None


@dataclass(slots=True)
class ContentChannelLink:
    source: str
    channel_key: str
    content_key: str
    membership_kind: str
    linked_at: str | None = None


@dataclass(slots=True)
class ContentRelation:
    source: str
    from_content_key: str
    relation_type: str
    to_content_key: str
    relation_semantic: str | None = None
    position: int | None = None
    metadata_json: str = "{}"


@dataclass(slots=True)
class ContentSyncBatch:
    nodes: list[ContentNode]
    channel_links: list[ContentChannelLink]
    relations: list[ContentRelation]


@dataclass(frozen=True, slots=True)
class ContentBatchWriteResult:
    saved_nodes: int
    skipped_nodes: int
    saved_links: int
    saved_relations: int


@dataclass(slots=True)
class ContentQueryRow:
    source: str
    content_key: str
    content_type: str
    external_id: str
    title: str
    url: str
    snippet: str
    author: str | None
    published_at: str | None
    fetched_at: str | None
    raw_payload: str
    matched_channels: tuple[str, ...]
    content_ref: str | None = None

    @property
    def channel_key(self) -> str:
        if len(self.matched_channels) == 1:
            return self.matched_channels[0]
        return ""


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
    content_ref: str | None = None


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
    channel_key: str | None = None
    metadata: dict[str, str] | None = None
    content_ref: str | None = None


@dataclass(slots=True)
class UpdateSummary:
    source: str
    channel_key: str | None
    saved_count: int
    skipped_count: int


@dataclass(slots=True)
class InteractionResult:
    ref: str
    verb: str
    status: str
    error: str | None = None


@dataclass(slots=True)
class ActionAuditRecord:
    executed_at: str
    action: str
    source: str
    mode: str | None
    target_kind: str
    targets: tuple[str, ...]
    params_summary: str
    status: str
    error: str | None
    dry_run: bool


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
    getter: Callable[[ContentQueryRow], str]
    justify: str = "left"
    max_width: int | None = None
    no_wrap: bool = False


@dataclass(slots=True)
class QueryViewSpec:
    columns: list[QueryColumnSpec]


@dataclass(slots=True)
class SearchColumnSpec:
    header: str
    getter: Callable[[SearchResult | ChannelRecord], str]
    justify: str = "left"
    max_width: int | None = None
    no_wrap: bool = False


@dataclass(slots=True)
class SearchViewSpec:
    columns: list[SearchColumnSpec]
