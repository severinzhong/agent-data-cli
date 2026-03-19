# Source Contract

Keep the source aligned with project architecture.

## Required entry shape

Each source lives in:

```text
sources/<name>/
```

The normal entry point is:

```text
sources/<name>/source.py
```

That module must expose:

- `MANIFEST`
- `SOURCE_CLASS`

`SOURCE_CLASS` must inherit `BaseSource`.

## Project boundaries

- source-specific logic stays inside `sources/<name>/`
- sources must not import other sources
- source code must not parse CLI arguments
- source code must not read SQLite directly
- source config is declared in manifest and consumed through `self.config`

## Capability boundaries

Supported surface:

- `resolve_mode()`
- `health()`
- `list_channels()`
- `search_channels()`
- `search_content()`
- `fetch_content()`
- `update()`
- `interact()`
- `parse_content_ref()`
- `subscribe()`
- `unsubscribe()`
- `list_subscriptions()`

Unsupported operations must fail through the shared protocol layer.

## Resource model

The core model has only two resource levels:

- `source`
- `channel`

`content` is a CLI namespace, not a third resource level.

Do not invent a third core resource level in the source design.

## Persistence

The store layer owns:

- channels
- subscriptions
- content nodes
- content channel links
- content relations
- sync state
- source config
- action audit

Update-capable source code returns normalized `ContentSyncBatch` data and lets the shared store persist it.

Batch shape:

- `nodes`: `ContentNode`
- `channel_links`: `ContentChannelLink`
- `relations`: `ContentRelation`

Core relation rules:

- core only interprets abstract structural relation type `parent`
- source-specific meaning belongs in `relation_semantic`
- do not invent source-private relation storage outside the shared store
