# agent-data-cli

[English](./README.md) | [中文](./README_zh.md)

> Making All Data AI-Native.
> Turn Any Data Source into a CLI.

`agent-data-cli` is a local information center for the agent era.

Most data interfaces were designed for humans to click through websites, feeds, dashboards, and APIs. `agent-data-cli` restructures that world into one explicit, scriptable, local-first interface that agents can actually operate.

It gives agents and humans one consistent interface for:

- news
- social media content
- financial data
- RSS feeds
- other sources that can fit the `source/channel/content` model

The command entrypoint is:

```bash
uv run -m adc ...
```

This repository is also a bundled skill pack for:

- Codex
- Claude Code
- OpenClaw

Once the bundled skills are loaded, an agent can use one command at a time to discover sources, sync updates, and read local results through the same command surface.

## Install with an Agent

Give your agent this repository:

```text
https://github.com/severinzhong/agent-data-cli
```

Then ask it to:

1. clone the repository
2. run `uv sync`
3. load the bundled skills
4. use `agent-data-cli` to discover sources, update them, and read local results

Example prompts:

- "Install `agent-data-cli` from `https://github.com/severinzhong/agent-data-cli`, load its bundled skills, and use it for me."
- "Use `agent-data-cli` to find a source, subscribe to a channel, sync it, and then query the local records."
- "Use the bundled source-authoring skill from `agent-data-cli` and scaffold a new source."

## Install Individual skills from skills.sh

Install the two bundled skills individually from `skills.sh`:

```bash
npx skills add https://github.com/severinzhong/agent-data-cli --skill using-data-cli
npx skills add https://github.com/severinzhong/agent-data-cli --skill authoring-data-cli-source
```

## Why agent-data-cli?

- AI-native tools need stable command surfaces instead of ad hoc browsing paths.
- Multi-source data should look like one system, not a collection of unrelated site scripts.
- Discovery, sync, local query, and remote side effects need hard semantic boundaries.
- Agents need a local information center they can inspect, update, and extend without hidden behavior.

In one line: `agent-data-cli` is about making all data AI-Native and turning any data source into a CLI.

## Status

The current implementation follows the redesign spec:

- [data-cli core redesign](./docs/superpowers/specs/2026-03-12-data-cli-core-redesign-design.md)

The project has already switched to a resource-first command surface:

- the core model keeps only two resource levels: `source` and `channel`
- `content` is a CLI namespace, not a third core resource
- top-level command groups are `source`, `channel`, `content`, `sub`, `group`, `config`, and `help`
- `channel search` and `content search` are separate remote discovery actions
- `content search` never writes to the local database
- `content update` is the only remote sync path that writes records locally
- `content query` always reads from the local database
- `content interact` is the explicit remote side-effect protocol
- sources are auto-discovered through `MANIFEST + SOURCE_CLASS`

## Built-in Sources

| Source | Channel Search | Content Search | Update | Query | Interact |
| --- | --- | --- | --- | --- | --- |
| `ashare` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `bbc` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `cryptocompare` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `hackernews` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `rsshub` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `sina_finance_724` | ❌ | ❌ | ✅ | ✅ | ❌ |
| `usstock` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `wechatarticle` | ❌ | ✅ | ❌ | ❌ | ❌ |

Notes:

- no built-in source currently declares `mode`
- the core `content.interact` protocol is implemented, but built-in sources do not expose public verbs yet
- `wechatarticle` is discovery-only
- `rsshub` needs a working RSSHub instance URL and route index URL

## Requirements

- Python `3.12+`
- `uv`

Install dependencies:

```bash
uv sync
```

## How It Works

For an agent, the happy path is simple:

1. discover a source or channel
2. subscribe if ongoing tracking is needed
3. sync remote data locally
4. read from the local database
5. run explicit remote interactions when needed

Core entrypoint:

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
- `content update`: sync subscribed targets and persist records
- `content query`: local-only querying
- `content interact`: explicit remote side effects only

## Minimal CLI Surface

Useful examples:

```bash
uv run -m adc help
uv run -m adc source list
uv run -m adc content search --source bbc --query openai --limit 5
uv run -m adc content update --group stocks --dry-run
uv run -m adc content query --source bbc --limit 10
```

Interact format:

```bash
uv run -m adc content interact --source <source> --verb <verb> --ref <content_ref> [--ref <content_ref> ...] [verb options...]
```

## Local Data

Default database file:

```text
agent-data-cli.db
```

The shared store persists:

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
cli/        argument parsing, dispatch, output
core/       protocol, manifest, registry, shared models
fetchers/   HTTP and browser acquisition
store/      SQLite persistence, dedup, sync state, config, audit
sources/    isolated source implementations
skills/     bundled agent skills
tests/      unit tests and CLI simulation tests
```

Included skills:

- [`using-data-cli`](./skills/using-data-cli/SKILL.md)
- [`authoring-data-cli-source`](./skills/authoring-data-cli-source/SKILL.md)

## Testing

Run the full test suite:

```bash
env -u http_proxy -u https_proxy -u all_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u no_proxy -u NO_PROXY .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

`tests/test_browser_fetcher.py` is a real integration test and expects a local Chrome instance with CDP enabled at:

```text
http://127.0.0.1:9222
```

## Source Development

The standard path for a new source is:

1. create `sources/<name>/source.py`
2. inherit `BaseSource`
3. declare `MANIFEST` and `SOURCE_CLASS`
4. keep all site-specific logic inside `sources/<name>/`

If the source is complex, split local logic into additional modules under `sources/<name>/` instead of growing one large `source.py`.
