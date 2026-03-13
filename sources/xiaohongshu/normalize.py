from __future__ import annotations

import json
from datetime import UTC, datetime

from core.models import ChannelRecord, ContentRecord, SearchResult, build_content_ref
from core.protocol import InvalidChannelError, InvalidContentRefError
from utils.text import clean_text, normalize_whitespace
from utils.time import utc_now_iso


def parse_user_channel_key(channel_key: str) -> str:
    normalized = channel_key.strip()
    prefix, separator, user_id = normalized.partition("/")
    if prefix != "user" or separator != "/" or not user_id:
        raise InvalidChannelError("xiaohongshu channel must use user/<user_id>")
    return user_id


def build_user_channel_key(user_id: str) -> str:
    normalized = user_id.strip()
    if not normalized:
        raise InvalidChannelError("xiaohongshu user_id cannot be empty")
    return f"user/{normalized}"


def build_note_opaque_id(note_id: str) -> str:
    normalized = note_id.strip()
    if not normalized:
        raise InvalidContentRefError("xiaohongshu note_id cannot be empty")
    return f"note:{normalized}"


def parse_note_opaque_id(opaque_id: str) -> str:
    normalized = opaque_id.strip()
    prefix, separator, note_id = normalized.partition(":")
    if prefix != "note" or separator != ":" or not note_id:
        raise InvalidContentRefError("xiaohongshu content_ref must use note:<note_id>")
    return note_id


def summarize_note_text(body: str, *, title_limit: int = 40, snippet_limit: int = 140) -> tuple[str, str]:
    lines = [clean_text(line) for line in body.splitlines()]
    non_empty_lines = [line for line in lines if line]
    if not non_empty_lines:
        return "", ""
    title = _truncate(non_empty_lines[0], title_limit)
    snippet = _truncate(normalize_whitespace(" ".join(non_empty_lines)), snippet_limit)
    return title, snippet


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit].rstrip()


def user_channel_record(payload: dict[str, object]) -> ChannelRecord:
    base = payload.get("user_base_dto")
    if isinstance(base, dict):
        payload = {**payload, **base}
    user_id = str(
        payload.get("user_id")
        or payload.get("id")
        or payload.get("userid")
        or ""
    ).strip()
    if not user_id:
        raise RuntimeError("xiaohongshu user payload missing user_id")
    nickname = str(payload.get("nickname") or payload.get("user_nickname") or payload.get("name") or user_id).strip()
    red_id = str(payload.get("red_id") or payload.get("username") or "").strip()
    avatar = str(payload.get("avatar") or payload.get("images") or payload.get("image") or "").strip()
    fans = str(payload.get("fans") or payload.get("fans_count") or "").strip()
    return ChannelRecord(
        source="xiaohongshu",
        channel_id=user_id,
        channel_key=build_user_channel_key(user_id),
        display_name=nickname,
        url=f"https://www.xiaohongshu.com/user/profile/{user_id}",
        metadata={
            "user_id": user_id,
            "nickname": nickname,
            "red_id": red_id,
            "avatar": avatar,
            "fans": fans,
        },
    )


def search_result_from_note(payload: dict[str, object]) -> SearchResult:
    note = _note_payload(payload)
    note_id = _note_id(payload)
    author = _author_name(note)
    author_user_id = _author_user_id(note)
    title, snippet = summarize_note_text(_note_text(note))
    return SearchResult(
        title=title or note_id,
        url=f"https://www.xiaohongshu.com/explore/{note_id}",
        snippet=snippet,
        source="xiaohongshu",
        channel_key=build_user_channel_key(author_user_id) if author_user_id else None,
        metadata={
            "author": author,
            "published_at": _timestamp_to_iso(_note_timestamp(note)),
        },
        content_ref=build_content_ref("xiaohongshu", build_note_opaque_id(note_id)),
    )


def content_record_from_note(channel_key: str, payload: dict[str, object]) -> ContentRecord:
    note = _note_payload(payload)
    note_id = _note_id(payload)
    title, snippet = summarize_note_text(_note_text(note))
    published_at = _timestamp_to_iso(_note_timestamp(note))
    return ContentRecord(
        source="xiaohongshu",
        channel_key=channel_key,
        record_type="note",
        external_id=note_id,
        title=title or note_id,
        url=f"https://www.xiaohongshu.com/explore/{note_id}",
        snippet=snippet,
        author=_author_name(note) or None,
        published_at=published_at,
        fetched_at=utc_now_iso(),
        raw_payload=json.dumps(note, ensure_ascii=False),
        dedup_key=f"note:{note_id}",
        content_ref=build_content_ref("xiaohongshu", build_note_opaque_id(note_id)),
    )


def note_search_items(payload: dict[str, object]) -> list[dict[str, object]]:
    items = payload.get("items", [])
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    notes = payload.get("notes", [])
    if isinstance(notes, list):
        return [item for item in notes if isinstance(item, dict)]
    return []


def paged_user_notes(payload: dict[str, object]) -> tuple[list[dict[str, object]], bool, str]:
    notes = payload.get("notes", [])
    if not isinstance(notes, list):
        notes = []
    normalized_notes = [note for note in notes if isinstance(note, dict)]
    return normalized_notes, bool(payload.get("has_more", False)), str(payload.get("cursor", "") or "")


def note_iso_time(payload: dict[str, object]) -> str | None:
    return _timestamp_to_iso(_note_timestamp(_note_payload(payload)))


def _note_payload(payload: dict[str, object]) -> dict[str, object]:
    note_card = payload.get("note_card")
    if isinstance(note_card, dict):
        return note_card
    return payload


def _note_id(payload: dict[str, object]) -> str:
    note = _note_payload(payload)
    note_id = str(
        note.get("note_id")
        or payload.get("id")
        or note.get("id")
        or ""
    ).strip()
    if not note_id:
        raise RuntimeError("xiaohongshu note payload missing note_id")
    return note_id


def _note_text(note: dict[str, object]) -> str:
    return str(
        note.get("display_title")
        or note.get("title")
        or note.get("desc")
        or note.get("content")
        or ""
    )


def _author_name(note: dict[str, object]) -> str:
    user = note.get("user")
    if isinstance(user, dict):
        return str(user.get("nickname") or user.get("name") or "").strip()
    return ""


def _author_user_id(note: dict[str, object]) -> str:
    user = note.get("user")
    if isinstance(user, dict):
        return str(user.get("user_id") or user.get("id") or "").strip()
    return ""


def _note_timestamp(note: dict[str, object]) -> int | None:
    raw_value = note.get("time") or note.get("publish_time") or note.get("last_update_time")
    if raw_value in (None, ""):
        return None
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None
    if value > 10_000_000_000:
        return value // 1000
    return value


def _timestamp_to_iso(timestamp: int | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, UTC).isoformat()
