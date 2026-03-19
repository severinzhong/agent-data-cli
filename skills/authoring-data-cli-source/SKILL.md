---
name: authoring-data-cli-source
description: Use when the user needs to add or redesign an agent-data-cli source for RSS, news, social media, finance, APIs, scraping, browser automation, authentication, or remote content sync.
---

# Authoring agent-data-cli source

## Overview

Use this skill to design and implement an `agent-data-cli` source with stable behavior and clear project fit.

This skill is deliberately stricter than normal feature work because a weak source design causes protocol drift, command confusion, and unreliable sync behavior.

It is the source-authoring path for RSS feeds, HTTP APIs, HTML scraping, browser-driven sites, finance data, news content, and other remote content systems that must fit the `source/channel/content` model.

Current core contract to keep in mind:

- `source/channel` is still the only core resource model
- `content update` sources return `ContentSyncBatch`, not flat per-row persistence instructions
- shared persistence is now `content_nodes`, `content_channel_links`, and `content_relations`
- structural relations in core use abstract `parent`; source-specific meaning belongs in `relation_semantic`

## Hard Gate

Do not start implementation immediately.

The required sequence is:

1. research
2. spec
3. plan
4. approval
5. implement
6. verify

If the user explicitly wants to skip a stage, say what risk that creates before proceeding.

## When to Use

Use this skill when the user wants to:

- add a new source
- redesign an existing source
- add source capabilities such as `channel search`, `content search`, `content update`, or `content interact`
- add support for RSS, APIs, scraping, browser automation, authentication, cookies, or remote side effects

Do not use this skill for:

- ordinary content operations against an existing source
- unrelated CLI or store changes with no source work

## Install From skills.sh

Install this skill directly from `skills.sh`:

```bash
npx skills add https://github.com/severinzhong/agent-data-cli --skill authoring-data-cli-source
```

## Install

If `agent-data-cli` is not present locally, install it first:

```bash
git clone https://github.com/severinzhong/agent-data-cli
cd agent-data-cli
uv sync
```

Then load the bundled skills from this repository's `skills/` directory and work from the repo root.

Important boundary:

- source code belongs in the source workspace repo, typically `agent-data-hub`
- keep `agent-data-cli` focused on core/cli/store/protocol work
- do not install source runtime dependencies into the core project with `uv add`
- use `uv pip install` or `init.sh` inside the source workspace instead

## Workflow

### 1. Research

Identify the source type before making architecture decisions.

Classify it as one or more of:

- RSS
- API
- HTML scraping
- browser-driven
- auth or session driven
- interact capable

Research must confirm:

- whether the source has a real `channel` concept
- whether remote discovery and remote sync are distinct
- how to identify unique content
- whether the source has hierarchical or container-like content that should become `content_relations`
- what time field is available
- how pagination or incremental fetch works
- what config is required
- whether interact is actually possible

Use available web research, local fetch tools, and the repo's `fetchers/` where appropriate.

### 2. Spec

Write a source-specific spec before implementation.

It must define:

- source to resource mapping
- supported capabilities
- config fields and mode if needed
- content normalization and dedup strategy
- `content_key` strategy
- whether update returns only direct content, or also context nodes and `content_relations`
- whether the source needs `relation_semantic` values such as `reply`, `contains`, or `list_item`
- storage requirements
- error boundaries
- CLI-visible semantics
- testing scope

For native search/query views:

- treat column names as a soft compatibility surface because multi-source and multi-channel aggregation merges by column header
- prefer explicit names such as `published_at`, `publisher`, `author`, `price`, `volume`
- avoid vague names such as `time`, `source`, `value` unless that meaning is genuinely exact
- column order is mainly for readability; header naming is what determines merge behavior

### 3. Plan

Turn the approved spec into an implementation plan.

The plan must break work into:

- failing tests to add first
- source code units to implement
- `ContentSyncBatch` construction path
- CLI verification steps
- persistence and audit verification

### 4. Approval

Wait for user approval after the spec and plan.

Do not jump from research straight to code.

### 5. Implement

Implement with TDD.

- write failing tests first
- verify the failure is correct
- write minimal code
- rerun focused tests

### 6. Verify

Before claiming completion, verify:

- unit tests
- CLI simulation tests
- help output
- capability and config behavior
- persistence side effects
- `content_nodes` / `content_channel_links` / `content_relations` side effects when update is involved
- interact audit behavior when applicable

## Read Next

- `references/source-contract.md` for repository rules
- `references/source-type-rss.md` for feed-like sources
- `references/source-type-api.md` for JSON or HTTP API sources
- `references/source-type-browser.md` for browser-driven sources
- `references/source-type-interact.md` for remote side effects
- `references/source-testing.md` for test matrix
- `references/source-review-checklist.md` before final verification
