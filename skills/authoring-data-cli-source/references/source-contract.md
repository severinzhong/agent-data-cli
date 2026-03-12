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
- content records
- sync state
- source config
- action audit

Source code returns normalized records and lets the store persist them.
