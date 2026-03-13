from __future__ import annotations

import time
from datetime import datetime

from core.base import BaseSource
from core.config import SourceConfigError
from core.manifest import (
    ActionOptionSpec,
    ConfigFieldSpec,
    ConfigRequirement,
    DocsSpec,
    InteractionParamSpec,
    InteractionVerbSpec,
    QuerySpec,
    SourceActionSpec,
    SourceIdentity,
    SourceManifest,
    StorageSpec,
)
from core.models import (
    ChannelRecord,
    ContentRecord,
    HealthRecord,
    InteractionResult,
    QueryColumnSpec,
    QueryViewSpec,
    SearchColumnSpec,
    SearchResult,
    SearchViewSpec,
    parse_content_ref as parse_core_content_ref,
)
from core.protocol import AuthRequiredError
from core.source_defaults import proxy_url_config
from utils.time import utc_now_iso

from .client import XiaohongshuClient
from .cookies import parse_cookie_header
from .normalize import (
    content_record_from_note,
    note_iso_time,
    note_search_items,
    paged_user_notes,
    parse_note_opaque_id,
    parse_user_channel_key,
    search_result_from_note,
    user_channel_record,
)


COOKIE_REQUIREMENT = (ConfigRequirement(keys=("cookie",), reason="requires authenticated cookie"),)


class XiaohongshuSource(BaseSource):
    name = "xiaohongshu"
    display_name = "Xiaohongshu"
    description = "Xiaohongshu user channels, note search, sync, and interactions"

    def health(self) -> HealthRecord:
        started_at = time.perf_counter()
        with self._client() as client:
            profile = client.get_self_info()
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        nickname = str(profile.get("nickname") or profile.get("basic_info", {}).get("nickname") or "").strip()
        details = "xiaohongshu authenticated API reachable"
        if nickname:
            details = f"{details} as {nickname}"
        return HealthRecord(
            source=self.name,
            status="ok",
            checked_at=utc_now_iso(),
            latency_ms=latency_ms,
            error=None,
            details=details,
        )

    def get_channel(self, channel_key: str) -> ChannelRecord:
        user_id = parse_user_channel_key(channel_key)
        normalized_key = f"user/{user_id}"
        if self.store is not None:
            stored = self.store.get_channel(self.name, normalized_key)
            if stored is not None:
                return stored
        return ChannelRecord(
            source=self.name,
            channel_id=user_id,
            channel_key=normalized_key,
            display_name=normalized_key,
            url=f"https://www.xiaohongshu.com/user/profile/{user_id}",
            metadata={"user_id": user_id},
        )

    def search_channels(self, query: str, limit: int = 20) -> list[ChannelRecord]:
        normalized_query = query.strip()
        if not normalized_query or limit <= 0:
            return []
        with self._client() as client:
            payload = client.search_users(normalized_query)
        users = payload.get("users")
        if not isinstance(users, list):
            users = payload.get("user_info_dtos", [])
        if not isinstance(users, list):
            return []
        channels: list[ChannelRecord] = []
        for item in users:
            if not isinstance(item, dict):
                continue
            channels.append(user_channel_record(item))
            if len(channels) >= limit:
                break
        return channels

    def search_content(
        self,
        channel_key: str | None = None,
        query: str | None = None,
        since: datetime | None = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        if limit <= 0:
            return []
        if channel_key is None and query is None:
            return []
        if channel_key is not None and query is not None:
            raise RuntimeError("xiaohongshu content search accepts either --channel or --query")
        if channel_key is not None:
            notes = self._fetch_user_note_payloads(channel_key, since=since, limit=limit, fetch_all=False)
            return [search_result_from_note(note) for note in notes[:limit]]
        if since is not None:
            raise RuntimeError("xiaohongshu keyword content search does not support --since")
        with self._client() as client:
            # The live endpoint may omit `items` for very small page_size values.
            payload = client.search_notes(query.strip(), page=1, page_size=max(limit, 20))
        results = [search_result_from_note(item) for item in note_search_items(payload)]
        return results[:limit]

    def get_channel_search_view(self) -> SearchViewSpec | None:
        return SearchViewSpec(
            columns=[
                SearchColumnSpec("nickname", lambda item: item.metadata.get("nickname", item.display_name), max_width=18),
                SearchColumnSpec("red_id", lambda item: item.metadata.get("red_id", ""), max_width=18),
                SearchColumnSpec("channel_key", lambda item: item.channel_key, no_wrap=True, max_width=24),
                SearchColumnSpec("url", lambda item: item.url, no_wrap=True, max_width=56),
            ]
        )

    def get_content_search_view(self, channel_key: str | None) -> SearchViewSpec | None:
        _ = channel_key
        return SearchViewSpec(
            columns=[
                SearchColumnSpec("title", lambda item: item.title, max_width=24),
                SearchColumnSpec("author", lambda item: (item.metadata or {}).get("author", ""), max_width=16),
                SearchColumnSpec("published_at", lambda item: (item.metadata or {}).get("published_at", ""), no_wrap=True),
                SearchColumnSpec("url", lambda item: item.url, no_wrap=True, max_width=56),
            ]
        )

    def get_query_view(self, channel_key: str | None = None) -> QueryViewSpec | None:
        _ = channel_key
        return QueryViewSpec(
            columns=[
                QueryColumnSpec("published_at", lambda item: item.published_at or "", no_wrap=True),
                QueryColumnSpec("author", lambda item: item.author or "", max_width=16),
                QueryColumnSpec("channel_key", lambda item: item.channel_key, no_wrap=True, max_width=24),
                QueryColumnSpec("title", lambda item: item.title, max_width=24),
                QueryColumnSpec("url", lambda item: item.url, no_wrap=True, max_width=56),
            ]
        )

    def fetch_content(
        self,
        channel_key: str,
        since: datetime | None = None,
        limit: int | None = 20,
        fetch_all: bool = False,
    ) -> list[ContentRecord]:
        notes = self._fetch_user_note_payloads(
            channel_key,
            since=since,
            limit=20 if limit is None else limit,
            fetch_all=fetch_all,
        )
        return [content_record_from_note(channel_key, note) for note in notes]

    def parse_content_ref(self, ref: str) -> str:
        parsed = parse_core_content_ref(ref)
        if parsed.source != self.name:
            raise RuntimeError(f"content ref source mismatch: expected {self.name}, got {parsed.source}")
        return parse_note_opaque_id(parsed.opaque_id)

    def interact(self, verb: str, refs: list[str], params: dict[str, object]) -> list[InteractionResult]:
        results: list[InteractionResult] = []
        with self._client() as client:
            for note_id in refs:
                self._run_interaction(client, verb, note_id, params)
                results.append(InteractionResult(ref=note_id, verb=verb, status="ok"))
        return results

    def _fetch_user_note_payloads(
        self,
        channel_key: str,
        *,
        since: datetime | None,
        limit: int,
        fetch_all: bool,
    ) -> list[dict[str, object]]:
        user_id = parse_user_channel_key(channel_key)
        known_ids = self._known_note_ids(channel_key) if since is None and not fetch_all else set()
        since_iso = None if since is None else since.astimezone().isoformat()
        notes: list[dict[str, object]] = []
        cursor = ""
        stop_after_page = False
        with self._client() as client:
            while True:
                payload = client.get_user_notes(user_id, cursor=cursor)
                page_notes, has_more, next_cursor = paged_user_notes(payload)
                if not page_notes:
                    break
                for note in page_notes:
                    note = self._enrich_note_time(client, note)
                    note_id = str(note.get("note_id") or note.get("id") or "").strip()
                    if note_id and note_id in known_ids:
                        stop_after_page = True
                    note_time = note_iso_time(note)
                    if since_iso is not None and note_time is not None and note_time < since_iso:
                        stop_after_page = True
                        continue
                    notes.append(note)
                if not fetch_all and limit > 0 and len(notes) >= limit:
                    break
                if stop_after_page or not has_more or not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor
        if fetch_all or limit <= 0:
            return notes
        return notes[:limit]

    def _known_note_ids(self, channel_key: str) -> set[str]:
        if self.store is None:
            return set()
        rows = self.store.list_content(self.name, channel_key, limit=100)
        return {row.external_id for row in rows}

    def _client(self) -> XiaohongshuClient:
        cookie_header = self.config.get_str("cookie")
        if cookie_header is None:
            raise AuthRequiredError("xiaohongshu cookie is not configured")
        try:
            cookies = parse_cookie_header(cookie_header)
        except SourceConfigError as exc:
            raise AuthRequiredError(str(exc)) from exc
        proxy_url = self.config.get_str("proxy_url")
        return XiaohongshuClient(cookies=cookies, proxy_url=proxy_url)

    def _enrich_note_time(self, client: XiaohongshuClient, note: dict[str, object]) -> dict[str, object]:
        if note_iso_time(note) is not None:
            return note
        note_id = str(note.get("note_id") or note.get("id") or "").strip()
        xsec_token = str(note.get("xsec_token") or "").strip()
        if not note_id or not xsec_token:
            return note
        detail = client.get_note_detail(note_id, xsec_token=xsec_token)
        items = note_search_items(detail)
        if not items:
            return note
        return items[0]

    def _run_interaction(
        self,
        client: XiaohongshuClient,
        verb: str,
        note_id: str,
        params: dict[str, object],
    ) -> None:
        if verb == "like":
            client.like_note(note_id)
            return
        if verb == "unlike":
            client.unlike_note(note_id)
            return
        if verb == "favorite":
            client.favorite_note(note_id)
            return
        if verb == "unfavorite":
            client.unfavorite_note(note_id)
            return
        if verb == "comment":
            text = params.get("text")
            if not isinstance(text, str) or not text.strip():
                raise RuntimeError("xiaohongshu comment requires --text")
            client.post_comment(note_id, text)
            return
        raise RuntimeError(f"unsupported xiaohongshu verb: {verb}")


MANIFEST = SourceManifest(
    identity=SourceIdentity(
        name="xiaohongshu",
        display_name="Xiaohongshu",
        summary="Xiaohongshu user channels, note search, sync, and interactions",
    ),
    mode=None,
    config_fields=(
        ConfigFieldSpec(
            key="cookie",
            type="string",
            secret=True,
            description="Full Xiaohongshu Cookie header string",
            obtain_hint="Copy the complete Cookie request header from your browser devtools",
            example="a1=xxx; web_session=yyy; webId=zzz",
        ),
        proxy_url_config(),
    ),
    source_actions={
        "source.health": SourceActionSpec(
            name="source.health",
            summary="Validate the configured Xiaohongshu cookie",
            config_requirements=COOKIE_REQUIREMENT,
        ),
        "channel.search": SourceActionSpec(
            name="channel.search",
            summary="Search Xiaohongshu users as subscribable channels",
            options={
                "query": ActionOptionSpec(name="query"),
                "limit": ActionOptionSpec(name="limit"),
            },
            config_requirements=COOKIE_REQUIREMENT,
        ),
        "content.search": SourceActionSpec(
            name="content.search",
            summary="Search notes or preview a user channel remotely",
            options={
                "channel": ActionOptionSpec(name="channel"),
                "query": ActionOptionSpec(name="query"),
                "since": ActionOptionSpec(name="since"),
                "limit": ActionOptionSpec(name="limit"),
            },
            config_requirements=COOKIE_REQUIREMENT,
        ),
        "content.update": SourceActionSpec(
            name="content.update",
            summary="Sync subscribed Xiaohongshu user channels into the local store",
            options={
                "channel": ActionOptionSpec(name="channel"),
                "since": ActionOptionSpec(name="since"),
                "limit": ActionOptionSpec(name="limit"),
                "all": ActionOptionSpec(name="all"),
            },
            config_requirements=COOKIE_REQUIREMENT,
        ),
        "content.interact": SourceActionSpec(
            name="content.interact",
            summary="Run explicit note interactions",
            config_requirements=COOKIE_REQUIREMENT,
        ),
    },
    query=QuerySpec(time_field="published_at", supports_keywords=True),
    interaction_verbs={
        "like": InteractionVerbSpec(name="like", summary="Like a note"),
        "unlike": InteractionVerbSpec(name="unlike", summary="Unlike a note"),
        "favorite": InteractionVerbSpec(name="favorite", summary="Favorite a note"),
        "unfavorite": InteractionVerbSpec(name="unfavorite", summary="Unfavorite a note"),
        "comment": InteractionVerbSpec(
            name="comment",
            summary="Comment on a note",
            params=(
                InteractionParamSpec(
                    name="text",
                    type="string",
                    required=True,
                    description="Comment body text",
                ),
            ),
        ),
    },
    storage=StorageSpec(
        table_name="xiaohongshu_records",
        required_record_fields=(
            "source",
            "channel_key",
            "record_type",
            "external_id",
            "title",
            "url",
            "snippet",
            "published_at",
            "fetched_at",
            "raw_payload",
            "dedup_key",
            "content_ref",
        ),
    ),
    docs=DocsSpec(
        notes=(
            "channel_key uses user/<user_id>",
            "cookie must be the full Cookie request header string",
        ),
        examples=(
            "adc channel search --source xiaohongshu --query openai --limit 5",
            "adc sub add --source xiaohongshu --channel user/<user_id>",
            "adc content search --source xiaohongshu --query openai --limit 10",
            "adc content update --source xiaohongshu --channel user/<user_id> --limit 20",
            "adc content interact --source xiaohongshu --verb comment --ref xiaohongshu:content/note%3A123 --text hello",
        ),
    ),
)

SOURCE_CLASS = XiaohongshuSource
XiaohongshuSource.manifest = MANIFEST
