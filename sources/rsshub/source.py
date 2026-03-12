from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from urllib.parse import urlsplit

from core.base import BaseSource
from core.config import ConfigFieldSpec, SourceConfigError
from core.help import HelpDoc, HelpSection
from core.models import (
    ChannelRecord,
    ContentRecord,
    HealthRecord,
    SearchColumnSpec,
    SearchResult,
    SearchViewSpec,
    SourceStorageSpec,
)
from core.protocol import ChannelNotFoundError
from utils.text import clean_text
from utils.time import rfc2822_to_iso, utc_now_iso


_TEMPLATE_TOKEN_RE = re.compile(r"/:[^/]+")


class RsshubSource(BaseSource):
    name = "rsshub"
    display_name = "RSSHub"
    description = "RSSHub routes as channels"
    supports_search = True
    supports_updates = True
    supports_query = True
    DEFAULT_BASE_URL = "https://rsshub.isrss.com"
    # Alternative public instances (manual switch only, no auto fallback):
    # DEFAULT_BASE_URL = "https://rsshub.ktachibana.party"
    # DEFAULT_BASE_URL = "https://rsshub.cups.moe"
    # DEFAULT_BASE_URL = "https://rsshub.umzzz.com"
    DEFAULT_ROUTES_JSON_URL = (
        "https://raw.githubusercontent.com/RSSNext/rsshub-docs/main/src/public/routes.json"
    )
    # Alternative route index source (manual switch):
    # DEFAULT_ROUTES_JSON_URL = "file:///absolute/path/to/rsshub-routes.json"

    @classmethod
    def config_spec(cls) -> list[ConfigFieldSpec]:
        return super().config_spec() + [
            ConfigFieldSpec(
                key="base_url",
                value_type="string",
                required=False,
                secret=False,
                description=(
                    f"RSSHub instance base URL (default: {cls.DEFAULT_BASE_URL}), "
                    "e.g. http://127.0.0.1:1200"
                ),
            ),
            ConfigFieldSpec(
                key="routes_json_url",
                value_type="string",
                required=False,
                secret=False,
                description=(
                    "Route index URL "
                    f"(default: {cls.DEFAULT_ROUTES_JSON_URL}), "
                    "e.g. https://docs.rsshub.app/routes.json"
                ),
            ),
        ]

    @classmethod
    def capability_config_requirements(cls) -> dict[str, tuple[str, ...]]:
        requirements = super().capability_config_requirements()
        requirements["health"] = ()
        requirements["channel"] = ()
        requirements["search"] = ()
        requirements["subscribe"] = ()
        requirements["update"] = ()
        requirements["query"] = ()
        return requirements

    def get_storage_spec(self) -> SourceStorageSpec:
        return SourceStorageSpec(
            source=self.name,
            table_name="rsshub_records",
            record_schema="content",
            supports_keywords=True,
            time_field="published_at",
        )

    def list_channels(self) -> list[ChannelRecord]:
        channels: dict[str, ChannelRecord] = {}
        for namespace, route_key, route_data in self._iter_routes():
            top_feeds = route_data.get("topFeeds")
            if not isinstance(top_feeds, list):
                continue
            for item in top_feeds:
                if not isinstance(item, dict):
                    continue
                channel_key = self._top_feed_channel_key(item.get("url"))
                if channel_key is None:
                    continue
                channels[channel_key] = ChannelRecord(
                    source=self.name,
                    channel_id=channel_key,
                    channel_key=channel_key,
                    display_name=str(item.get("title") or route_data.get("name") or channel_key),
                    url=self._build_channel_url(channel_key),
                    metadata={
                        "namespace": namespace,
                        "route_key": route_key,
                    },
                )
        return [channels[key] for key in sorted(channels)]

    def get_channel(self, channel_key: str) -> ChannelRecord:
        normalized_key = self._normalize_channel_key(channel_key)
        if self._looks_like_template(normalized_key):
            raise ChannelNotFoundError(f"{self.name} channel requires concrete params: {normalized_key}")
        return ChannelRecord(
            source=self.name,
            channel_id=normalized_key,
            channel_key=normalized_key,
            display_name=normalized_key,
            url=self._build_channel_url(normalized_key),
            metadata={},
        )

    def health(self) -> HealthRecord:
        started_at = datetime.now(UTC)
        self._load_routes_index()
        latency_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)
        return HealthRecord(
            source=self.name,
            status="ok",
            checked_at=utc_now_iso(),
            latency_ms=latency_ms,
            error=None,
            details="rsshub routes index reachable",
        )

    def search(
        self,
        query: str,
        channel: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        needle = query.strip().lower()
        results: list[tuple[int, SearchResult]] = []
        seen: set[tuple[str, str]] = set()
        for namespace, route_key, route_data in self._iter_routes():
            if channel and namespace != channel:
                continue
            route_name = str(route_data.get("name") or "")
            example = str(route_data.get("example") or "")
            description = str(route_data.get("description") or "")
            base_text = " ".join([namespace, route_key, route_name, example, description]).lower()
            if needle and needle not in base_text:
                matched_top_feed = False
                top_feeds = route_data.get("topFeeds")
                if isinstance(top_feeds, list):
                    for item in top_feeds:
                        if not isinstance(item, dict):
                            continue
                        item_text = " ".join(
                            [
                                str(item.get("title") or ""),
                                str(item.get("description") or ""),
                                str(item.get("url") or ""),
                            ]
                        ).lower()
                        if needle in item_text:
                            matched_top_feed = True
                            break
                if not matched_top_feed:
                    continue

            top_feeds = route_data.get("topFeeds")
            if isinstance(top_feeds, list):
                for item in top_feeds:
                    if not isinstance(item, dict):
                        continue
                    channel_key = self._top_feed_channel_key(item.get("url"))
                    if channel_key is None:
                        continue
                    dedup_key = ("channel", channel_key)
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)
                    title = str(item.get("title") or route_name or channel_key)
                    score = self._search_score(needle, title, channel_key, base_text) + 200
                    results.append(
                        (
                            score,
                            SearchResult(
                                title=title,
                                url=self._build_channel_url(channel_key),
                                snippet=clean_text(str(item.get("description") or route_name)),
                                source=self.name,
                                result_kind="channel",
                                channel_key=channel_key,
                                metadata={
                                    "namespace": namespace,
                                    "route_key": route_key,
                                    "example": example,
                                },
                            ),
                        )
                    )

            template_key = route_key
            dedup_template_key = ("channel_template", template_key)
            if dedup_template_key in seen:
                continue
            seen.add(dedup_template_key)
            score = self._search_score(needle, route_name, template_key, base_text) + 100
            results.append(
                (
                    score,
                    SearchResult(
                        title=f"{namespace} - {route_name}" if route_name else template_key,
                        url=f"https://docs.rsshub.app/routes/{namespace}",
                        snippet=f"template={template_key} example={example or '-'}",
                        source=self.name,
                        result_kind="channel_template",
                        channel_key=template_key,
                        metadata={
                            "namespace": namespace,
                            "route_key": route_key,
                            "example": example,
                        },
                    ),
                )
            )

        results.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in results[:limit]]

    def get_search_view(self, kind: str) -> SearchViewSpec | None:
        if kind not in {"channel", "channel_template"}:
            return None
        return SearchViewSpec(
            columns=[
                SearchColumnSpec("result_kind", lambda result: result.result_kind, no_wrap=True),
                SearchColumnSpec("title", lambda result: result.title, max_width=32),
                SearchColumnSpec(
                    "channel_key",
                    lambda result: result.channel_key or "",
                    no_wrap=True,
                    max_width=52,
                ),
                SearchColumnSpec("url", lambda result: result.url, no_wrap=True, max_width=56),
            ]
        )

    def _fetch_remote_records(
        self,
        channel_key: str,
        record_type: str | None = None,
        limit: int = 10,
        since: str | None = None,
        fetch_all: bool = False,
    ) -> list[ContentRecord]:
        if record_type not in (None, "entry"):
            raise RuntimeError("rsshub query only supports record_type=entry")
        channel = self.get_channel(channel_key)
        xml_body = self.http.get_text(channel.url)
        records = self._parse_feed(xml_body, channel.channel_key)
        if since is not None:
            normalized_since = f"{since[:4]}-{since[4:6]}-{since[6:8]}"
            records = [
                record
                for record in records
                if record.published_at and record.published_at[:10] >= normalized_since
            ]
        if fetch_all:
            return records
        return records[:limit]

    def get_default_query_record_type(self) -> str | None:
        return "entry"

    def get_supported_record_types(self) -> tuple[str, ...]:
        return ("entry",)

    def get_help(self) -> HelpDoc | None:
        return HelpDoc(
            title="rsshub",
            summary="RSSHub 路由即频道。",
            sections=[
                HelpSection(
                    title="Config",
                    lines=[
                        "dc config set rsshub base_url <rsshub-instance-base-url>",
                        "dc config set rsshub routes_json_url <routes-json-url>",
                    ],
                ),
                HelpSection(
                    title="Examples",
                    lines=[
                        "dc search rsshub youtube --limit 20",
                        "dc sub add rsshub /youtube/channel/<id>",
                        "dc update rsshub --channel /youtube/channel/<id>",
                        "dc query --source rsshub --channel /youtube/channel/<id>",
                    ],
                ),
            ],
        )

    def _parse_feed(self, xml_body: str, channel_key: str) -> list[ContentRecord]:
        try:
            root = ET.fromstring(xml_body)
        except ET.ParseError as exc:
            raise RuntimeError(f"rsshub feed parse error: {exc}") from exc

        if root.tag.endswith("feed"):
            return self._parse_atom(root, channel_key)
        channel = root.find("./channel")
        if channel is not None:
            return self._parse_rss(channel, channel_key)
        if root.tag.lower().endswith("rss"):
            fallback_channel = root.find("./channel")
            if fallback_channel is not None:
                return self._parse_rss(fallback_channel, channel_key)
        raise RuntimeError("rsshub feed unsupported format")

    def _parse_rss(self, channel_element: ET.Element, channel_key: str) -> list[ContentRecord]:
        records: list[ContentRecord] = []
        for item in channel_element.findall("./item"):
            title = clean_text(item.findtext("title", default=""))
            link = item.findtext("link", default="")
            description = clean_text(item.findtext("description", default=""))
            guid = item.findtext("guid", default=link or title)
            pub_date = self._parse_datetime(item.findtext("pubDate"))
            author = item.findtext("author")
            if author is None:
                author = item.findtext("{http://purl.org/dc/elements/1.1/}creator")
            records.append(
                ContentRecord(
                    source=self.name,
                    channel_key=channel_key,
                    record_type="entry",
                    external_id=guid or link or title,
                    title=title or (guid or link or "entry"),
                    url=link or self._build_channel_url(channel_key),
                    snippet=description,
                    author=author,
                    published_at=pub_date,
                    fetched_at=utc_now_iso(),
                    raw_payload=ET.tostring(item, encoding="unicode"),
                    dedup_key=f"{self.name}:{channel_key}:{guid or link or title}",
                )
            )
        return records

    def _parse_atom(self, root: ET.Element, channel_key: str) -> list[ContentRecord]:
        records: list[ContentRecord] = []
        entries = root.findall("./{http://www.w3.org/2005/Atom}entry")
        if not entries:
            entries = root.findall("./entry")
        for entry in entries:
            title = clean_text(self._atom_text(entry, "title"))
            link = self._atom_link(entry)
            summary = clean_text(self._atom_text(entry, "summary") or self._atom_text(entry, "content"))
            external_id = self._atom_text(entry, "id") or link or title
            author = self._atom_text(entry, "author/name") or self._atom_text(entry, "author")
            published = self._atom_text(entry, "published") or self._atom_text(entry, "updated")
            records.append(
                ContentRecord(
                    source=self.name,
                    channel_key=channel_key,
                    record_type="entry",
                    external_id=external_id,
                    title=title or external_id,
                    url=link or self._build_channel_url(channel_key),
                    snippet=summary,
                    author=author or None,
                    published_at=self._parse_datetime(published),
                    fetched_at=utc_now_iso(),
                    raw_payload=ET.tostring(entry, encoding="unicode"),
                    dedup_key=f"{self.name}:{channel_key}:{external_id}",
                )
            )
        return records

    def _atom_text(self, node: ET.Element, path: str) -> str:
        namespaced = node.find(f"./{{http://www.w3.org/2005/Atom}}{path}")
        if namespaced is not None and namespaced.text:
            return namespaced.text
        plain = node.find(f"./{path}")
        if plain is not None and plain.text:
            return plain.text
        return ""

    def _atom_link(self, node: ET.Element) -> str:
        links = node.findall("./{http://www.w3.org/2005/Atom}link")
        if not links:
            links = node.findall("./link")
        if not links:
            return ""
        for link in links:
            rel = (link.attrib.get("rel") or "").strip()
            href = (link.attrib.get("href") or "").strip()
            if rel in {"", "alternate"} and href:
                return href
        return (links[0].attrib.get("href") or "").strip()

    def _parse_datetime(self, value: str | None) -> str | None:
        if value is None:
            return None
        raw = value.strip()
        if not raw:
            return None
        try:
            return rfc2822_to_iso(raw)
        except Exception:  # noqa: BLE001
            pass
        normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat()

    def _load_routes_index(self) -> dict:
        routes_json_url = self._require_config_string("routes_json_url")
        payload = self.http.get_json(routes_json_url)
        if not isinstance(payload, dict):
            raise RuntimeError("rsshub routes index must be an object")
        return payload

    def _iter_routes(self):
        routes_index = self._load_routes_index()
        for namespace, namespace_data in routes_index.items():
            if not isinstance(namespace_data, dict):
                continue
            routes = namespace_data.get("routes")
            if not isinstance(routes, dict):
                continue
            for route_key, route_data in routes.items():
                if isinstance(route_data, dict):
                    yield namespace, route_key, route_data

    def _top_feed_channel_key(self, raw_url: object) -> str | None:
        if not isinstance(raw_url, str) or not raw_url:
            return None
        return self._normalize_channel_key(raw_url)

    def _normalize_channel_key(self, raw_key: object) -> str:
        if not isinstance(raw_key, str):
            raise ChannelNotFoundError(f"{self.name} invalid channel key: {raw_key}")
        trimmed = raw_key.strip()
        if not trimmed:
            raise ChannelNotFoundError(f"{self.name} invalid channel key: {raw_key}")

        if trimmed.startswith("rsshub://"):
            parsed = urlsplit(trimmed)
            path = f"/{parsed.netloc}{parsed.path}"
            if parsed.query:
                path = f"{path}?{parsed.query}"
            return path

        if trimmed.startswith("http://") or trimmed.startswith("https://"):
            parsed = urlsplit(trimmed)
            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"
            return path

        if not trimmed.startswith("/"):
            trimmed = f"/{trimmed}"
        return trimmed

    def _build_channel_url(self, channel_key: str) -> str:
        base_url = self._require_config_string("base_url").rstrip("/")
        return f"{base_url}{channel_key}"

    def _require_config_string(self, key: str) -> str:
        value = self.config.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        default_value = self._default_config_value(key)
        if default_value is not None:
            return default_value
        raise SourceConfigError(f"missing required config: {self.name}.{key}")

    def _default_config_value(self, key: str) -> str | None:
        if key == "base_url":
            return self.DEFAULT_BASE_URL
        if key == "routes_json_url":
            return self.DEFAULT_ROUTES_JSON_URL
        return None

    def _looks_like_template(self, channel_key: str) -> bool:
        return _TEMPLATE_TOKEN_RE.search(channel_key) is not None

    def _search_score(self, needle: str, *texts: str) -> int:
        if not needle:
            return 1
        score = 0
        for text in texts:
            lowered = text.lower()
            if lowered.startswith(needle):
                score += 20
            if needle in lowered:
                score += 10
        return score
