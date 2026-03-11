from __future__ import annotations


SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    name TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL,
    supports_search INTEGER NOT NULL,
    supports_subscriptions INTEGER NOT NULL,
    supports_updates INTEGER NOT NULL,
    supports_query INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS channels (
    source TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    channel_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    url TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY (source, channel_key)
);

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    channel_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_updated_at TEXT,
    enabled INTEGER NOT NULL,
    metadata_json TEXT NOT NULL,
    UNIQUE (source, channel_key)
);

CREATE TABLE IF NOT EXISTS source_configs (
    source TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    value_type TEXT NOT NULL,
    is_secret INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (source, key)
);

CREATE TABLE IF NOT EXISTS groups (
    group_name TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS group_members (
    group_name TEXT NOT NULL,
    member_type TEXT NOT NULL,
    source TEXT NOT NULL,
    channel_key TEXT NOT NULL,
    PRIMARY KEY (group_name, member_type, source, channel_key)
);

CREATE TABLE IF NOT EXISTS sync_state (
    source TEXT NOT NULL,
    channel_key TEXT NOT NULL,
    cursor TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (source, channel_key)
);

CREATE TABLE IF NOT EXISTS health_checks (
    source TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    latency_ms INTEGER NOT NULL,
    error TEXT,
    details TEXT NOT NULL
);
"""


def build_content_table_schema(table_name: str) -> str:
    return f"""
CREATE TABLE IF NOT EXISTS {table_name} (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    channel_key TEXT NOT NULL,
    record_type TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    snippet TEXT NOT NULL,
    author TEXT,
    published_at TEXT,
    fetched_at TEXT NOT NULL,
    raw_payload TEXT NOT NULL,
    dedup_key TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_{table_name}_channel_type_time
ON {table_name}(channel_key, record_type, published_at DESC, record_id DESC);

CREATE INDEX IF NOT EXISTS idx_{table_name}_time
ON {table_name}(published_at DESC, record_id DESC);
"""
