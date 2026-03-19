from __future__ import annotations


SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    name TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    summary TEXT NOT NULL
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

CREATE TABLE IF NOT EXISTS cli_configs (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    value_type TEXT NOT NULL,
    is_secret INTEGER NOT NULL,
    updated_at TEXT NOT NULL
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

CREATE TABLE IF NOT EXISTS action_audits (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    executed_at TEXT NOT NULL,
    action TEXT NOT NULL,
    source TEXT NOT NULL,
    mode TEXT,
    target_kind TEXT NOT NULL,
    targets_json TEXT NOT NULL,
    params_summary TEXT NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    dry_run INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS content_nodes (
    node_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    content_key TEXT NOT NULL,
    content_type TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    snippet TEXT NOT NULL,
    author TEXT,
    published_at TEXT,
    fetched_at TEXT NOT NULL,
    raw_payload TEXT NOT NULL,
    content_ref TEXT,
    UNIQUE (source, content_key)
);

CREATE INDEX IF NOT EXISTS idx_content_nodes_source_time
ON content_nodes(source, published_at DESC, node_id DESC);

CREATE INDEX IF NOT EXISTS idx_content_nodes_source_type_time
ON content_nodes(source, content_type, published_at DESC, node_id DESC);

CREATE TABLE IF NOT EXISTS content_channel_links (
    source TEXT NOT NULL,
    channel_key TEXT NOT NULL,
    content_key TEXT NOT NULL,
    membership_kind TEXT NOT NULL,
    linked_at TEXT NOT NULL,
    PRIMARY KEY (source, channel_key, content_key)
);

CREATE INDEX IF NOT EXISTS idx_content_channel_links_source_channel
ON content_channel_links(source, channel_key, membership_kind);

CREATE INDEX IF NOT EXISTS idx_content_channel_links_source_content
ON content_channel_links(source, content_key);

CREATE TABLE IF NOT EXISTS content_relations (
    source TEXT NOT NULL,
    from_content_key TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    to_content_key TEXT NOT NULL,
    position INTEGER,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY (source, from_content_key, relation_type, to_content_key)
);

CREATE INDEX IF NOT EXISTS idx_content_relations_source_parent
ON content_relations(source, to_content_key, relation_type, position);

CREATE INDEX IF NOT EXISTS idx_content_relations_source_child
ON content_relations(source, from_content_key, relation_type, position);
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
    dedup_key TEXT NOT NULL UNIQUE,
    content_ref TEXT
);

CREATE INDEX IF NOT EXISTS idx_{table_name}_channel_type_time
ON {table_name}(channel_key, record_type, published_at DESC, record_id DESC);

CREATE INDEX IF NOT EXISTS idx_{table_name}_time
ON {table_name}(published_at DESC, record_id DESC);
"""
