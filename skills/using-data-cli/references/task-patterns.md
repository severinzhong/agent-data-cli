# Task Patterns

Use these patterns to translate user intent into CLI flows.

## Temporary inspection

User intent:

- "Search BBC for OpenAI"
- "Look up recent WeChat articles about AI"
- "See what RSSHub has for YouTube"

Pattern:

1. pick the source
2. run `channel search` or `content search`
3. report findings

Do not subscribe or update unless the user asks for tracking.

## Ongoing tracking

User intent:

- "Track BBC world"
- "Keep watching this stock"
- "Subscribe to this feed and sync it"

Pattern:

1. identify source and channel
2. run `sub add`
3. run `content update`
4. run `content query`
5. report sync result and local records

## Local investigation

User intent:

- "What do I already have about Iran?"
- "Show my stored posts from top HN"
- "Query local financial records since last week"

Pattern:

1. stay local
2. run `content query`
3. filter with `--source`, `--channel`, `--group`, `--keywords`, or `--since`

Do not trigger remote work.

## Group update

User intent:

- "Update my stocks group"
- "Dry run the group expansion first"

Pattern:

1. if the user wants inspection, run `content update --group <group> --dry-run`
2. otherwise run `content update --group <group>`
3. then use `content query --group <group>` if the user wants local results

## Remote side effects

User intent:

- "Like this item"
- "Comment on these refs"
- "Run this interact verb"

Pattern:

1. require explicit source
2. require explicit refs
3. require explicit verb
4. run `content interact`
5. report the per-ref result

Never infer refs from a prior search result unless the user explicitly picks them.
