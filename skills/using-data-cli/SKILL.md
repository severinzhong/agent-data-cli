---
name: using-data-cli
description: Use when the user wants to discover, track, sync, or query news, RSS, social, financial, or other external sources through agent-data-cli and any configured source workspace such as agent-data-hub.
---

# Using agent-data-cli

## Overview

`agent-data-cli` is a local information center for multi-source content.

This skill is for discovering sources, searching channels, subscribing, syncing remote content, querying the local database, and running explicit interactions against news, RSS, social media, and financial data sources.

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

## Install From skills.sh

Install this skill directly from `skills.sh`:

```bash
npx skills add https://github.com/severinzhong/agent-data-cli --skill using-data-cli
```

## Install And Repo Setup

If `agent-data-cli` is not present locally, install it first:

```bash
git clone https://github.com/severinzhong/agent-data-cli
cd agent-data-cli
uv sync
```

Then:

1. Load the bundled skills from this repository's `skills/` directory.
2. Use the repo root that contains `pyproject.toml`, `cli/`, and `store/`.
3. Treat `source_workspace` as external configuration. The default path is `./sources`, and it is typically backed by the separate `agent-data-hub` workspace.
4. Execute commands from the repo root.

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

## Usage Tips

### Configure Proxy

`proxy_url` uses one field with three states:

- unset: use the user's current network environment
- `http://127.0.0.1:7890`: force that proxy
- `direct`: force direct connection and break CLI-level proxy inheritance

When one source needs its own proxy behavior, configure it explicitly:

```bash
uv run -m adc config source set <source> proxy_url http://127.0.0.1:7890
uv run -m adc config source set <source> proxy_url direct
```

If multiple sources should share one proxy, set the CLI-level default:

```bash
uv run -m adc config cli set proxy_url http://127.0.0.1:7890
uv run -m adc config cli unset proxy_url
```

If a source needs to bypass an inherited CLI proxy, set that source to `direct`.

Inspect current source config:

```bash
uv run -m adc config source list <source>
```

### Configure `source_workspace`

Core only loads sources that exist in the current workspace.

```bash
uv run -m adc config cli explain source_workspace
uv run -m adc config cli set source_workspace ./sources
uv run -m adc config cli set source_workspace /abs/path/to/agent-data-hub
```

If the workspace contains `data_hub`, use it to discover and install official sources:

```bash
uv run -m adc content search --source data_hub --channel official --query xiaohongshu
uv run -m adc content interact --source data_hub --verb install --ref data_hub:content/xiaohongshu
```

### Schedule Updates with `cron`

Use a system scheduler when you want periodic local syncs. Keep the repo path explicit and append logs so the run can be inspected later:

```bash
30 8 * * * cd /abs/path/to/agent-data-cli && /abs/path/to/uv run -m adc content update --source bbc >> /abs/path/to/agent-data-cli/update.log 2>&1
```

If you need tighter OS integration, the same pattern can also be implemented with `launchd` or `systemd`.

### Use `--jsonl` with `jq` or `awk`

For machine filtering, prefer `--jsonl` and pipe to shell tools:

```bash
uv run -m adc content query --source cryptocompare --channel BTC --limit 30 --jsonl | jq '.title'
uv run -m adc content query --source cryptocompare --channel BTC --limit 30 --jsonl | jq 'select(.channel=="BTC")'
uv run -m adc content query --source cryptocompare --channel BTC --limit 30 --jsonl | awk -F'"' '/"channel": "BTC"/ {print $0}'
```

The same pattern works for remote discovery:

```bash
uv run -m adc channel search --source cryptocompare --query BTC --limit 5 --jsonl | jq '.channel_key'
```

### Save Output with `>` and `>>`

Use `>` to overwrite a file and `>>` to append:

```bash
uv run -m adc content query --source cryptocompare --channel BTC --limit 100 --jsonl > btc.jsonl
uv run -m adc content query --source cryptocompare --channel ETH --limit 100 --jsonl >> btc.jsonl
uv run -m adc channel search --source cryptocompare --query BTC --limit 20 --jsonl > channels.jsonl
```

This is useful when you want to:

- keep a snapshot for later analysis
- feed results into `jq`, `awk`, or other CLI tools
- accumulate multiple command outputs into one JSONL file

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
- installing source runtime dependencies must stay out of the core project manifest; use `uv pip install` or source-local `init.sh`, not `uv add`

If a task does not fit these boundaries, say so directly instead of approximating.
