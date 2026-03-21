# agent-data-cli

`agent-data-cli` is a unified multi-source content CLI for discovery, sync, local query, and explicit interaction.

It is designed for agent workflows and human operators who want one stable command surface across news, RSS, social media, market data, and other content sources that fit the `source/channel/content` model.

## Install

Recommended:

```bash
uv tool install agent-data-cli
```

If you want to use `agent-data-cli` inside an existing `uv` project:

```bash
uv add agent-data-cli
uv run adc help
```

PyPA-standard CLI install:

```bash
pipx install agent-data-cli
```

If you also want the dashboard:

```bash
uv tool install "agent-data-cli[dashboard]"
```

As a project dependency with dashboard support:

```bash
uv add "agent-data-cli[dashboard]"
uv run adc dashboard --help
```

or:

```bash
pipx install "agent-data-cli[dashboard]"
```

## Quick Start

```bash
adc init --defaults
adc help
adc source list
```

`adc init` creates the local runtime home at `~/.adc`, initializes the database, and prepares the default `source_workspace`.

## Typical Flow

```bash
adc hub search --query xiaohongshu
adc hub install xiaohongshu
adc source list
adc channel search --source xiaohongshu --query 咖啡
adc sub add --source xiaohongshu --channel <channel>
adc content update --source xiaohongshu
adc content query --source xiaohongshu --limit 20
```

## Dashboard

```bash
adc dashboard
adc dashboard start --daemon
adc dashboard status
adc dashboard stop
```

## Python Version

- Python `3.12+`

## Links

- Source: <https://github.com/severinzhong/agent-data-cli>
- Issues: <https://github.com/severinzhong/agent-data-cli/issues>
- Companion source workspace: <https://github.com/severinzhong/agent-data-hub>
