---
name: using-data-cli
description: Use when the user wants to use agent-data-cli as a local information center for news, social media, financial data, RSS feeds, or other multi-source content, and needs to discover, subscribe, sync, query, or interact with that content.
---

# Using agent-data-cli

## Overview

`agent-data-cli` is a local information center for multi-source content.

Use it for:

- news
- social media
- financial data
- RSS feeds
- other sources that fit the `source/channel/content` model

This skill is operational, not explanatory. When the user's goal is clear, execute the CLI flow directly instead of only suggesting commands.

## When to Use

Use this skill when the user wants to:

- inspect available sources or channels
- discover remote content before subscribing
- subscribe to channels for ongoing tracking
- sync subscribed channels into the local database
- query locally stored content
- run explicit remote interactions on content refs

Do not use this skill for:

- implementing or redesigning a source
- changing the command surface or core protocol
- free-form scraping outside the `agent-data-cli` model

## Repo Setup

Assume the full `agent-data-cli` repository is present locally.

Before first use:

1. Locate the repo root that contains `pyproject.toml`, `cli/`, `sources/`, and `store/`.
2. Run `uv sync` if dependencies are not ready.
3. Execute commands from the repo root.

Always prefer:

```bash
uv run -m adc ...
```

## Operating Rules

- Translate natural language into the smallest correct CLI flow.
- Respect the command semantics exactly.
- Do not invent fallback behavior when a capability is unsupported.
- Do not hide remote side effects behind search or update.
- Do not turn `content query` into a remote search.
- Do not auto-subscribe unless the user's goal implies ongoing tracking.
- For `content interact`, require an explicit source and explicit refs.

Read `references/command-semantics.md` before using a command family you have not touched in the current session.

Read `references/task-patterns.md` when the user request is ambiguous and needs stable intent-to-command mapping.

Read `references/result-reporting.md` before reporting back after a multi-step run.

## Execution Flow

1. Classify the request as discovery, subscription, sync, local query, or remote interact.
2. Check whether the task should stay local or requires remote execution.
3. If needed, inspect source capability and config state before executing the main command.
4. Run the shortest correct command chain.
5. Report what was done, what was found, and what next action is now available.

## Hard Boundaries

- `channel search` is remote channel discovery only.
- `content search` is remote content discovery only and does not write to the database.
- `content update` is the only remote sync path that writes to the database.
- `content query` is local-only and never triggers remote work.
- `content interact` is explicit remote side effect execution only.

If a task does not fit these boundaries, say so directly instead of approximating.
