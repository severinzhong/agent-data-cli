from __future__ import annotations

from typing import Protocol

from .help import HelpDoc
from .models import (
    ChannelRecord,
    HealthRecord,
    QueryViewSpec,
    SearchResult,
    SearchViewSpec,
    SourceDescriptor,
    SubscriptionRecord,
    UpdateSummary,
)


class UnsupportedCapabilityError(RuntimeError):
    pass


class ChannelNotFoundError(RuntimeError):
    pass


class SourceProtocol(Protocol):
    name: str
    display_name: str

    def describe(self) -> SourceDescriptor:
        raise NotImplementedError

    def health(self) -> HealthRecord:
        raise NotImplementedError

    def list_channels(self) -> list[ChannelRecord]:
        raise NotImplementedError

    def get_channel(self, channel_key: str) -> ChannelRecord:
        raise NotImplementedError

    def search(
        self,
        query: str,
        channel: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        raise NotImplementedError

    def get_search_view(self, kind: str) -> SearchViewSpec | None:
        raise NotImplementedError

    def query(
        self,
        channel_key: str,
        record_type: str | None = None,
        limit: int = 10,
        since: str | None = None,
        fetch_all: bool = False,
    ):
        raise NotImplementedError

    def get_query_view(self, record_type: str | None = None) -> QueryViewSpec | None:
        raise NotImplementedError

    def get_default_query_record_type(self) -> str | None:
        raise NotImplementedError

    def get_supported_record_types(self) -> tuple[str, ...]:
        raise NotImplementedError

    def get_help(self) -> HelpDoc | None:
        raise NotImplementedError

    def update(
        self,
        channel_key: str | None = None,
        record_type: str | None = None,
        limit: int = 10,
        since: str | None = None,
        fetch_all: bool = False,
    ) -> UpdateSummary:
        raise NotImplementedError

    def subscribe(self, channel_key: str) -> SubscriptionRecord:
        raise NotImplementedError

    def unsubscribe(self, channel_key: str) -> None:
        raise NotImplementedError

    def list_subscriptions(self) -> list[SubscriptionRecord]:
        raise NotImplementedError
