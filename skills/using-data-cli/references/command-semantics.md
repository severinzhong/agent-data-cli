# Command Semantics

Use this file to keep command meanings strict.

## Source and channel

- `source list`: list registered sources and their capability state.
- `source health <source>`: run source health check.
- `channel list <source>`: list known channels provided by the source.
- `channel search --source <source> --query <query>`: remote channel discovery only.

`channel search` does not write to the database.

## Content discovery and sync

- `content search`: remote content discovery only
- `content update`: remote sync for subscribed targets only
- `content query`: local database query only
- `content interact`: explicit remote side effects only

Never blur these boundaries.

## Important rules

- `content search` does not persist records.
- `content update` only works on already subscribed targets.
- `content query` never becomes remote search because of `--keywords`.
- `content update --group --dry-run` expands targets and prints them without remote execution.
- `content interact` must use explicit `--source`, `--verb`, and one or more explicit `--ref`.

## Option boundaries

- `--channel` with `content query` requires `--source`.
- `--channel` cannot be combined with `--group` in `content query`.
- `--source` and `--group` are mutually exclusive in `content update`.
- `--all` cannot be combined with `--since` or `--limit` in `content update`.

## Safe defaults

- Prefer `content search` when the user says "search", "find", or "show me what exists" and does not ask for persistence.
- Prefer `sub add` plus `content update` plus `content query` when the user wants ongoing tracking.
- Prefer `content query` when the user asks about already synced local data.
