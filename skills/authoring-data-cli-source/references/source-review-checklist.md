# Source Review Checklist

Use this checklist before completion.

## Semantics

- Does the source fit the `source/channel` model cleanly?
- Is `content` treated as a CLI namespace instead of a third resource level?
- Are `search`, `update`, `query`, and `interact` kept separate?

## Capabilities

- Are unsupported actions rejected explicitly?
- Are unsupported options rejected explicitly?
- Is help aligned with capability and config state?

## Config

- Is every source config key declared in manifest?
- Is conditional config only driven by mode?
- Does the source consume `self.config` instead of reading SQLite or env directly?

## Persistence

- Does the source return normalized `ContentSyncBatch` data without doing its own persistence?
- Is `content_key` based on stable identity fields?
- If the source has container or hierarchy structure, does it use shared `content_relations` instead of source-private storage?
- If the source needs relation meaning, is it carried by `relation_semantic` instead of a core-specific relation type?
- Is sync state updated only through the shared store path?

## Implementation shape

- Is `source.py` still readable as an entry point?
- If the source is complex, has internal logic been split into local helper modules?
- Does the source avoid importing any other source?

## Tests

- Did you add failing tests first?
- Did you run focused tests and broader verification?
- Did you cover CLI misuse paths as well as happy paths?
