# agent-data-cli

[English](./README.md) | [中文](./README_zh.md)

> Making All Data AI-Native.
> Turn Any Data Source into a CLI.
> Let agents operate it and aggregate the data for you.
> This project defines a protocol so data sources can talk to agents through a stable, uniform `command language`.

`agent-data-cli` is a local information center for the agent era.

Most existing data interfaces were designed for humans. You click through websites, feeds, admin panels, and scattered APIs to find and piece things together. `agent-data-cli` reorganizes that into one explicit, scriptable, locally queryable `cli` interface so agents can operate data reliably.

It gives agents and humans one unified entrypoint for:

- news
- social media content
- financial data
- RSS feeds
- other content sources that can be mapped into the `source/channel/content` model

This repository is also a pack of loadable skills for:

- Codex
- Claude Code
- OpenClaw

Once those built-in skills are loaded, an agent can follow the same command surface to discover sources, sync updates, and read results step by step through one command at a time.

## Why agent-data-cli?

- AI-native tools need a stable command surface, not a pile of temporary webpage paths and site scripts.
- Multi-source data should behave like one system, not a collection of unrelated site adapters.
- Discovery, sync, local query, and remote side effects need clear boundaries.
- Agents need an information center they can inspect, update, query, and extend, not a toolbox built from implicit behavior.

In one line: `agent-data-cli` is about making all data AI-native and turning any data source into a CLI.

## Install with an Agent

Give your agent the repository URL directly. You can say things like:

- "Install `agent-data-cli` from `https://github.com/severinzhong/agent-data-cli`, load the built-in skills, and use it directly for me."
- "Use `agent-data-cli` to help me find a source, subscribe to channels, sync updates, and then read the local results."
- "Use the source authoring skill in `agent-data-cli` to add a new source for me."

## Install These Two skills Separately from skills.sh

If you only want these two built-in skills, run:

```bash
npx skills add https://github.com/severinzhong/agent-data-cli --skill using-data-cli
npx skills add https://github.com/severinzhong/agent-data-cli --skill authoring-data-cli-source
```

## Semantic Alignment

`agent-data-cli` keeps only two core resource levels: `source` and `channel`.

- `source`: a concrete data source implementation and a capability boundary, such as a news site, a market data provider, or a social media platform.
- `channel`: a trackable target inside a source. A channel can be a feed, a stock symbol, or an RSSHub route. You can discover channels, subscribe or unsubscribe them, add them to groups, and run `content update` on subscribed channels. Examples include BBC's `world`, A-share symbol `sh600001`, and RSSHub route `/youtube/channel/<id>`.
- `content`: a remote search result or a local record written after sync. You use `content search` for remote discovery, `content query` for local reads, and `content update` to sync remote content from subscribed channels into the local store. If a source later declares interaction verbs, you can also use `content interact` to run explicit remote actions on individual content items.

## Current Built-in Sources

| Source | Channel Search | Content Search | Update | Query | Interact |
| --- | --- | --- | --- | --- | --- |
| `ashare` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `bbc` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `cryptocompare` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `hackernews` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `xiaohongshu` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `rsshub` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `sina_finance_724` | ❌ | ❌ | ✅ | ✅ | ❌ |
| `usstock` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `wechatarticle` | ❌ | ✅ | ❌ | ❌ | ❌ |

## Thanks 

to [jackwener/xiaohongshu-cli](https://github.com/jackwener/xiaohongshu-cli).

After equipping the `authoring-data-cli-source` skill, tell your agent to turn `https://github.com/jackwener/xiaohongshu-cli` into a source, then follow the agent's guidance step by step. From development through testing, the whole process took about 3-4 hours. enjoy~💗

---

# The Rest Below Is for Agents, Not Humans

## Requirements

- Python `3.12+`
- `uv`

Install dependencies:

```bash
uv sync
```

## Proxy Configuration

`proxy_url` keeps a single field with three meanings:

- unset: use the user's current network environment
- `http://127.0.0.1:7890`: force that proxy
- `direct`: force direct connection and do not inherit the CLI-level proxy

Examples:

```bash
uv run -m adc config cli set proxy_url http://127.0.0.1:7890
uv run -m adc config source set bbc proxy_url direct
uv run -m adc config cli unset proxy_url
```

## How It Works

For an agent, the shortest path is:

1. Discover a source or channel.
2. Subscribe first if you want to track it continuously.
3. Sync remote data into the local store.
4. Read from the local database.
5. Run explicit remote interactions only when needed.

Unified entrypoint:

```bash
uv run -m adc ...
```

## Command Model

The stable command families are:

```text
source
channel
content
sub
group
config
help
```

Semantic boundaries:

- `channel search`: remote channel discovery only
- `content search`: remote content discovery only, no persistence
- `content update`: sync subscribed targets and write them locally
- `content query`: local-only query
- `content interact`: explicit remote side effects only

## Minimal CLI Surface

Keeping a few common examples is enough:

```bash
uv run -m adc help
uv run -m adc source list
uv run -m adc content search --source bbc --query openai --limit 5
uv run -m adc content update --group stocks --dry-run
uv run -m adc content query --source bbc --limit 10
```

Interact command shape:

```bash
uv run -m adc content interact --source <source> --verb <verb> --ref <content_ref> [--ref <content_ref> ...] [verb options...]
```

## Local Data

Default database file:

```text
agent-data-cli.db
```

The shared store layer persists:

- channels
- subscriptions
- groups
- group members
- sync state
- health checks
- source configs
- cli configs
- action audits
- per-source content tables such as `bbc_records` and `rsshub_records`

## Project Layout

```text
cli/        argument parsing, command dispatch, output formatting
core/       protocol, manifest, registry, shared models
fetchers/   HTTP / browser fetching
store/      SQLite persistence, deduplication, sync state, config, audit
sources/    isolated source implementations
skills/     agent skills shipped with the repository
tests/      unit tests and simulated CLI tests
```

Current built-in skills:

- [`using-data-cli`](./skills/using-data-cli/SKILL.md)
- [`authoring-data-cli-source`](./skills/authoring-data-cli-source/SKILL.md)

## Testing

Run the full test suite:

```bash
env -u http_proxy -u https_proxy -u all_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u no_proxy -u NO_PROXY .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

`tests/test_browser_fetcher.py` is a real integration test and requires a local Chrome instance with CDP enabled at:

```text
http://127.0.0.1:9222
```

## Developing a New Source

The standard path for adding a new source is:

1. Create `sources/<name>/source.py`.
2. Inherit `BaseSource`.
3. Declare `MANIFEST` and `SOURCE_CLASS`.
4. Keep site-specific logic inside `sources/<name>/`.

If the source is more complex, prefer splitting it into local modules under `sources/<name>/` instead of piling everything into one oversized `source.py`.
