from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .models import (
    ChannelRecord,
    ContentRecord,
    HealthRecord,
    InteractionResult,
    QueryViewSpec,
    SearchResult,
    SearchViewSpec,
    SourceStorageSpec,
    SubscriptionRecord,
    UpdateSummary,
)


class SourceError(RuntimeError):
    pass


class UnsupportedActionError(SourceError):
    pass


class UnsupportedOptionError(SourceError):
    pass


class MissingConfigError(SourceError):
    pass


class InvalidChannelError(SourceError):
    pass


class InvalidContentRefError(SourceError):
    pass


class AuthRequiredError(SourceError):
    pass


class RemoteExecutionError(SourceError):
    pass


ChannelNotFoundError = InvalidChannelError
UnsupportedCapabilityError = UnsupportedActionError


class SourceProtocol(Protocol):
    name: str
    display_name: str

    def describe(self):
        raise NotImplementedError

    def get_storage_spec(self) -> SourceStorageSpec:
        raise NotImplementedError

    def resolve_mode(self) -> str:
        raise NotImplementedError

    def health(self) -> HealthRecord:
        raise NotImplementedError

    def list_channels(self) -> list[ChannelRecord]:
        raise NotImplementedError

    def get_channel(self, channel_key: str) -> ChannelRecord:
        raise NotImplementedError

    def search_channels(self, query: str, limit: int = 20) -> list[ChannelRecord]:
        raise NotImplementedError

    def search_content(
        self,
        channel_key: str | None = None,
        query: str | None = None,
        since: datetime | None = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        raise NotImplementedError

    def get_channel_search_view(self) -> SearchViewSpec | None:
        raise NotImplementedError

    def get_content_search_view(self, channel_key: str | None) -> SearchViewSpec | None:
        raise NotImplementedError

    def fetch_content(
        self,
        channel_key: str,
        since: datetime | None = None,
        limit: int | None = 20,
        fetch_all: bool = False,
    ) -> list[ContentRecord]:
        raise NotImplementedError

    def get_query_view(self, channel_key: str | None = None) -> QueryViewSpec | None:
        raise NotImplementedError

    def update(
        self,
        channel_key: str | None = None,
        limit: int | None = 20,
        since: datetime | None = None,
        fetch_all: bool = False,
    ) -> UpdateSummary:
        raise NotImplementedError

    def subscribe(
        self,
        channel_key: str,
        display_name: str | None = None,
    ) -> SubscriptionRecord:
        raise NotImplementedError

    def unsubscribe(self, channel_key: str) -> None:
        raise NotImplementedError

    def list_subscriptions(self) -> list[SubscriptionRecord]:
        raise NotImplementedError

    def parse_content_ref(self, ref: str) -> str:
        raise NotImplementedError

    def interact(self, verb: str, refs: list[str], params: dict[str, object]) -> list[InteractionResult]:
        raise NotImplementedError
